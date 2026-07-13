# Host Integration Guide — What Other Components Need To Set Up

This is the reference for anyone building a component *other than the Host* (e.g. the
`event-creator` repo, or any future hosted app) that needs to plug into `organize-me`. It answers,
per slice: what infra to provision, what routing to wire up, what secrets to read, and what
interface/design contract the Host expects a hosted app to honor.

It is a living document — **update it in the same PR that lands each new Platform Restructure
slice** (`docs/platform-restructure/WBS/slice-R*.md`), whether or not that slice touches another
repo directly. Each slice gets its own `## Slice R<n> — <name>` section below, added in order.

For the full architecture rationale, see
[`platform-restructure-design.md`](platform-restructure-design.md) (design) and
[`platform-restructure-prd.md`](platform-restructure-prd.md) (product intent). For the
credential/secret journey in detail, see [`secrets-and-accounts.md`](secrets-and-accounts.md) —
this doc summarizes the actionable subset; that one is the full reference.

## Quick-start checklist for a brand-new hosted app

If you're standing up app #3 (or later) from scratch, you need, at minimum:

1. Its own git repo with independent CI/CD (build → test → deploy) — never a Host build/redeploy.
2. A `<app>-qa` / `<app>-prod` Cloud Run service pair.
3. A pinned dependency on the Host's published `organizeme-chrome` package (chrome/theme templates
   + JWT-verify helper + app-registry data).
4. An entry in the Host-authored app-registry (`packages/chrome/src/organizeme_chrome/registry.py`)
   describing its nav items and Settings tabs — this is the single source of truth for both what
   renders in the sidebar *and* what the Load Balancer routes to your service.
5. Its own Postgres schema (ask for one to be added via `ALTER TABLE ... SET SCHEMA` if reusing
   existing tables, or create fresh ones) with its **own** independent Alembic history
   (`version_table_schema = <your_schema>`).
6. `GCP_SA_KEY` and `SUPABASE_QA_URL`/`SUPABASE_PROD_URL` as GitHub Actions secrets in **your own**
   repo (not shared from the Host's repo).
7. `--set-secrets=JWT_SECRET=jwt-secret-{qa,prod}:latest` on your `gcloud run deploy` step — same
   secret name/value as every other hosted app, read-only, signature-verify only.
8. If you need `ENCRYPTION_KEY` (Fernet-encrypted credentials at rest): same pattern, add
   `--set-secrets=ENCRYPTION_KEY=encryption-key-{qa,prod}:latest`.
9. No login, session, registration, or password-handling code of your own, ever — identity comes
   entirely from verifying the Host-issued JWT cookie.
10. No server-to-server call to the Host at request time, for anything.

Everything below traces exactly which slice introduced each of these requirements, and what's
still pending.

---

## Slice R0 — DNS control for `organizeme.russcoopersoftware.com`

**Type:** Manual ops, no code.

- **Infra:** New Cloud DNS public zone `russcoopersoftware-com` in GCP project
  `gen-lang-client-0791944342`; registrar (Squarespace) nameservers repointed to it.
- **Routing:** None yet — this only proves DNS is editable. The actual A/AAAA cutover to the Load
  Balancer IP happens in R5 (QA) and R11/R12 (prod).
- **Secrets:** None.
- **Interface impact on other components:** None directly, but it's the blocking prerequisite for
  R5's managed SSL cert, so no hosted app gets a stable shared-origin URL until this lands.

## Slice R1 — Database schema separation

- **Infra:** Two Postgres schemas, `host` and `event_creator`, in the existing shared Supabase
  instance. Two `NOLOGIN` roles, `host_app` and `event_creator_app`, least-privilege per schema.
- **Routing:** None.
- **Secrets:** None new.
- **Interface contract for other components:**
  - Every table your app owns lives in **your own schema**, never `host` or another app's schema.
  - If you need a real FK back to `host.users.id`, you get a narrow `REFERENCES`-only grant on that
    one column — never `SELECT`/`INSERT`/`UPDATE` on `host.*`.
  - Your Alembic history must set `version_table_schema` to your own schema name so it never
    collides with the Host's or another app's migration history, even though everyone connects to
    the same physical database.
  - Migrating existing tables into a new schema is metadata-only (`ALTER TABLE ... SET SCHEMA`) —
    no data rewritten.

## Slice R2 — Decouple Event Creator data from the Host `users` model

- **Infra:** New `event_creator.user_settings` table (notification prefs, onboarding flags),
  FK-cascaded to `host.users.id`.
- **Routing:** None.
- **Secrets:** None.
- **Interface contract:** Any per-user preference/state that isn't strictly account identity
  (email, password, OAuth) belongs in **your own schema**, not on the Host's `users` table — create
  it lazily (get-or-create) rather than eagerly at registration, since the Host has no idea your
  app exists at registration time.

## Slice R3 — Shared chrome/theme package + app-registry

- **Infra:** New `packages/chrome/` package, `organizeme-chrome`, published by the Host's CI as a
  versioned GitHub Release wheel/sdist on `chrome-v*` tag push (git-tag dependency pin, not a
  private PyPI registry).
- **Routing:** N/A directly, but this package now bundles the app-registry data that R5 turns into
  routing rules.
- **Secrets:** None.
- **Interface contract for other components — this is the core integration surface:**
  - Depend on `organizeme-chrome` as a **pinned** version — bumping it is a deliberate, explicit
    action in your repo, never automatic. A Host-side chrome edit never silently changes what your
    app renders.
  - It gives you: Jinja macros/templates for sidebar/header/Settings tab-bar, the Tailwind/DaisyUI
    theme, the app-registry data, and a standalone JWT-verify helper (PyJWT-based — signature +
    expiry + audience only, **no** fastapi-users import, **no** network call).
  - You add your app's nav items and Settings tabs to the app-registry (authored in the Host repo);
    this one file drives both what renders in the sidebar and (from R5 onward) what the Load
    Balancer routes to you.
  - Extend `chrome_base.html` / `chrome_authenticated_base.html` from the package for every page —
    don't hand-roll chrome.

## Slice R4 — Domain-scoped SSO cookie + Secret Manager

- **Infra:** `JWT_SECRET` moved off plaintext env vars into GCP Secret Manager
  (`jwt-secret-qa`/`jwt-secret-prod`), read via `--set-secrets` by the Cloud Run runtime service
  account (`170051512639-compute@developer.gserviceaccount.com`, granted
  `roles/secretmanager.secretAccessor` on it).
- **Routing:** N/A — cookie domain scoping is deferred until R5/R11 land (still unset on
  `*.run.app` hosts as of R6).
- **Secrets:** Your `gcloud run deploy` step needs
  `--set-secrets=JWT_SECRET=jwt-secret-{qa,prod}:latest`. This must be the **exact same secret**,
  byte-identical, as the Host's — that identity is the entire SSO trust mechanism, not a
  coincidence.
- **Interface contract:** Your app verifies the JWT's signature + expiry only. It never signs a
  JWT, never handles a password, never talks to fastapi-users.

## Slice R5 — GCP HTTPS Load Balancer + path routing + managed SSL

- **Infra:** External HTTPS Load Balancer, two global static IPs (v4+v6), Cloud DNS A/AAAA records
  in the R0 zone, Google-managed SSL cert, one Serverless NEG per Cloud Run service, backend
  services, URL map, target-HTTPS-proxy, global forwarding rules. Provisioned via
  `infra/gcp_lb/provision.sh` (idempotent `gcloud` script, not Terraform) — a manual operator run,
  not part of CI.
- **Routing:** `infra/gcp_lb/generate_url_map.py` turns the app-registry (R3) into URL-map path
  rules automatically: the Host's fixed auth routes always win a collision; two non-host apps can't
  claim the same path (build-time guard).
- **Secrets:** None new.
- **Interface contract:** Once your app-registry entry lists your nav paths, you get routed to
  automatically the next time the URL map is regenerated — you don't hand-edit the Load Balancer
  yourself. Your Cloud Run service needs its own Serverless NEG/backend service added at this
  layer (done for Event Creator in R6, below).

## Slice R6 — Event Creator scaffold + SSO-trust tracer bullet

- **Infra:** First independent hosted-app repo (`event-creator`), its own `event-creator-qa` /
  `event-creator-prod` Cloud Run services, own CI/CD mirroring the Host's `.github/workflows/`
  shape (build → test → deploy, no Host build/redeploy involved).
- **Routing:** `event-creator-qa` attached to the R5 URL map's second NEG/backend so
  `organizeme.qa.russcoopersoftware.com/dashboard` routes there.
- **Secrets:** Reads `JWT_SECRET` from Secret Manager (same value as Host, R4). Does **not** need
  `ENCRYPTION_KEY` yet (no stored credentials of its own).
- **Interface contract exercised end-to-end for the first time:**
  - `GET /dashboard` → verify JWT (signature + expiry via the R3 helper) → extract `user_id` →
    render shared chrome + placeholder body. No login/session/registration code in this repo at
    all.
  - Owns the `event_creator` schema (moved to it in R1) with its **own** Alembic history from here
    on — the Host no longer touches those tables' migrations.
  - Unauthenticated request to `/dashboard` redirects to the Host's login — proves the negative
    case, not just the happy path.
  - **Gotcha hit during this slice:** the Host's own `pyproject.toml` had a stale
    `organizeme-chrome` pin that silently kept the live URL map on the pre-R3-split registry — the
    Host repo must bump its own chrome-package pin whenever the package's app-registry changes, the
    same as any other consumer.

## Slice R7 — Parity 1: Storage + Settings tabs

- **Infra:** No new Cloud Run/DNS resources — same `event-creator-{qa,prod}` services from R6.
  New GCP Secret Manager secrets: `google-oauth-client-secret-{qa,prod}`,
  `dropbox-oauth-client-secret-{qa,prod}` (client *ids* are non-confidential and travel as plain
  Cloud Run env vars instead, alongside `DATABASE_URL`). `encryption-key-{qa,prod}` already existed
  from R6 and needed no new setup.
- **Routing:** None new — Storage/Notifications/Preferences are tab *content* Event Creator
  contributes to the Host-rendered Settings shell via the app-registry (R3), not new top-level
  routes the Load Balancer needs to know about.
- **Secrets:** `--set-secrets=ENCRYPTION_KEY=encryption-key-{qa,prod}:latest` (Fernet key,
  encrypts stored OAuth tokens/S3 keys at rest) alongside R4's `JWT_SECRET`. OAuth client *secrets*
  (Google/Dropbox) also travel via `--set-secrets`, matching the reasoning that confidential values
  never sit in a plaintext env-vars file readable via `gcloud run services describe`.
- **Interface contract:**
  - Event Creator owns `event_creator.storage_configs` (one row per user, encrypted
    Drive/Dropbox/S3 credentials) and drives the R2 `user_settings` table's notification toggles.
  - A hosted app that stores third-party credentials encrypts them at rest with the shared
    `CredentialCipher`/`ENCRYPTION_KEY` pattern (`app/core/security.py`) — never plaintext.
  - The Host still renders the Settings *shell* (tab-bar chrome, per R3); a hosted app supplies
    only tab *content* and declares its tabs via the app-registry — no hosted-app chrome code.
  - OAuth callback redirect URIs for a hosted app's own connect flow are *additional* authorized
    redirect URIs added to the Host's existing Google/Dropbox OAuth app consoles (client id/secret
    are shared with the Host, not a separate registered app per hosted service).
  - **Gotcha hit during this slice:** `HostUser` (the SELECT-ONLY cross-schema mapping a hosted app
    uses to read Host fields like `email`/`phone_number`) must be registered on the **same**
    `Base`/`MetaData` as the hosted app's own models, not a separate `DeclarativeBase` — otherwise
    any string-based `ForeignKey("host.users.id")` on your own tables fails to configure at all
    (`NoReferencedTableError`). Safety from Alembic ever trying to *manage* that table instead comes
    from `migrations/env.py`'s `include_object` filter (excluding the `host` schema outright), not
    from keeping it off the shared metadata.

## Slice R8 — Parity 2: Upload + Pipeline + Processing + Logs

- **Infra:** Real Celery worker process, standing up what the monolith's `app/worker.py` only ever
  stubbed (`autostart=false`, no `REDIS_URL` deployed, no task defined). Event Creator's container
  now runs supervisord with two programs — `[program:web]` and `[program:worker]`, both
  `autostart=true` — the worker consuming the same Upstash Redis instance as its broker/backend.
  New GCP Secret Manager secrets: `redis-url-{qa,prod}` (a `rediss://` connection string, treated
  as confidential the same way OAuth client secrets are), granted `secretmanager.secretAccessor` on
  the Cloud Run runtime service account. Cloud Run deploys for this service now also set
  `--timeout=3600`, matching the Host's own long-request-timeout convention — the SSE progress
  stream needs it.
- **Routing:** None new — `/api/v1/upload`, `/processing`, `/logs` etc. are additional paths on the
  existing `event-creator-{qa,prod}` services, already routed by R5/R6.
- **Secrets:** `--set-secrets=REDIS_URL=redis-url-{qa,prod}:latest` alongside the existing
  `JWT_SECRET`/`ENCRYPTION_KEY`/OAuth-client-secret entries. `GEMINI_API_KEY`, `RESEND_API_KEY`,
  and `TWILIO_*` are read as plain (non-Secret-Manager) env vars for now, matching how the monolith
  itself configured them — a future hardening pass could move these into Secret Manager too, same
  as R4 did for `JWT_SECRET`.
- **Interface contract:**
  - A hosted app that needs background/async work runs its **own** Celery worker inside its own
    Cloud Run container (via supervisord, one process per `[program:*]` block) — it does not share
    a worker or a task queue with the Host or any other hosted app. Each app's tasks are named and
    routed independently (`Celery("event_creator", ...)` here), even though the Redis instance
    happens to be reused.
  - A Celery task must only ever receive JSON-serialisable arguments (ids/strings) — never a live
    object like a DB session, an open HTTP client, or an in-memory storage provider, since none of
    those survive the hop to a separate worker process. Reconstruct collaborators fresh inside the
    task from those ids (a persisted config row, `get_settings()`, etc.).
  - An in-memory/ephemeral fallback storage provider (no persistent, cross-process backing store)
    can't be handed to a worker process by reference — its bytes must travel in the task payload
    itself (base64, capped at the same size limit the upload endpoint already enforces) if a hosted
    app wants a resilient fallback that survives the process boundary.
  - SSE/long-lived streaming endpoints need Cloud Run's request timeout raised past the default
    (`--timeout=3600` here) — the default is far too short for a connection meant to stay open for
    the life of a background job.

## Slices R9–R13 — not yet landed

Per `docs/project-status.md`, R8 is the most recently completed slice. R9–R13 exist as WBS docs
under `docs/platform-restructure/WBS/slice-R{9..13}.md` but haven't been implemented — check those
files and `docs/project-status.md` before relying on anything past R8 as current state. Known
deferred items called out by earlier slices that a future slice will resolve:

- `COOKIE_DOMAIN` and full cross-domain SSO cookie scoping — deferred to **R11**.
- Per-schema DB connection identity (`host_app`/`event_creator_app` roles exist but neither app
  actually connects as them yet; both still use the shared admin `DATABASE_URL`) — flagged as a
  deferred hardening item, no slice assigned yet.
- `DATABASE_URL` living as a GitHub Actions secret rather than GCP Secret Manager — candidate for a
  future hardening pass.

---

## How to keep this doc current

When you finish implementing a slice (whether in `organize-me` or a hosted-app repo), add a new
`## Slice R<n> — <name>` section here, in slice order, covering:

- **Infra** — what GCP/Cloud Run/DNS/DB resources were created or changed.
- **Routing** — what changed in the Load Balancer URL map or how a request gets to a service.
- **Secrets** — what a hosted app now needs to read, from where, via what mechanism.
- **Interface contract** — what a hosted app must now do (or must never do) to integrate
  correctly; call out any gotcha a future integrator would otherwise rediscover the hard way.

Keep each section short and actionable — this doc is for someone building the *next* hosted app,
not a full slice history (that's `docs/project-status.md` and the WBS files).
