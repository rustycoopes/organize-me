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
   + JWT-verify helper + app-registry data). Every page's template context must pass the Host's
   `dark_mode` preference (read via the `HostUser` cross-schema mapping — see R7 below) into
   `chrome_base.html`'s `theme_attr()` call, on every route, not just the ones you remember to
   check first — a page that forgets always renders light-only regardless of the user's Host
   Profile setting (see the R7 gotcha and issue #207).
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
  - **Gotcha found in issue #200 (fixed 2026-07-15):** build that redirect_uri from a fixed,
    per-environment setting (e.g. `GOOGLE_DRIVE_REDIRECT_URI`), never from the incoming request's
    Host header (`request.base_url`). Google matches redirect URIs as an exact string, and a
    dynamically-derived value silently tracks whatever domain/service happens to receive the
    request — it only works by coincidence until the next load-balancer or service-boundary
    change (exactly what broke Drive-connect in QA after Storage moved behind the LB in this
    slice). Whenever a hosted app's own domain/routing changes, re-register the exact new
    redirect URI on the OAuth client in Google Cloud Console — this is a manual, outside-repo step
    the code cannot perform or detect.
  - **Gotcha hit during this slice:** `HostUser` (the SELECT-ONLY cross-schema mapping a hosted app
    uses to read Host fields like `email`/`phone_number`) must be registered on the **same**
    `Base`/`MetaData` as the hosted app's own models, not a separate `DeclarativeBase` — otherwise
    any string-based `ForeignKey("host.users.id")` on your own tables fails to configure at all
    (`NoReferencedTableError`). Safety from Alembic ever trying to *manage* that table instead comes
    from `migrations/env.py`'s `include_object` filter (excluding the `host` schema outright), not
    from keeping it off the shared metadata.
  - **Theme sync (fixed in issue #207, not caught until R9/R11 pages had already shipped):**
    `HostUser` also carries `dark_mode` — the Host Profile's light/dark preference — for the exact
    same reason it carries `email`/`phone_number`: it's a Host-owned field a hosted app needs to
    render correctly but never owns or writes. Every page route must call a `get_dark_mode(db,
    user_id)` helper (a thin wrapper over `get_host_user()` that defaults to `False` when the row
    is missing — see `app/services/host_user.py` in `event-creator`) and pass the result as
    `dark_mode` in its template context, the same context key `chrome_base.html`'s `theme_attr()`
    reads. R8/R9's initial page ports (`dashboard.py`, `processing.py`, `prompt.py`, `logs.py`,
    `upload.py`) each hardcoded `"dark_mode": False` instead, deferring the lookup as "out of
    scope" — the Settings > Notifications fragment (this slice) had already wired the identical
    `get_host_user()` call for `email`/`phone_number`, so the fix was reusing an existing, already-
    proven pattern, not building a new one. **Lesson for future hosted-app pages:** any new page
    route that renders the shared chrome needs this wiring from day one; it's easy to ship a page
    that "looks right" in light mode and only surfaces the gap when a user with `dark_mode=true`
    visits it.

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

## Slice R9 — Parity 3: Dashboard + Events + Prompt

- **Infra:** None new — the Dashboard/Events/Prompt surfaces are additional routes on the existing
  `event-creator-{qa,prod}` Cloud Run services, already provisioned by R5/R6.
- **Routing:** None new. `/dashboard` was already routed to `event-creator` since the R6 tracer
  bullet — this slice replaces its placeholder body with the real events table, so the change goes
  live the moment it's deployed. `/prompt` is a genuinely new route added to `event-creator`, but
  the app-registry (`packages/chrome/src/organizeme_chrome/registry.py`) still lists it under the
  Host's own `AppNavItem` list, same as `/upload`/`/processing`/`/logs` since R8 — full-page-route
  cutover for these paths is deliberately deferred to the **R11 QA Cutover** slice, not done
  incrementally per parity slice (unlike R7's Settings-tab fragments, which don't need an LB path
  change since the Host keeps rendering the `/settings` shell and only fetches tab content via
  `hx-get`). Until R11 lands, the Host's own `/prompt` keeps serving live traffic; Event Creator's
  new `/prompt` route exists and is tested but isn't reachable through the shared Load Balancer
  yet.
- **Secrets:** None new.
- **Interface contract:**
  - The `events`, `llm_prompts`, and `user_settings` tables (adopted into `event_creator`'s schema
    since R1/R2) now have their full read/write surface in Event Creator:
    `GET`/`DELETE`/`PATCH /api/v1/events{,/{id}}`, `GET`/`PUT /api/v1/llm-prompt` +
    `POST /api/v1/llm-prompt/reset`. A hosted app reading/writing rows in another app's schema
    (e.g. a future app wanting event data) must go through these endpoints, not direct DB access.
  - The Getting Started onboarding checklist reads `event_creator.user_settings`'s three boolean
    flags (`onboarding_storage_done`, `onboarding_notifications_done`,
    `onboarding_first_upload_done`, all already wired by R2/R7/R8's storage-connect/notification/
    upload write-paths) — no new flag or table was needed for this slice.
  - Re-enabled `e2e/tests/import-pending-files.spec.ts`'s Dashboard-page case (issue #185), skipped
    since R7 exposed that `/dashboard` had routed to Event Creator's placeholder since R6. A hosted
    app that reuses a Host-authored partial (here, the "Import pending files" button) should keep
    its markup (element ids in particular) identical so shared e2e coverage keeps working
    unmodified.
  - The post-login redirect (`GOOGLE_OAUTH_SUCCESS_REDIRECT`/`LOGIN_SUCCESS_REDIRECT` in
    `app/api/v1/auth.py`) still targets `/profile`, not `/dashboard` — the monolith never made this
    switch despite the Dashboard existing since R6. Left as-is here as well: repointing the
    post-login landing page is a user-visible auth-flow change with its own risk, better done as
    its own reviewed follow-up than folded into this slice — see the GitHub issue filed alongside
    this slice's PR.

## Slice R10 — Host↔Event Creator boundary E2E test suite

> Backfilled here after being missed when R10 shipped — see R11's section below for how this gap
> was caught (during R11's own "compare against acceptance criteria" pass).

- **Infra:** None new.
- **Routing:** None new — the boundary suite drives the existing shared QA Load Balancer domain.
- **Secrets:** None new.
- **Interface contract:**
  - New `e2e/tests/host-event-creator-boundary.spec.ts` (organize-me) proves the seams the R6-R9
    split created still hold: logout at the Host clears the cookie Event Creator relies on for
    auth, and Event Creator's JWT trust (`app.core.auth.current_user_id_optional` in the
    event-creator repo) rejects a garbage cookie value and a tampered-signature token. Login-once
    SSO and no-cookie rejection were already covered by `sidebar.spec.ts`; a Host Profile field
    reaching an Event-Creator-owned dependency was already covered by `notifications.spec.ts`.
  - `event-creator`'s own CI gained a new `e2e-boundary-qa` job (checks out organize-me's `main`,
    runs only the boundary spec against live QA after `deploy-qa`) — a hosted app that wants its
    own CI to catch a boundary regression, not just the Host's, can follow this same pattern:
    checkout the Host repo at a fixed ref, run only the specific spec(s) relevant to that app.
  - Account-deletion cascade to an independent microservice's own schema isn't observable over
    HTTP (a stateless JWT-trust boundary never queries the Host's `users` table), so it's asserted
    directly against the schema instead: one DB-level cascade test per `event_creator` table with
    a direct `ON DELETE CASCADE` FK to `host.users` (`test_user_settings_model.py`,
    `test_storage_config_model.py`, `test_llm_prompt_model.py`, `test_event_model.py` in the
    event-creator repo).

## Slice R11 — QA cutover + full verification (P0 gate)

- **Infra:** None new — reuses the `event-creator-{qa,prod}` Cloud Run services and the shared LB
  provisioned by R5/R6.
- **Routing:** The actual cutover. `packages/chrome/src/organizeme_chrome/registry.py`'s
  `event-creator` `AppEntry` gains `/upload`, `/processing`, `/logs`, `/prompt` (moved off the
  Host's own entry), plus the API/fragment `api_prefixes` behind them (`/api/v1/events`,
  `/api/v1/llm-prompt`, `/api/v1/upload`, `/api/v1/import-pending-files`,
  `/api/v1/processing-runs`, the bare `/processing-runs` page-detail prefix, and
  `/api/html/processing-runs` for the log-partial fragment). The QA Load Balancer's URL map was
  regenerated from the updated registry (`uv run python -m infra.gcp_lb.generate_url_map`) and
  re-imported live (`gcloud compute url-maps import organizeme-qa-url-map ...` — the same
  idempotent step `infra/gcp_lb/provision.sh` already performs, re-run standalone rather than the
  whole script since every other resource already existed). The Host's own copies of these
  pages/endpoints are left in place, now simply unreachable through the LB — removing them is
  R13's job, not this one's.
  - **A hosted app that wants its nav paths cut over from the Host must publish this timing
    explicitly**: R7-R9 built full parity for these four pages but deliberately deferred their LB
    routing until this dedicated verification slice, rather than flipping traffic incrementally
    per parity slice (unlike Settings-tab fragments, which never needed an LB change at all — see
    R7's section above). Follow that same pattern for any future hosted-app page migration: build
    and test parity first, cut routing over as its own reviewed, verified step.
- **Secrets:** None new.
- **Interface contract:**
  - `organizeme-chrome` bumped to `chrome-v0.4.0` (registry-only change; both this repo's own pin
    and `event-creator`'s were bumped and redeployed before the live URL-map import, so both
    services render sidebar/Settings-tab chrome from the same registry snapshot the moment
    routing flips).
  - A previously-undetected gap surfaced by this slice's "compare against acceptance criteria"
    pass: Event Creator never got its own `/upload` **page** (only the `POST /api/v1/upload` API,
    ported in R8) — R8's own tests never exercised the page because they only needed the API.
    Backfilled here (`app/pages/upload.py` + `app/templates/pages/upload.html` in the
    event-creator repo, near-verbatim port of the Host's own `app/pages/upload.py`/
    `templates/upload.html`) before cutting `/upload`'s routing over — a lesson for any future
    slice that assumes "the API exists" implies "the page exists": verify both independently
    before routing a nav path to a service.
  - New e2e specs closing the PRD-story-13–52 verification gap that had no prior browser-level
    coverage: `dashboard.spec.ts`, `logs.spec.ts`, `upload.spec.ts` (organize-me `e2e/tests/`).
    All three are routing-agnostic (they assert observable page behaviour, not which backend
    served the request), so they were written and could pass *before* the cutover too — proving
    Host and Event Creator's parity implementations are behaviourally equivalent was exactly the
    point.
  - Event-Creator's own `organizeme-chrome` pin had silently drifted to `chrome-v0.2.0` (missing
    R7's `api_prefixes` field and Settings-tab ownership move) with zero observable effect, purely
    by coincidence: nav *paths* never changed between v0.2.0 and v0.3.0, and the Host's own
    `/settings` shell reads Event Creator's tab list via an explicit `get_app("event-creator")`
    call (`app/pages/settings.py`), never through Event Creator's own (stale) `register_chrome`
    global. Fixed alongside the R11 pin bump. **Lesson for future slices:** a hosted app's own
    chrome pin can go stale without any CI or runtime signal if nothing it renders happens to
    depend on the changed fields — don't assume "no visible bug" means "the pin is current."

### R11 redesign — Celery/Redis replaced with Cloud Tasks (post-cutover fix)

R11's live cutover surfaced a blocker documented in full in
`docs/adr/0001-event-creator-worker-cpu-throttling.md`: the R8 Celery worker crash-loops under
Cloud Run's request-based CPU throttling (a separate always-on process has no HTTP request of its
own to justify CPU allocation). Resolved by replacing Celery/Redis with Cloud Tasks push-based
dispatch — this is a redesign within R11, not a new numbered slice.

- **Infra:** New Cloud Tasks queues, `event-creator-pipeline-{qa,prod}`
  (`max-concurrent-dispatches=1`, `max-attempts=3`), provisioned via `event-creator`'s
  `infra/cloud_tasks/provision.{sh,ps1}` (mirrors `infra/gcp_lb/provision.sh`'s idempotent,
  manual-operator-run pattern). The Celery worker process is gone entirely — `event-creator`'s
  `supervisord`/two-program container from R8 reverted to a single plain `uvicorn` process
  (`app.worker`, `supervisord.conf` removed). QA's `--no-cpu-throttling` experiment (the ADR's
  short-term validation) is reverted; both QA and prod stay on request-based billing throughout.
- **Routing:** New internal endpoint `POST /internal/pipeline/run` on the existing
  `event-creator-{qa,prod}` services — not part of the app-registry/Load-Balancer routing (it's
  never reached via the shared LB; Cloud Tasks pushes directly to the service's own
  `https://*.run.app` URL, bypassing the LB).
- **Secrets:** `redis-url-{qa,prod}` no longer read (Redis/Upstash dependency removed). New
  plaintext (non-Secret-Manager) env vars: `GCP_PROJECT_ID`, `CLOUD_TASKS_LOCATION`,
  `CLOUD_TASKS_QUEUE`, `PIPELINE_INVOKER_SERVICE_ACCOUNT`, `PIPELINE_ENDPOINT_URL` (the last one
  self-referential — captured from `gcloud run services describe` in a follow-up deploy step,
  since a service can't know its own URL before its first deploy). See
  `secrets-and-accounts.md`'s Cloud Tasks entry for the IAM grants.
- **Interface contract:**
  - A hosted app that needs background/async work on Cloud Run **without** moving to
    instance-based billing should push each unit of work back to itself as a genuine HTTP request
    (Cloud Tasks push target with OIDC verification), not a separate always-on worker process —
    Cloud Run's CPU throttling model only allocates CPU to a request it's actively handling, so
    detached background work (a Celery worker *or* a plain `asyncio.create_task()`) needs
    `--no-cpu-throttling` either way. This was a real design-review correction: the initial
    instinct (revert to the monolith's in-process asyncio) turned out to need the same
    CPU-always-allocated flag the monolith itself required (see the ADR's Resolution section) —
    it doesn't actually avoid the cost problem.
  - The push endpoint must self-verify the Cloud-Tasks-presented OIDC token in code (`aud` +
    `email` claims against expected values) rather than relying on Cloud Run's own IAM gate, since
    the service as a whole stays `--allow-unauthenticated` for its normal user-facing routes.
  - The push handler must be idempotent (check the target resource isn't already in a terminal
    state before processing) — Cloud Tasks retries are a real possibility (lost response, queue
    retry policy), and a task queue offers no exactly-once guarantee.
  - "Sequential, not concurrent" batch processing (the same requirement R8's Celery `chain` met)
    is **not** guaranteed by a queue's `max-concurrent-dispatches=1` setting alone — that only
    bounds concurrency, not dispatch *order* (Cloud Tasks documents order as best-effort by
    schedule time, and a retry on an earlier item can let a later item's task become eligible
    first). A code-review pass caught this before it shipped: strict ordering is met by explicit
    chaining instead — only the batch's first item is enqueued directly; each payload carries the
    rest of the batch, and the push endpoint enqueues the next item itself once the current one
    finishes (including on a retried/already-terminal redelivery, so the chain can resume even if
    an earlier attempt died between finishing its item and advancing the chain).

## Slice R12 — Production cutover (done)

- **Infra:** Production External HTTPS Load Balancer fronting `organizeme.russcoopersoftware.com`
  provisioned via `infra/gcp_lb/provision-prod.{sh,ps1}` — same shape as R5's QA setup, every
  resource suffixed `-prod` instead of `-qa` (GCP global resource names can't be shared across
  environments): two static IPs, Cloud DNS A/AAAA records, a Google-managed cert
  (`organizeme-prod-cert`), Serverless NEGs against `organizeme-prod`/`event-creator-prod`, three
  backend services (`host-backend-prod`, `organizeme-backend-prod`, `event-creator-backend-prod`),
  a URL map, an HTTPS proxy, and forwarding rules. `infra/gcp_lb/generate_url_map.py` gained an
  optional environment argument (`... generate_url_map prod`) to rename every backend consistently.
- **Already-satisfied prerequisites, confirmed via read-only `gcloud` checks rather than re-done:**
  the prod Cloud Tasks queue (`event-creator-pipeline-prod`) already existed and is `RUNNING`; both
  prod services are already on request-based billing (`run.googleapis.com/cpu-throttling: true`, no
  `min-instances`); `E2E_TEST_MODE` is unset on both. The `host`/`event_creator` prod schema
  separation is presumed already applied too, since `deploy.yml` runs the Alembic migration on
  every prod deploy and prod has deployed successfully many times since R1 landed — a failing
  migration would have failed those deploys.
- **Cutover completed:** the managed cert went `ACTIVE` (faster than the ~24h estimate); routing
  verified directly against the LB IP with the prod Host header (`/login` → Host backend `200`,
  `/dashboard` → Event Creator backend `302`, the expected unauthenticated redirect). The user
  registered the new redirect URIs on the Google OAuth client in Cloud Console and confirmed
  `google-oauth-client-secret-prod` matches the real client secret (the same class of bug found in
  issue #203 for QA). `GOOGLE_OAUTH_REDIRECT_URI`/`GOOGLE_DRIVE_REDIRECT_URI` flipped to the LB
  domain in `organize-me`'s `deploy.yml`; `event-creator`'s prod `GOOGLE_DRIVE_REDIRECT_URI` was
  already pointed there (set proactively during #200, since event-creator-prod wasn't yet receiving
  real traffic), so no change was needed there.
- **Post-cutover smoke tests surfaced two live bugs, both fixed (neither an R12 regression — both
  were latent, first exercised by this cutover's real-upload test):**
  - **Stale Google Drive OAuth token in prod.** `event-creator-prod` failed every upload/import
    with a Fernet `InvalidSignature` decrypting the stored `oauth_access_token` — it had been
    encrypted before `ENCRYPTION_KEY` moved to GCP Secret Manager, under a different key value than
    what's there now. Fixed by reconnecting Google Drive in prod Settings (re-encrypts under the
    current key); no code change. Any other prod user who connected Drive before that Secret Manager
    migration and hasn't uploaded since would hit the same error — flagged as issue #206 for a
    deliberate audit decision.
  - **Missing `GEMINI_API_KEY` in `event-creator`.** R11 moved the Gemini-calling pipeline here, but
    the key was only ever wired into `organize-me`'s `ci.yml`/`deploy.yml` — invisible to CI since
    tests mock the Gemini client. Fixed in `event-creator` PR #14
    (`fix/wire-gemini-api-key`): added the GitHub secret and wired it into both QA and prod Cloud
    Run env.
- Real login (existing data confirmed intact) and a real upload (pipeline ran to completion) both
  verified working end-to-end in prod after both fixes.

## Slice R13 — Host Cleanup + "How to Add a Hosted App" Playbook

- **Infra:** None new. The Host's Celery worker process definition (`[program:worker]` in
  `supervisord.conf`, always `autostart=false` and never wired to real `REDIS_URL`/tasks since
  the R11-redesign moved that architecture to Cloud Tasks in `event-creator` instead) was removed
  — the Host's container now runs a single `uvicorn` process.
- **Routing:** None. The Host's own app-registry entry (`packages/chrome/src/organizeme_chrome/
  registry.py`'s `"organizeme"` `AppEntry`) already only listed `/settings` and `/profile` — the
  Dashboard/Upload/Processing/Logs/Prompt nav items had already moved to the `event-creator`
  entry back in R11, so no registry/URL-map change was needed for this slice.
- **Secrets:** None new.
- **Interface contract / what changed:**
  - Removed the Host's now-dead event-extraction code entirely: the page modules, API routers,
    `app/services/{pipeline,llm,storage}/` (whole dirs), the pipeline-only parts of
    `app/services/notifications/` (kept `email.py` — still used for the Host's own
    password-reset emails), `app/core/{prompts,date_parser,calendar_url,message_filter,
    onboarding}.py`, `app/worker.py`, their SQLAlchemy models (`Event`, `LLMPrompt`,
    `ProcessingRun`, `ProcessingStep`, `StorageConfig`, `UserSettings`), their Pydantic schemas,
    and their Jinja templates. `app/api/v1/users.py`'s `UserRead`/`UserUpdate` also dropped
    `notification_email`/`notification_sms` — those fields read/wrote
    `event_creator.user_settings` (moved there in R2, and R7 already migrated the Settings UI for
    them to event-creator), so exposing them on the Host's own `/api/v1/users` was leftover
    surface with no remaining owner-side purpose once the model was removed.
  - `app/pages/app_shell.py`'s placeholder-page logic no longer needs to special-case
    Dashboard/Upload/Processing/Logs/Prompt paths (`PAGES_WITH_OWN_ROUTER` shrank to
    `{"/profile", "/settings"}`) — those paths were never in the Host's own registry nav to begin
    with, so this was pure code cleanup, not a behavior change.
  - Wrote [`how-to-add-a-hosted-app.md`](how-to-add-a-hosted-app.md), the condensed forward-looking
    playbook for app #3+, validated against `event-creator`'s real registry entry, `jwt_verify`
    usage, and `organizeme-chrome` pin.
  - **Interface contract for future slices:** removing a hosted app's leftover code from the Host
    is purely additive-safe cleanup as long as (a) the app-registry's nav for that app already
    points entirely at the other service (true here since R11), and (b) any Host-owned code that
    happens to import the app's models/schemas (found here: `app/api/v1/users.py` reading
    `UserSettings` for notification prefs) gets explicitly untangled first, not just deleted
    alongside — grep for cross-imports before assuming a module is exclusively
    event-extraction's.
  - Deferred items still open after this slice (unchanged by it, listed here for continuity):
    `COOKIE_DOMAIN`/full cross-domain SSO cookie scoping (still not needed — both services share
    a hostname via the LB); per-schema DB connection identity (`host_app`/`event_creator_app`
    roles unused, both apps still connect as the shared admin `DATABASE_URL`); `DATABASE_URL` as a
    GitHub Actions secret rather than Secret Manager; the post-login redirect target (`/profile`,
    not `/dashboard` — issue #189, still unresolved, out of scope for this slice since it's a
    user-visible auth-flow change); the hardcoded QA LB domain duplicated across both repos' CI
    configs (issue #191).

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
