# OrganizeMe — Changelog

> This is the single source of truth for "what shipped." As of 2026-07-16, new entries are
> **one line per merged issue**, linking to where the full detail actually lives:
> - For a feature built via the `docs/features/<feature-slug>/` workflow (or the legacy
>   `docs/features/platform-restructure/`), link to that slice's WBS file — `/to-implementation` appends a
>   **Delivered** section there (issue #, branch, outcome) when the work lands.
> - For a small change filed straight to a GitHub issue with no WBS slice, link to the issue/PR
>   itself.
>
> Example: `- 2026-07-16 — #168 Slice R13: Host Cleanup + Hosted-App Playbook — [details](platform-restructure/WBS/slice-R13.md)`
>
> `docs/project-status.md` has been removed — this index plus each WBS slice's own status *is* the
> project-status view now. Entries written before this policy took effect remain in their original
> long form below (and in [`changelog-archive.md`](changelog-archive.md)); only new entries follow
> the one-liner format.

---

## [Unreleased]

### Added
- 2026-07-16 — #212 Slice 1: Grouped, collapsible sidebar in organize-me (Host) — [details](features/sidebar-nav-groups/WBS/slice-1-host-sidebar-groups.md)
- 2026-07-16 — event-creator#18/#19 Slices 2+3: event-creator reads the Host's real per-user sidebar-group collapse state on every page — [details](features/sidebar-nav-groups/WBS/slice-2-event-creator-sync-pattern.md)
- 2026-07-18 — #218 Registry decoupling Slice 1: Host endpoint + `organizeme_chrome` client machinery + event-creator migration — [details](features/registry-decoupling/WBS/slice-1-host-endpoint-and-event-creator-migration.md)
- **Issue #168 — Slice R13: Host Cleanup + "How to Add a Hosted App" Playbook.** Removed the
  Host's now-dead event-extraction code now that `event-creator` fully owns it (stable in prod
  since R12): the page modules (`app/pages/{dashboard,upload,processing,logs,prompt}.py`), API
  routers (`app/api/v1/{upload,events,llm_prompt,processing_runs,storage_config,
  storage_google_drive,storage_dropbox,import_pending_files}.py`), `app/services/{pipeline,llm,
  storage}/` (whole dirs), the pipeline-only parts of `app/services/notifications/` (kept
  `email.py` — the Host's own password-reset emails still use it), `app/core/{prompts,
  date_parser,calendar_url,message_filter,onboarding}.py`, `app/worker.py` (a Celery stub that
  was never wired up — real background processing moved to `event-creator`'s Cloud Tasks design
  in R11), their SQLAlchemy models/Pydantic schemas, and their Jinja templates. Also stripped
  `notification_email`/`notification_sms` off `app/api/v1/users.py`'s `UserRead`/`UserUpdate` —
  those fields read/wrote the now-removed `event_creator.user_settings` model, and R7 had already
  moved the Notifications Settings tab's UI to `event-creator`, so this was dead surface on the
  Host's own `/api/v1/users` endpoint. 63 files deleted from `app/`, 34 Python test files + 8
  Playwright specs deleted from `tests/`/`e2e/tests/` (equivalent coverage already verified in
  `event-creator`'s own suites). `notifications.spec.ts` was found during review to have been
  missed from #168's original migration list — it's architecturally identical to
  `storage.spec.ts`/`prompt.spec.ts` (a Host-rendered settings-tab whose actual content/data is
  entirely event-creator-owned); ported it to `event-creator` (PR #17) and deleted it here too.
  Plus one Host-only DB-schema regression test
  (`test_host_users_no_longer_has_moved_columns`) moved from the deleted
  `test_user_settings_model.py` into `tests/test_schema_separation.py`, its natural home. Wrote
  [`docs/how-to-add-a-hosted-app.md`](how-to-add-a-hosted-app.md),
  the condensed playbook for a future app #3, validated against `event-creator`'s real
  app-registry entry, `organizeme_chrome.jwt_verify` usage, and LB URL-map regeneration. Updated
  README/technical-approach to describe the Host-only surface (auth/profile/settings-shell/
  nav-shell) and added this slice's section to `docs/host-integration-guide.md`.

  A code-review pass caught dead code the mechanical deletion sweep missed — nothing mypy/pytest
  could catch since it was still syntactically valid, just orphaned: `app/core/security.py`
  (`CredentialCipher`) + `tests/test_security.py` (its only caller, `storage_config.py`, was
  already gone), `app/auth/oauth.py::get_dropbox_oauth_client()` (Dropbox's OAuth client
  constructor — same story), and the `Settings` fields only those dead functions read
  (`encryption_key`, `google_drive_redirect_uri`, `dropbox_oauth_client_id/secret`,
  `gemini_api_key`, `twilio_account_sid/auth_token/phone_number`, `base_url`). Removing them
  exposed `celery[redis]`, `twilio`, `google-genai`, `boto3`, and `sse-starlette` as unused
  dependencies too (zero remaining imports) — pruned from `pyproject.toml`, `uv.lock`
  regenerated, and `ci.yml`/`deploy.yml`/`.env.local.example` trimmed of the env vars/secrets
  that only ever fed this dead code. `uv run mypy app tests` (52 files) and
  `uv run pytest --collect-only` (141 tests) clean after the full sweep. Branch
  `restructure/r13-host-cleanup`.
- **Issue #167 (done) — Slice R12: Production Cutover.** Post-cutover smoke testing (real login,
  real upload) surfaced two live bugs the routing/redirect_uri work couldn't catch on its own,
  both now fixed:
  - **Stale Google Drive OAuth token.** `event-creator-prod` failed every upload/import with a
    Fernet `InvalidSignature` decrypting the stored `oauth_access_token` — the token had been
    encrypted before `ENCRYPTION_KEY` moved to GCP Secret Manager, under a different key value than
    what's there now. Not an R12 regression — this was already broken for any real Drive-connected
    upload in prod, it just hadn't been exercised until this smoke test. Fixed by reconnecting
    Google Drive in prod Settings, which re-encrypts the token under the current key; no code
    change needed.
  - **Missing `GEMINI_API_KEY` in event-creator.** R11 moved the Gemini-calling pipeline
    (upload/import-pending-files) to `event-creator`, but `GEMINI_API_KEY` was only ever wired into
    `organize-me`'s `ci.yml`/`deploy.yml` — invisible to CI since tests mock the Gemini client.
    Failed live as `Gemini call failed: GEMINI_API_KEY is not set`. Fixed in
    `event-creator` PR #14 (branch `fix/wire-gemini-api-key`): added the GitHub secret and wired it
    into both QA and prod Cloud Run env, same plaintext-env-var pattern as the other non-confidential
    config already there.

  Full R12 history below (LB provisioning, then the redirect_uri flip):
- **Issue #167 — Slice R12: Production Cutover, LB provisioning step.** Provisioned
  the production External HTTPS Load Balancer fronting `organizeme.russcoopersoftware.com`,
  mirroring R5's QA setup: two static IPs, Cloud DNS A/AAAA records, a Google-managed SSL cert
  (`organizeme-prod-cert`, provisioning — can take up to ~24h to validate), Serverless NEGs against
  `organizeme-prod`/`event-creator-prod`, three backend services (`host-backend-prod`,
  `organizeme-backend-prod`, `event-creator-backend-prod`), a URL map generated from the R3
  app-registry, an HTTPS proxy, and forwarding rules. New scripts
  `infra/gcp_lb/provision-prod.{sh,ps1}` (idempotent, mirror `provision.sh`/`provision.ps1`).
  `infra/gcp_lb/generate_url_map.py` gained an optional environment argument
  (`... generate_url_map prod`) that renames every backend service consistently
  (`host-backend-prod`, etc.) so prod's URL map doesn't collide with QA's identically-named global
  resources; omitting the argument keeps the original QA behavior unchanged. This step is
  deliberately non-disruptive: `organizeme.russcoopersoftware.com` is a brand-new hostname nothing
  currently points at (prod is reached today via the raw Cloud Run URLs), so no existing traffic is
  affected until `GOOGLE_OAUTH_REDIRECT_URI`/`GOOGLE_DRIVE_REDIRECT_URI` are deliberately flipped to
  it in a follow-up PR — pending the cert going `ACTIVE` and the new redirect URIs being registered
  on the Google OAuth client in Cloud Console (manual, outside-repo step). Branch
  `restructure/r12-prod-cutover`.
- **Issue #167 — Slice R12: prod redirect_uri cutover.** The LB cert went `ACTIVE`
  faster than the ~24h estimate and routing was verified (`/login` → Host, `/dashboard` →
  Event Creator, both via the LB IP with the prod Host header). User registered the new redirect
  URIs on the Google OAuth client in Cloud Console and confirmed `google-oauth-client-secret-prod`
  matches the real client secret. Flipped `GOOGLE_OAUTH_REDIRECT_URI`/`GOOGLE_DRIVE_REDIRECT_URI` in
  `deploy.yml` from the raw Cloud Run URL to `https://organizeme.russcoopersoftware.com/...` —
  `event-creator`'s prod `GOOGLE_DRIVE_REDIRECT_URI` already pointed at the LB domain (set
  proactively during #200, since event-creator-prod wasn't yet receiving real traffic), so no
  change was needed there. Branch `restructure/r12-flip-prod-redirect-uris`.

### Fixed
- **Issue #200 — Google Drive connect failed with `Error 400: redirect_uri_mismatch`.** Both the
  Host's (this repo) and event-creator's copies of the Google Drive OAuth connect flow
  (`storage_google_drive.py`) built the callback `redirect_uri` dynamically from the incoming
  request's Host header (`request.base_url`), rather than from a fixed setting - the same
  reasoning already fixed for *login* OAuth back when the R5 load-balancer cutover moved QA to
  `organizeme.qa.russcoopersoftware.com` (see the `da9515b` fix). The Drive-connect flow's own
  redirect URI silently followed suit, but the LB-domain variant of that URI was never registered
  on the Google OAuth client, and Google rejects any redirect_uri that isn't an exact match. Fixed
  by adding a `GOOGLE_DRIVE_REDIRECT_URI` setting (env var already documented in
  `.env.local.example` but never wired to `app/core/config.py` until now) and building the
  authorization/token-exchange calls from it instead of the request. Prod's value stays pinned to
  the already-registered raw Cloud Run URL (R12, the production cutover to the LB domain, hasn't
  landed yet); QA's and event-creator's values point at the LB domain, which needs the matching
  redirect URI added to the Google Cloud Console OAuth client (a manual, outside-repo step - see
  the host-integration-guide). Branch `fix/google-drive-oauth-redirect-uri-parity`
  (event-creator: `fix/google-drive-oauth-redirect-uri`).
- **Issue #203 — Google Drive connect still failed after #200, with a generic "connection
  failed" banner.** The OAuth callback (`event-creator`'s `storage_google_drive.py`) had several
  distinct silent-failure branches collapsed into one banner, making the real cause invisible
  without a production debugging round-trip. Added a `logger.warning(...)` to each branch
  (Google-returned error, missing code/state, state-JWT decode failure, CSRF mismatch, and
  `GetAccessTokenError` from the token exchange) - no secrets or attacker-controlled values logged.
  Deployed to QA and used to capture the real failure: Google's token endpoint returned `401
  Unauthorized` during the code exchange - a client-credential rejection, not a redirect_uri
  problem. Root cause: `event-creator-qa`'s `GOOGLE_OAUTH_CLIENT_SECRET` is sourced from GCP Secret
  Manager (`google-oauth-client-secret-qa`), and the value stored there did not match the real
  Google OAuth client secret - `organizeme-qa`'s plaintext copy of the same secret was correct.
  Fixed by adding a new Secret Manager version with the correct value and forcing a new Cloud Run
  revision (secret refs are resolved at container startup, not per-request, so the fix didn't take
  effect until a fresh revision rolled out). No application code change was required for the actual
  fix - only the diagnostic logging (branch `fix/drive-callback-diagnostic-logging`, event-creator
  PR #13) plus the infra-level secret correction. `event-creator-prod` has the identical
  structural risk (separate Secret Manager secret from `organizeme-prod`'s known-good value,
  unverified) - flagged in the host-integration-guide as a pre-R12 checklist item.

### Changed
- **ADR-0001 resolved — Event Creator's Celery/Redis pipeline dispatch replaced with Cloud
  Tasks.** R11's live cutover surfaced the Celery worker crash-looping under Cloud Run's
  request-based CPU throttling (a separate always-on process has no HTTP request of its own to
  justify CPU allocation — see `docs/adr/0001-event-creator-worker-cpu-throttling.md`). The
  obvious fix (`--no-cpu-throttling`) trades into instance-based billing, which the user has hit
  ~$70/month on before and wants to avoid. Design review initially favored reverting to the
  monolith's in-process `asyncio.create_task()` approach, but that turned out to need the same
  CPU-always-allocated flag the monolith itself required — it doesn't actually solve the cost
  problem, just relocates it. Replaced Celery/Redis entirely with Cloud Tasks push-based
  dispatch instead (in the `event-creator` repo): `POST /api/v1/upload` and
  `/api/v1/import-pending-files` now enqueue a Cloud Tasks task targeting a new, OIDC-verified
  `POST /internal/pipeline/run` endpoint on the same service, so each pipeline run is a genuine
  inbound HTTP request and Cloud Run allocates CPU for exactly its duration — true pay-per-run
  under request-based billing (Cloud Tasks' own cost is negligible: 1M free operations/month).
  `app/worker.py` (Celery) removed, replaced by `app/services/pipeline/dispatch.py`;
  `supervisord`/the two-program container reverted to a single `uvicorn` process; new
  `infra/cloud_tasks/provision.{sh,ps1}` queue-provisioning scripts. QA's `--no-cpu-throttling`
  experiment reverted — both QA and prod stay on request-based billing. Full writeup in the ADR's
  Resolution section and `docs/host-integration-guide.md`'s new R11-redesign
  subsection.

### Added
- **Issue #166 implemented — Slice R11: QA Cutover + Full Verification (P0 Gate).** The routing
  cutover the R6-R9 parity slices deferred: `packages/chrome/src/organizeme_chrome/registry.py`'s
  `event-creator` entry gains `/upload`, `/processing`, `/logs`, `/prompt` and their API/fragment
  `api_prefixes` (moved off the Host's own entry); the QA Load Balancer's URL map was regenerated
  from the updated registry and re-imported live. The Host's own copies of these pages/endpoints
  are left in place, now simply unreachable — removal is R13's job. Two previously-undetected gaps
  surfaced during this slice's "compare against acceptance criteria" pass, both fixed before
  cutover: Event Creator never got an `/upload` **page** (only the `POST /api/v1/upload` API,
  ported in R8 — R8's own tests only needed the API, so the missing page went unnoticed until R11
  tried to route real browser traffic at it); and Event Creator's own `organizeme-chrome` pin had
  silently drifted to `chrome-v0.2.0` (two versions stale) with zero observed effect, purely by
  coincidence — see `docs/host-integration-guide.md`'s R11 section for the
  full explanation. `organizeme-chrome` bumped to `chrome-v0.4.0`; both this repo's and
  `event-creator`'s pins updated. Closed the PRD-story-13–52 e2e coverage gap (upload, the events
  dashboard, and processing-history logs previously had no browser-level tests) with three new
  specs — `dashboard.spec.ts`, `logs.spec.ts`, `upload.spec.ts` — all deliberately routing-agnostic
  (asserting observable page behaviour, not which backend served the request), so they pass
  whether Host or Event Creator answers, proving behavioural parity was the point. Independent-
  deploy proof: already naturally demonstrated by R6-R10's git/CI history (each repo deployed
  repeatedly without touching the other's build).
- **Issue #165 implemented — Slice R10: Host↔Event Creator Boundary E2E Test Suite.** New
  `e2e/tests/host-event-creator-boundary.spec.ts` proves the seams the platform split created
  still hold: logout at the Host clears the cookie Event Creator relies on for auth, and Event
  Creator's JWT trust rejects a garbage cookie value and a tampered-signature token (forged with a
  throwaway secret via new `e2e/utils/jwt.ts` — never touches the real signing key). Login-once
  SSO and no-cookie rejection were already covered by `sidebar.spec.ts`; the Host-Profile-field →
  Event-Creator-dependency criterion was already covered by `notifications.spec.ts` — documented
  in the new spec rather than duplicated. `event-creator`'s own CI gained a new `e2e-boundary-qa`
  job running this same spec against live QA after `deploy-qa`. Account-deletion cascade to Event
  Creator's own schema was asserted directly at the DB level (a cascade test per `event_creator`
  table with a direct FK to `host.users`), since it isn't observable over Event Creator's
  stateless JWT trust boundary (it never queries the Host's `users` table at all).
- **Issue #164 implemented — Slice R9: Parity 3 (Dashboard + Events + Prompt).** Completes
  functional parity: the events dashboard (type/date-range/free-text filters, sort toggle,
  pagination, per-event Google Calendar/Tasks quick-add links, delete-with-confirm, a reviewed
  toggle, and the three-step Getting Started onboarding checklist) and the Prompt page
  (view/edit/reset, lazily seeding the factory-default extraction prompt) move from the monolith
  into `event-creator` (branch `restructure/r9-parity3-dashboard`), replacing the R6 tracer
  bullet's placeholder `/dashboard` body. Ported near-verbatim: `app/core/calendar_url.py`
  (Google Calendar's `render?action=TEMPLATE` convention; Tasks has no documented URL scheme, so
  that link is best-effort), `app/core/onboarding.py`, `app/core/initials.py` (agreed-by initials
  chips), the `events`/`llm-prompt` API routers, and both page templates — adapted to this repo's
  Host-JWT auth (`app.core.auth.current_user_id[_optional]`) instead of a fastapi-users
  `current_active_user` rewrite. The onboarding checklist reads the R2 `event_creator.
  user_settings` flags that R7/R8's storage-connect/notification/upload write-paths already flip —
  no new column needed. Also wired the "Import pending files" button onto the real Dashboard (its
  API endpoint has existed since R8 with no UI entry point until now) and re-enabled
  `e2e/tests/import-pending-files.spec.ts`'s Dashboard-page case (issue #185), skipped since R7
  exposed that `/dashboard` had routed to Event Creator since R6 with no real button to click.
  `/prompt` is a genuinely new Event Creator route, but unlike `/dashboard`'s R6 tracer-bullet
  cutover, its Load-Balancer app-registry entry stays under the Host for now — full-page-route
  cutover for `/prompt`/`/upload`/`/processing`/`/logs` is deliberately deferred to the **R11 QA
  Cutover** slice, so the Host's own `/prompt` keeps serving live traffic until then. The
  monolith's post-login redirect still hardcodes `/profile` rather than `/dashboard` — a
  pre-existing gap the WBS flagged, not something this slice introduced; left as its own follow-up
  (filed as a GitHub issue) rather than folded in here, since repointing it is a user-visible
  auth-flow change with its own risk profile. `mypy --strict` clean across the full repo.
- **Issue #163 implemented — Slice R8: Parity 2 (Upload + Pipeline + Processing + Logs).**
  Migrates the heaviest feature area — file intake, the 7-step extraction pipeline, live SSE
  progress, processing history/logs, and notification dispatch — from the monolith into
  `event-creator` (branch `restructure/r8-parity2-pipeline`). Includes standing up a **real**
  Celery worker: the monolith's own `app/worker.py` was a never-deployed stub
  (`[program:worker]` `autostart=false`, no `REDIS_URL`, no task defined — the pipeline actually
  ran as a plain in-process asyncio background task). Event Creator now runs the pipeline as an
  actual Celery task: new `app/worker.py` (`Celery("event_creator", broker=REDIS_URL, ...)`) is a
  thin async-to-sync bridge whose task takes only JSON-serialisable arguments — never a live
  `StorageProvider`/DB session, which can't survive the Redis-brokered hop to a separate worker
  process — and reconstructs its collaborators inside the task. Three storage-reconstruction
  modes: `"configured"` rebuilds the real Drive/Dropbox/S3 provider from the user's persisted
  `storage_configs` row and downloads by remote file id; `"ephemeral"`/`"fake"` (no persistent,
  cross-process-durable backing store) carry the file's bytes base64-encoded directly in the task
  payload (capped at the same 10 MB the upload endpoint already enforces) and re-seed a fresh
  in-memory provider. `CeleryPipelineScheduler` (`app/api/v1/upload.py`) replaces the monolith's
  `BackgroundPipelineScheduler`; `import_pending_files.py`'s batch dispatches via a Celery `chain`
  to preserve the monolith's "sequential, not parallel" per-file guarantee. New GCP Secret Manager
  secrets `redis-url-{qa,prod}` (an Upstash `rediss://` URL), IAM-granted `secretAccessor` to the
  Cloud Run runtime service account, wired via `--set-secrets` alongside the existing
  `JWT_SECRET`/`ENCRYPTION_KEY`/OAuth-client-secret entries; `--timeout=3600` added to both
  `gcloud run deploy` commands for the long-lived SSE connection. `supervisord.conf` (new to this
  repo) runs `[program:web]` and `[program:worker]`, both `autostart=true`; the `Dockerfile` now
  installs and invokes supervisord instead of plain uvicorn. `app/services/pipeline/{runner,
  progress}.py`, the Gemini client/message-filter/date-parser core, and the notification sender
  (rewired to read this repo's own R7 `user_settings`/`HostUser` instead of the monolith's
  `User`/settings) are near-verbatim ports, independently unit/integration tested with
  `FakeStorageProvider`/`FakeGeminiClient`/`FakeNotificationSender` mirroring the monolith's own
  test pattern — LLM-failure (fail immediately, no retry, file → `failed/`, failure notification)
  and zero-new-events (success, file → `processed/`, "0 new events" notification) paths verified
  at parity. `mypy --strict` clean across the full repo (98 source files). Backfilled the
  previously-missing Slice R7 section in `docs/host-integration-guide.md`
  (the doc had gone stale, still claiming "R7–R13 not yet landed" after R7 had already merged)
  alongside the new R8 section.
- **Issue #162 implemented — Slice R7: Parity 1 (Storage + Settings Tabs).** Migrates
  storage-connection (Google Drive / Dropbox / S3) and the Settings tab content (Storage /
  Notifications / Preferences) from the monolith into `event-creator` (branch
  `restructure/r7-parity1-event-creator`, PR #3), with the Host (branch
  `restructure/r7-parity1-host`, PR #184) rendering only the Settings-page shell chrome and
  fetching each tab's content via `hx-get` fragments. Preferences is a stub tab (no functionality
  ever existed for it in the monolith); S3 stays a "coming soon" stub (matches the monolith's own
  never-built write endpoint); Dropbox gets a full Connect/Disconnect UI that the monolith's
  backend always had but never wired up. The full `StorageProvider` runtime (base/factory/
  google_drive/dropbox/s3/ephemeral/fake) was ported in this slice, ahead of anything calling it.
  `AppEntry` gained an `api_prefixes: list[str]` field so the LB's URL-map generator can route an
  app's own `/api/v1/*` surface, not just its nav pages (closes #178); `organizeme-chrome` bumped
  to `chrome-v0.3.0`. The QA Load Balancer's URL map was re-provisioned to pick up the new routes.
  Several bugs were caught and fixed along the way: the GCP URL-map `/*` wildcard doesn't match
  the bare prefix path (both are now emitted); htmx only swaps 2xx responses, so the "please log
  back in" fragment moved from 401 to 200; `HostUser` needs to share Alembic's `target_metadata`
  (via an `include_object` filter) for FK resolution rather than a separate `DeclarativeBase`;
  `AppNavItem`/`SettingsTab`/`AppEntry` converted from `NamedTuple` to frozen dataclasses to fix a
  shared-mutable-default bug on `api_prefixes`; `event-creator`'s test suite was missing
  `COOKIE_SECURE=false` in `tests/conftest.py` (present in the Host's own conftest, missed on
  port), so Secure-flagged CSRF cookies were never resent by httpx's cookie jar in tests; and
  `e2e/playwright.config.ts`/`ci.yml` pointed E2E at the Host's bare Cloud Run URL instead of the
  shared LB domain, so relative `hx-get` fragments never reached `event-creator` at all in CI.
  Deferred: #183 (live verification of the URL-map wildcard fix) and #185 (Dashboard's "Import
  pending files" e2e test, skipped until R9 gives `event-creator`'s Dashboard real content — it
  predates R6 and was silently broken since then).
- **Issue #161 implemented — Slice R6: Event Creator Scaffold + SSO-Trust Tracer Bullet.**
  Stands up the platform's second Cloud Run service in its own new repo,
  [`rustycoopes/event-creator`](https://github.com/rustycoopes/event-creator), proving the
  Host↔Event Creator trust boundary end-to-end: `GET /dashboard` verifies the Host-issued JWT
  (`organizeme_chrome.jwt_verify`, HS256, shared `JWT_SECRET`) from the `organizeme_auth` cookie
  and renders the shared chrome + a placeholder Dashboard body, with **no** call back to the Host
  and no login/session code of its own. Three prerequisite gaps in the Host repo were closed as
  part of this slice (branch `restructure/r6-host-prereqs`, PR #180): the app-registry
  (`organizeme_chrome.registry`) now has a dedicated `event-creator` `AppEntry` owning
  `/dashboard`, `register_chrome()` merges `nav_items` across **all** registered apps (not just
  the caller's own) so every service still renders the identical unified sidebar, and
  `infra/gcp_lb/provision.sh`/`.ps1` gained a third backend service (`event-creator-backend`) wired
  to a new Serverless NEG — turning the LB URL map's `/dashboard` rule from `organizeme-backend`
  over to Event Creator's own service. Event Creator owns the `event_creator` Postgres schema
  (tables already moved there by the Host's R1 migration) with its own independent Alembic history
  (`event_creator.alembic_version`), adopted via a deliberate no-op baseline migration. Both repos'
  `JWT_SECRET` and `ENCRYPTION_KEY` now come from the same GCP Secret Manager secrets
  (`jwt-secret-{qa,prod}` / `encryption-key-{qa,prod}`) via `--set-secrets`, read independently by
  each service with zero network call between them — documented in full, with a mermaid diagram of
  the secrets/accounts/request flow, in `docs/secrets-and-accounts.md`. Per an
  explicit user ask made mid-slice, both repos' `deploy.yml`/`ci.yml` were also audited to confirm
  neither uses `--no-cpu-throttling` on `gcloud run deploy` (instance-based billing) — Cloud Run
  billing for both services is request-based only. `COOKIE_DOMAIN` was deliberately **not** wired
  into either service yet: an early attempt broke all 16 login-dependent E2E tests, since E2E hits
  the raw `*.run.app` host rather than the LB's custom domain and a domain-scoped cookie never
  reaches it — full cross-domain SSO cutover (custom-domain E2E, `COOKIE_DOMAIN` live) is Slice
  R11's job, not this tracer bullet's. A genuine deploy-blocking bug was caught and fixed during
  first-deploy troubleshooting: the Host's own `pyproject.toml` was still pinned to
  `organizeme-chrome@chrome-v0.1.1` (only Event Creator's pin had been bumped to v0.2.0), so
  `infra/gcp_lb/generate_url_map.py` silently generated the URL map from the stale pre-split
  registry even after `provision.sh` ran successfully — caught by verifying the *live* URL map
  content rather than trusting a clean script exit, fixed by bumping the Host's own pin, re-locking,
  and re-running `provision.sh`. Two lower-priority findings deferred as `modelsuggested` Intake
  issues: #181 (Alembic adoption has no safety net for fresh environments) and #182 (non-root
  Docker user + pin chrome to a commit SHA rather than a mutable tag).
- **Issue #159 implemented — Slice R5: GCP HTTPS Load Balancer + Path Routing + Managed SSL**
  (branch `restructure/r5-load-balancer`). Provisions the shared External HTTPS Load Balancer that
  will front `organizeme.qa.russcoopersoftware.com`. New `infra/gcp_lb/generate_url_map.py` is a
  pure function turning the R3 app-registry (`organizeme_chrome.registry`) into URL-map path rules
  — Host-owned auth routes (`/`, `/login`, `/register`, `/forgot-password`, `/reset-password`,
  `/profile`) are a fixed list since they aren't part of any app's nav, everything else is derived
  per-app so a path never needs hand-maintaining separately from the registry that also drives
  chrome rendering (R3). `tests/test_url_map_generator.py` (5 tests, TDD) covers host/app path
  dedup and proves the generator is registry-driven, including that R6's Event Creator can be
  added without changing the generator. **IaC tooling decision** (open item in the WBS spec):
  chose a `gcloud` shell script (`infra/gcp_lb/provision.sh`) over Terraform, matching this repo's
  existing pattern of plain `gcloud` calls in `ci.yml`/`deploy.yml` rather than introducing a new
  toolchain. The script is idempotent (existence-checked before each create) and provisions two
  global static IPs (v4+v6), Cloud DNS A/AAAA records in the `russcoopersoftware-com` zone (R0),
  a Google-managed SSL cert, a Serverless NEG against `organizeme-qa`, two backend services
  (`host-backend` + `organizeme-backend`, both on the same NEG today since Host and the
  "organizeme" app are one Cloud Run service pre-R6), the generated URL map, a target-HTTPS-proxy,
  and global forwarding rules. **Deliberately not run as part of this PR/CI**: per user decision
  (mirroring R0's and R4's manual-operator pattern), this creates real billable GCP resources and
  the managed cert can't validate until DNS propagates — up to ~24h — so `infra/gcp_lb/README.md`
  documents running `provision.sh` manually post-merge; the live-LB acceptance criterion isn't
  something this PR's CI can verify. A `code-review-master` pass caught three real bugs before
  merge, all fixed: (1) `provision.sh`'s backend-service idempotency check used a `{ ... }` block
  as the RHS of `||`, which cascades bash's `errexit` exemption into the whole block (BashFAQ/105)
  — a failing `add-backend` after a successful `create` would silently continue past step 5 with
  no NEG attached, and re-running would then skip the block entirely since `describe` now
  succeeds; replaced with an explicit `if`. (2) The forwarding-rules `create` calls omitted
  `--load-balancing-scheme=EXTERNAL_MANAGED`, defaulting to the classic `EXTERNAL` scheme and
  mismatching the backend services' scheme — would have failed at the very last provisioning
  step, after all the billable resources before it were already created; both calls now specify
  it explicitly. (3) The generated URL-map YAML referenced backend services by bare name
  (`service: host-backend`); `gcloud compute url-maps import`'s schema expects a resource path
  (`global/backendServices/host-backend`) — bare names are silently misresolved rather than
  rejected. Also added, on review: a cross-app path-collision guard in `generate_path_rules`
  (raises naming both apps if two non-host apps claim the same nav path, since `gcloud` would
  otherwise reject the resulting ambiguous URL map) and 2 more tests (7 total) covering the
  collision guard and parsing the rendered YAML structure end-to-end (`pyyaml` added as a dev
  dependency). One review finding deferred rather than fixed now: the generator only routes paths
  present in each app's `nav` list, not an app's full route surface (nested pages, `/api/v1/*`) —
  harmless in R5 since there's only one real backend, but a genuine gap once R6 splits Event
  Creator into its own service; filed as issue #178 (`modelsuggested`, Intake). Full mypy
  (`--strict`, whole repo) clean; both review agents' fixes verified, `code-quality-guardian`
  returned no changes requested on the original pass.
- **Issue #160 implemented — Slice R4: Domain-Scoped SSO Cookie + Secret Manager**
  (branch `restructure/r4-domain-cookie-secret-manager`). Adds the capability the future
  cross-service SSO (R6+) needs, without flipping it on live yet. `app/auth/backend.py` gains a
  `COOKIE_DOMAIN` env var (read via plain `os.environ`, mirroring the existing `COOKIE_SECURE`
  pattern — the module is built once at import time, before `Settings`/`get_settings()` would
  normally resolve), wired into `fastapi_users`' `CookieTransport(cookie_domain=...)`. Blank/unset
  collapses to `None`, which is byte-for-byte identical to omitting the parameter (verified against
  `CookieTransport`/Starlette's `Response.set_cookie` source — no `Domain` attribute is ever
  emitted), so today's implicit host-only cookie behaviour is completely unchanged. **Deliberately
  left unset in `ci.yml`/`deploy.yml`** rather than set to `organizeme(.qa).russcoopersoftware.com`
  as the WBS spec's literal example values: QA/prod currently serve on `*.run.app` hosts, not those
  eventual shared-origin hostnames (DNS cutover R0 and the Load Balancer R5 haven't landed), and a
  cookie scoped to a host the browser isn't actually talking to would never be sent back — breaking
  login in QA/prod immediately. This was an explicit user decision (proceed with R4 ahead of R0/R5
  rather than wait, but keep the flip inert until they land) rather than an implementation gap.
  New `tests/test_auth_backend_cookie_domain.py` (3 tests) exercises the unset/blank/set cases via
  `importlib.reload` under patched env vars — necessary because, like `COOKIE_SECURE`, the value is
  parsed once at import; confirmed by code review that this reload cannot leak into other test
  files since every other module consumes `auth_backend`/`cookie_transport` by value
  (`from app.auth.backend import ...`), not by live module-attribute access. The three
  "cookie issuance sites" the WBS spec calls out (`app/api/v1/auth.py`, `storage_google_drive.py`,
  `storage_dropbox.py`) needed no changes — their `set_cookie()` calls are unrelated OAuth CSRF
  state cookies; the actual auth cookie is issued once via the shared `cookie_transport` object and
  relayed verbatim by `_redirect_with_login_cookie`, so all three pick up the domain scoping
  automatically. Also wired the JWT signing secret through GCP Secret Manager on Cloud Run:
  `ci.yml`/`deploy.yml` no longer write `JWT_SECRET` into the plaintext `--env-vars-file`, instead
  passing `--set-secrets=JWT_SECRET=jwt-secret-qa:latest` / `jwt-secret-prod:latest` on the
  `gcloud run deploy` step (the `test` job's plain `JWT_SECRET` GitHub Actions secret, used for
  local pytest/mypy against real QA, is untouched — separate concern). **Human setup required
  before deploy succeeds:** the `jwt-secret-qa`/`jwt-secret-prod` GCP Secret Manager secrets don't
  exist yet — no local `gcloud` credentials were available this session to create them. The
  operator must create both secrets (seeded with the existing `JWT_SECRET_QA`/`JWT_SECRET_PROD`
  values so already-issued tokens stay valid), and grant the Cloud Run runtime service account
  (`170051512639-compute@developer.gserviceaccount.com`, the project default — neither service sets
  a custom `--service-account`) `roles/secretmanager.secretAccessor` on each. Until then,
  `deploy-qa`/`deploy-prod` will fail at the `--set-secrets` step — expected, not a regression.
  Full suite (488 tests, chunked due to background-process flakiness in this environment — zero
  failures across all chunks) + `packages/chrome`'s own suite (9 tests) + `mypy --strict` (both
  `app`/`tests` and `packages/chrome`) all clean. Both `code-review-master` and
  `code-quality-guardian` review passes came back with no changes requested.
- **Issue #157 implemented — Slice R3: Extract Shared Chrome/Theme Package + App-Registry**
  (branch `feature/restructure-r3-chrome-package`). New installable package,
  `packages/chrome/` (`organizeme-chrome`, own `pyproject.toml`/src-layout/pytest/mypy), owning
  the sidebar/header/Settings-tab-bar Jinja templates (moved verbatim from
  `app/templates/base.html` + `authenticated_base.html`, now deleted), the Tailwind/DaisyUI theme
  strings, the app-registry (`organizeme_chrome.registry` — nav items + Settings tabs per hosted
  app, replacing `app/pages/nav.py`), and a standalone JWT-verify helper
  (`organizeme_chrome.verify_token` — PyJWT, HS256, signature + expiry + audience only, no
  fastapi-users import, no network call) that a future hosted app (Event Creator, R6) will depend
  on for identity instead of the Host's full fastapi-users auth stack. The Settings tab-bar was
  generalized from OrganizeMe's hardcoded Storage/Notifications markup into a data-driven
  `settings_tab_bar(tabs)` Jinja macro, driven by the registry's `settings_tabs` per app. Host
  wiring: `app/core/templating.py` calls `organizeme_chrome.register_chrome(env,
  app_service_name="organizeme")`, which adds the package's template directory to the Jinja
  loader and exposes `nav_items`/`settings_tabs`/theme globals; every page template now extends
  `chrome_base.html`/`chrome_authenticated_base.html` instead of the deleted originals. Host pins
  the package as a **git-tag dependency** (`organizeme-chrome @
  git+https://github.com/rustycoopes/organize-me@chrome-v0.1.1#subdirectory=packages/chrome`) —
  chosen over GitHub's beta PyPI registry to avoid extra registry-auth-token plumbing for no
  functional benefit; a new `.github/workflows/publish-chrome.yml` builds and attaches a
  versioned wheel/sdist to a GitHub Release on `chrome-v*` tag push, so a Host-side chrome edit
  never reaches a consumer until it bumps its pin, per the platform-restructure design. New
  `tests/test_chrome_jwt_interop.py` proves a real Host-issued auth cookie verifies via the
  package helper; `packages/chrome/tests/` covers the JWT helper and registry in isolation.
  `tests/test_sidebar.py` (unchanged) is the byte-for-byte parity check that the Host still
  renders identically post-extraction. Local `pytest` initially showed a large batch of failures
  (`column users.notification_sms does not exist`); root cause turned out to be Slice R2 (#158,
  below) mid-flight on the same shared QA database, stamping its migration ahead of what this
  branch's history knew about — resolved by merging `main` (with R2's migration) into this branch
  once #158 landed, not a bug in this slice.
- **Issue #158 implemented — Slice R2: Decouple Event-Creator Data from the Host `users` Model**
  (branch `restructure/r2-decouple-event-creator-user-data`). Removes the two remaining
  Host↔Event-Creator data couplings identified in the Platform Restructure design: (1) moved
  `notification_sms`, `notification_email`, `onboarding_storage_done`,
  `onboarding_notifications_done`, `onboarding_first_upload_done` off `host.users` into a new
  `event_creator.user_settings` table (one row per user, FK-cascaded to `host.users.id`), created
  lazily via `get_or_create_user_settings` (`app/services/user_settings.py`) rather than eagerly
  at registration - mirrors the existing `get_or_create_user_prompt` lazy-seed pattern, so
  `on_after_register` never writes Event-Creator data; (2) removed the eager `LLMPrompt` insert
  from `app/auth/users.py::on_after_register` entirely, relying on that same pre-existing lazy
  self-heal path (`app/api/v1/llm_prompt.py::get_or_create_user_prompt`) to seed a new user's
  prompt on first visit to the Prompt page instead. A single Alembic migration
  (`e6f7a8b9c0d1`) creates `event_creator.user_settings`, backfills it from every existing
  `host.users` row's real values (not column defaults), then drops the five moved columns -
  backfill-then-drop keeps rollback safe. Every reader/writer of these fields was repointed:
  the users API (`GET`/`PATCH /api/v1/users/me`), the Settings/Dashboard pages, the onboarding
  checklist view-model, the notification sender and pipeline runner's "silently disabled
  channel" warning, and the four onboarding-flag writers (Dropbox/Google Drive OAuth callbacks,
  manual upload, import-pending-files) - the latter two now share
  `mark_storage_onboarding_done`/`mark_first_upload_onboarding_done` helpers instead of
  duplicating a get-or-create-then-commit sequence four times. `PATCH /api/v1/users/me`'s
  notification-prefs write is sequenced *after* the core `user_manager.update()` call succeeds
  (not before) specifically so a request that fails on a conflicting email never partially
  persists the notification-prefs half of the same PATCH - a regression a code review caught
  before merge, now covered by a dedicated test. No API/URL contract changes this slice (the
  `notification_email`/`notification_sms` fields stay on `UserRead`/`UserUpdate` exactly as
  before) - only where the data is stored/read server-side changed. Two lower-priority follow-ups
  from code review filed as `modelsuggested` issues #174 (shared test fixture for the
  notification-prefs `UserSettings` row) and #175 (migration `downgrade()` column-definition
  duplication).

- **Issue #156 implemented — Slice R1: Database Schema Separation** (branch
  `restructure/r1-db-schema-separation`). Platform Restructure prefactoring: introduces `host`
  and `event_creator` Postgres schemas in the shared Supabase QA database and moves the existing
  tables into them via metadata-only `ALTER TABLE ... SET SCHEMA` (`users`, `oauth_accounts` →
  `host`; `storage_configs`, `llm_prompts`, `processing_runs`, `processing_steps`, `events` →
  `event_creator`), including their Postgres enum types (`storage_provider`,
  `processing_run_status`, `processing_step_status`). Creates two `NOLOGIN` roles - `host_app`
  (full R/W on `host`, no access to `event_creator`) and `event_creator_app` (full R/W on
  `event_creator`, `REFERENCES`-only on `host.users`, no other `host` access) - as the
  least-privilege grants the eventual service split will use; the running app keeps its existing
  admin `DATABASE_URL` connection unchanged in this slice, so nothing about the app's runtime
  behaviour changes. All 7 SQLAlchemy models now declare their schema via `__table_args__`
  (cross-schema FKs fully schema-qualified, e.g. `ForeignKey("host.users.id", ...)`) and the three
  `SAEnum` columns now declare `schema="event_creator"` explicitly - omitting it left Postgres
  unable to resolve the now-relocated enum type name at insert time (`type "..._status" does not
  exist`), caught by the new regression tests before merge. Alembic's `version_table_schema` is
  now pinned to `public` (unchanged in practice - that's where the version table already lived -
  but now explicit, prepping for per-repo Alembic history in a later slice). New
  `tests/test_schema_separation.py` (9 tests) verifies table→schema placement, the role grants
  (via `has_schema_privilege`/`has_table_privilege` - the roles are `NOLOGIN` so a real
  connect-as-role test isn't possible this slice), and that deleting a `host.users` row still
  cascades to a user's `event_creator` rows. No app code outside `app/models/*.py` changed - no
  endpoint issues unqualified table names, so this was a pure DB/model change.

- **Issue #144 fixed** — notification delivery failures now surface with detail (branch
  `fix/notification-delivery-visibility`). A real email/SMS delivery failure (bad/unset
  credentials, the provider rejecting the recipient, a network error, ...) inside
  `RealNotificationSender._send_with_session` (`app/services/notifications/sender.py`) used to be
  swallowed by a bare `except Exception: logger.exception(...)` per channel - the pipeline's
  Notify step still logged "Notified user: ..." and reported success regardless, so a genuine
  delivery failure was indistinguishable from a real send anywhere the user (or support) could
  see, exactly the reported symptom: preferences correctly set to notify, no error shown, but no
  email/SMS ever arrived. `NotificationSender.send()` (the pipeline's boundary Protocol, `app/
  services/notifications/pipeline.py`) now returns `list[str]` describing each enabled channel
  that raised; `app/services/pipeline/runner.py::_notify()` appends each as a `Warning: ...` log
  line on the Notify step (same convention #112 already established for silently-disabled
  channels), visible via `/processing-runs/{id}/logs`. Also gave `ResendEmailSender.send()` the
  same fail-fast-on-unset-config guard `TwilioSmsSender` already had (issue #124's deferred
  email-side half) - a missing `RESEND_API_KEY` now raises a clear `RuntimeError` immediately
  instead of a confusing Resend SDK error after a live network round-trip. 4 new regression tests
  (email + SMS delivery-failure surfacing, the Notify step log line, the Resend config guard); full
  suite green; `mypy --strict` clean. Investigating the report surfaced the likely actual root
  cause: `Settings.email_from` defaults to Resend's shared sandbox sender
  (`onboarding@resend.dev`), which Resend restricts to only deliver to the account's own verified
  address - if prod hasn't verified a custom sending domain, arbitrary recipients' emails would be
  rejected exactly like the reporter's symptom. That's an account/DNS-level fix outside this
  repository, filed as `modelsuggested` issue #152; this fix's real, concrete value is making that
  failure (or any other future one) visible instead of silent.

- **Issue #143 fixed** — import-pending-files errors now surface with detail (branch
  `fix/import-pending-files-error-detail`). A Drive/Dropbox API failure while listing pending files
  (`POST /api/v1/import-pending-files`) or writing an uploaded file (`POST /api/v1/upload`) used to
  propagate as an unhandled exception, which FastAPI's default handler turns into a bare 500 with no
  `detail` body - the client's `messageFor()` map had nothing to key off, so the user always saw the
  generic "Import/Upload failed. Please try again." with no indication of what actually went wrong
  (the reported symptom: files visibly waiting in Drive, click fails anyway, no explanation). Both
  endpoints now catch `GoogleDriveError`/`DropboxError` around the storage call, `logger.exception`
  it (with the user id, for support/log correlation), close the provider, and return a `502` with
  detail `storage_error`, which `import_pending_button.html` and `upload.html` map to "Could not reach
  your storage provider. Try reconnecting it in Settings, or try again in a moment." 2 new regression
  tests (`test_import_pending_files_api.py`, `test_upload_api.py`), each asserting the 502/detail and
  that no run is created/scheduled on failure. The first draft of that message used "Couldn't" - a
  literal apostrophe inside the single-quoted `x-data='...'` Alpine attribute, which terminated the
  attribute early and broke Alpine init for the whole button (the exact bug class #23's
  `register.html` fix already warned about in this same file). CI's `e2e-qa` job caught it
  (`import-pending-files.spec.ts`/`processing.spec.ts` failing against the deployed QA app even
  though the backend was verified correct via direct API calls); reworded to "Could not" to sidestep
  the apostrophe rather than escaping it. Two lower-priority improvements deferred to issues #146
  (distinguish auth-failure from transient errors with a dedicated `storage_reauth_required` detail)
  and #147 (e2e coverage for the `storage_error` path), both `modelsuggested`.

- **Issue #94 implemented** — S3 StorageProvider (Slice 8.2, branch
  `feature/s3-storage-provider`). New `S3StorageProvider` (`app/services/storage/s3.py`) implements
  the `StorageProvider` ABC against a user's manually-entered AWS credentials (access key, secret,
  bucket, region — no OAuth), using the synchronous `boto3` SDK with every blocking call wrapped in
  `asyncio.to_thread` (mirroring `ResendEmailSender`'s pattern, per the issue's specified approach,
  rather than adding `aioboto3`). `folder_path` is treated as a key prefix within the bucket;
  `list_new_files` lists with `Delimiter="/"` so S3's native prefix listing (which is recursive by
  default) matches the non-recursive, direct-children-only semantics Dropbox/Google Drive already
  have — `processed/`/`failed/` sub-prefixes (and any other nested "subfolder") are excluded by
  construction rather than by manual filtering. S3 has no native move, so `move_file` is
  copy-then-delete. `app/services/storage/factory.py` gains `build_s3_provider`, decrypting all
  four stored credential columns and wiring a live `S3StorageProvider` into
  `build_storage_provider` for `provider = s3` (previously raised `unsupported storage provider`).
  Added `boto3` to `pyproject.toml` (+ `mypy` `ignore_missing_imports` overrides for `boto3`/
  `botocore`, which ship no type stubs). 14 new provider tests plus 2 new factory tests, all via a
  hand-rolled fake S3 client (no live AWS credentials touched in CI, per the issue's acceptance
  criteria); full suite (455 tests) and `mypy --strict` clean. Improvement pass: wrapped every
  boto3 call's `ClientError`/`BotoCoreError` in a new `S3Error` (previously defined but unused —
  errors would have propagated as raw botocore exceptions, unlike Dropbox's `DropboxError`
  wrapping), and added a factory test asserting the *decrypted* credential values actually reach
  `boto3.client(...)` (previously only checked the resolved provider type, not that decryption
  happened correctly — a mismatch would otherwise only surface as an opaque AWS auth failure at
  runtime). Two lower-priority ideas deferred to `modelsuggested` issues #149 (retry/backoff on S3
  throttling errors) and #150 (`boto3.client()` construction runs synchronously on the event loop —
  fixing it properly cascades into an async refactor of `build_storage_provider` and both its
  callers, out of proportion to this issue's scope).

- **Issue #112 implemented** — log notification silent modes as warnings (branch
  `feature/slice-7-notify-silent-mode-warnings`). During the pipeline's Notify step,
  `_silent_notification_modes_warning()` adds one extra log line naming which channels won't
  actually fire (`disabled email`, `disabled SMS`, `no phone number` — only the ones that apply,
  omitted entirely when everything's live), mirroring `RealNotificationSender`'s own gating exactly
  so the warning can never disagree with what actually sends. Doesn't affect step/run status; no
  new endpoint wiring needed since `/processing-runs/{id}/logs` already surfaces arbitrary
  `ProcessingStep.log_lines`. 6 new tests, including one true end-to-end test through the real
  logs endpoint. No improvement-pass changes or `modelsuggested` issues — matched the acceptance
  criteria with no gaps.

- **Issue #113 implemented** — "reviewed" flag on dashboard events (branch `feature/slice-5-events-reviewed-flag`). New `reviewed` boolean column on `events` (migration `a7b8c9d0e1f2`, default `false`) plus a partial index `ix_events_user_id_unreviewed_sort` (migration `b8c9d0e1f2a3`, `WHERE reviewed = false`) covering the dashboard's now-default `reviewed = false` filter+sort, matching the precedent set by `f6a7b8c9d0e1`. `GET /api/v1/events` and `/dashboard` gain a `show_reviewed` param (default `false`) that hides reviewed events, composing with the existing type/date/search filters and pagination. New `PATCH /api/v1/events/{id}` endpoint (owner-scoped via a shared `get_owned_event` helper, same 404 semantics as `DELETE`) toggles the flag and returns the updated event. Dashboard table gets a per-row "Reviewed" checkbox (Alpine.js `fetch` PATCH, no page reload, reverts on failure) and the filter bar gets a "Show reviewed" checkbox. 15 new tests (9 API, 6 page-level) covering default-hide behaviour, the show-all toggle, filter composition, PATCH ownership/404 semantics, and the all-reviewed empty-state message; full suite green; `mypy --strict` clean.

  A code-review pass then caught two real bugs pre-merge: marking a row reviewed while "Show reviewed" was off used hand-written JS to remove the row and decrement a count, which desynced from the server on pagination boundaries (didn't backfill rows from the next page, didn't show the empty-state message when the last row was removed) — fixed by re-rendering `#dashboard-body` via `htmx.ajax()` after a successful PATCH instead, reusing the same swap every other filter/sort/page control on this page already uses; and `has_active_filters` didn't count the default `show_reviewed=false` hiding as a filter, so a returning user whose events were all reviewed saw the misleading first-time "No events yet" message — fixed using the already-fetched `event_types` list (unaffected by filters) as a free signal that the user has events at all. Also fixed in the same pass: a redundant `db.refresh()` after commit (the session is `expire_on_commit=False`) and duplicated owner-lookup code between `DELETE`/`PATCH` (extracted to `get_owned_event`). Two lower-priority suggestions deferred to issues #135 (type-filter dropdown includes types that only exist on reviewed events) and #136 (no e2e coverage for the reviewed checkbox/filter interaction), both `modelsuggested`.

- **Issue #93 implemented** — Dropbox StorageProvider (Slice 8.1, branch
  `feature/slice-8.1-dropbox-storage-provider`). New `DropboxStorageProvider`
  (`app/services/storage/dropbox.py`) implements the `StorageProvider` ABC against the Dropbox API
  v2 via an injected `httpx.AsyncClient` (no official `dropbox` SDK dependency, mirroring
  `google_drive.py`'s pattern): files are addressed by Dropbox's stable `id:...` identifier rather
  than path (paths change on move/rename), `list_new_files` walks `list_folder`/`list_folder/continue`
  pagination filtering to `.tag == "file"` entries, and `move_file` creates the destination
  `processed/`/`failed/` subfolder on first use (tolerating the "already exists" conflict).
  New `app/api/v1/storage_dropbox.py` mirrors the Google Drive OAuth connect/disconnect flow
  (`POST /auth`, `GET /callback`, `POST /disconnect`) with its own CSRF cookie/state audience,
  requesting `files.content.write`/`files.content.read` scopes (a scoped Dropbox app only grants
  what's explicitly requested, unlike Google's client) and `token_access_type=offline` for a
  refresh token. Dropbox's revoke endpoint authenticates via the token being revoked (not a token
  passed in the request body like Google's), so `revoke_dropbox_token` calls it directly rather
  than through `httpx_oauth`. New `get_dropbox_oauth_client()` (`app/auth/oauth.py`) builds a
  generic `httpx_oauth.oauth2.BaseOAuth2` client, since `httpx_oauth` ships no dedicated Dropbox
  client (unlike Google/GitHub/etc). `app/services/storage/factory.py`'s `build_storage_provider`
  now actually branches on `config.provider` (previously always resolved to Google Drive
  regardless — a latent placeholder now fixed) and raises for the not-yet-implemented S3 provider
  (Slice 8.2, #94). New settings `DROPBOX_OAUTH_CLIENT_ID`/`DROPBOX_OAUTH_CLIENT_SECRET` (empty
  defaults, same pattern as the other optional provider credentials). 25 new tests (provider unit
  tests via `httpx.MockTransport`, OAuth flow tests mirroring `test_storage_google_drive.py`, and
  factory branching tests); `mypy --strict` clean. Improvement pass: added the
  `files.content.write`/`files.content.read` scope request (a scoped Dropbox app silently grants
  no permissions without it — a real functional gap, not just a nice-to-have), wired
  `DROPBOX_OAUTH_CLIENT_ID`/`SECRET` into `ci.yml`/`deploy.yml`'s Cloud Run env vars (mirroring the
  Twilio/Google precedent), and decoupled the consent-URL test from ambient environment
  configuration (overrides `get_dropbox_oauth_client` with a client built from literal test
  credentials, rather than asserting against whatever `DROPBOX_OAUTH_CLIENT_ID` happens to be set
  in the environment it runs in — no such secret exists in the repo yet). Deferred lower-priority
  idea (persisting the refreshed access token back to `storage_configs`, mirroring the existing
  Google Drive gap in #68) filed as `modelsuggested` issue #140. **Human setup before it works
  live:** register a Dropbox app at dropbox.com/developers/apps (scoped access, `files.content.write`
  + `files.content.read` permissions) and set `DROPBOX_OAUTH_CLIENT_ID`/`DROPBOX_OAUTH_CLIENT_SECRET`
  as repo secrets — same class of gap as issue #72's Google/Gemini/Twilio setup steps. Settings >
  Storage tab UI support for Dropbox (provider selector, connect button) is Slice 8.3 (#95), not
  in this issue's scope.
  An 8-angle multi-agent code-review pass then caught and fixed four real issues, several
  independently flagged by multiple angles: (1) `DropboxStorageProvider._raw_request`'s 401-retry
  rebuilt headers with the stale dict spread last, so a just-refreshed Authorization header was
  silently overwritten by the expired one that had just failed — any live 401 (a revoked token, or
  the proactive expiry check being wrong) would refresh successfully but still retry with the same
  invalid token and raise; (2) `_normalize_path` never guaranteed a leading `/`, but Dropbox
  requires one on every non-root path — `folder_path`'s write-path validator is shared across all
  three providers and only trims whitespace, so a value saved without a leading slash (harmless for
  Google Drive's split-and-traverse resolution) would send a malformed path to every Dropbox call;
  (3) `dropbox_disconnect` preferred the refresh token over the access token when calling Dropbox's
  revoke endpoint, but that endpoint authenticates via the token *being revoked* as the Bearer
  credential (unlike Google's body-param revoke, where either works) — since `token_access_type=
  offline` means a refresh token is present on nearly every connection, disconnect would 401
  against Dropbox, have the exception swallowed by the best-effort try/except, and leave the actual
  grant live indefinitely while the UI showed "disconnected"; (4) `PUT /api/v1/storage-config`
  didn't clear a config's stored credentials when the provider changed, so a config could stay
  "connected" under a *different* provider than the one its token authenticates — reachable by
  connecting Google Drive then switching `provider` to `s3` without disconnecting first, which
  would hit `build_storage_provider`'s new not-yet-implemented-S3 `ValueError` instead of the
  factory silently (if wrongly) building Google Drive as it did before this issue. 6 new regression
  tests (live-401 retry, path normalization, disconnect token choice, provider-switch credential
  clearing x2); full suite (422 tests) + `mypy --strict` green.

- **Issue #110 implemented** — Import pending files button (branch
  `feature/slice-7-import-pending-files`). New `POST /api/v1/import-pending-files` scans the
  connected storage watch folder via `StorageProvider.list_new_files()`, creates one
  `processing_runs` row per pending file, and processes them **sequentially** in a single
  background task (new `PipelineScheduler.schedule_batch()`, resolved via a clarifying question
  before building — differs from the manual upload path's fire-and-forget-per-file `schedule()`).
  Returns the first file's `run_id`; the client follows it to `/processing` like a manual upload,
  with the rest of the batch visible afterward via `/logs`. New shared `is_drive_connected()`
  helper (`app/api/v1/storage_config.py`) and `partials/import_pending_button.html` back the
  button on both `/upload` and `/dashboard` without duplicating the Alpine fetch/redirect logic.
  New Playwright `e2e/tests/import-pending-files.spec.ts` covers what's deterministic under
  `E2E_TEST_MODE` (button enabled, "no pending files" on click); genuinely populating pending
  files needs a real connected Drive account, out of e2e scope per the standing #23 decision.
  Improvement pass: importing now also flips `onboarding_first_upload_done`, matching manual
  upload. A code-review pass then caught and fixed three real issues confirmed independently by
  multiple review angles: `_run_batch` never rolled back its shared session after an unhandled
  per-file failure, which would silently poison every remaining file in the batch; `get_import_storage`
  duplicated the "is Drive connected" check instead of reusing the `is_drive_connected()` helper
  this same diff introduced; and a dead `db.refresh()` loop issued one wasted SELECT per pending
  file despite `expire_on_commit=False` making it a no-op. Also fixed a minor storage-client leak
  on the no-pending-files path and updated README.md. Two lower-priority findings deferred as
  `modelsuggested`: auto-advancing `/processing` across a whole batch instead of only the first
  file (#132), and guarding against a double-click/multi-tab race enqueuing duplicate batches —
  same class of gap the existing single-file upload endpoint already has, backstopped by the
  `events` table's dedup constraint (#133). 9 new/updated backend tests; full suite +
  `mypy --strict` green.

- **Issue #115 verified** — onboarding checklist hide-on-completion (branch
  `feature/slice-5.3-onboarding-hide-verify`). No code changes were needed: the mechanism
  (`onboarding_complete()` + the dashboard's conditional render) was already correct, and #88's
  review pass had already fixed the one real bug (stale `/profile` link) blocking this from working.
  Added a regression test that drives all three onboarding steps through their real endpoints
  (Drive OAuth connect, notification-prefs PATCH, file upload) rather than setting the User flags
  directly, so a regression in any endpoint's flag-flipping logic would be caught, not just in the
  dashboard's read of those flags. Full Playwright e2e coverage of the flow stays out of scope per
  the standing #23 decision to keep real Google OAuth out of e2e (tracked separately in the
  already-open #91).

- **Issue #88 implemented** — Slice 7.3 Settings > Notifications tab (branch
  `feature/slice-7.3-notifications-tab`). New Notifications tab on `/settings` alongside Storage
  (Alpine `activeTab` state switches between them client-side, no reload), with independent
  email/SMS toggles backed by the existing `PATCH /api/v1/users/me` — `UserRead`/`UserUpdate`
  gained `notification_email`/`notification_sms` (same NOT-NULL/explicit-null-rejection pattern
  as `dark_mode`). Email toggle disabled unless `user.email` is set; SMS toggle disabled unless
  `user.phone_number` is set; either way, hint text plus a read-only display of the current
  email/phone linking to `/profile`. Saving sets `onboarding_notifications_done = True` the first
  time either toggle is part of a PATCH payload (idempotent thereafter). New Playwright
  `e2e/tests/notifications.spec.ts` (SMS toggle disabled → enabled after setting a phone number in
  Profile; email toggle save/reload round-trip). The "toggle off stops that channel sending"
  criterion is covered for both channels: email by Slice 7.1's existing test, and SMS by a new
  test added here once Slice 7.2 (#87, merged to `main` the same day) landed the SMS sender —
  closing the gap `modelsuggested` issue #129 had flagged. Also filed #128 (`modelsuggested`):
  both Settings tabs hand-roll card/tab markup instead of the shared `card_page` macro, deferred
  to avoid scope creep into the already-shipped Storage tab. 20+ new/updated backend tests; full
  suite + `mypy --strict` clean.
  A code-review pass then caught and fixed three real issues: the onboarding checklist's
  "Set Notification Preferences" step still linked to `/profile` (no notification UI there) instead
  of `/settings`; the onboarding-flag write did a second `db.commit()`/`refresh()` after
  `user_manager.update()` had already committed (folded into the same transaction by setting the
  flag on `user` before that call); and the tab bar's active/`aria-selected` state existed only in
  Alpine bindings, so a screen reader or pre-hydration fetch saw neither tab marked active
  (restored static `tab-active`/`aria-selected="true"` on Storage matching Alpine's initial state).
  A fourth candidate fix - rejecting a channel toggle turned on with no matching contact info on
  file - was tried and reverted: it contradicted Slice 7.2's already-shipped design, where
  `RealNotificationSender` silently skips an SMS send with no phone number rather than treating it
  as an error, and `notification_sms` defaults `True` for every user regardless of whether a phone
  number is on file. The reverted validation broke `e2e-qa` (a user saving the email toggle alone
  still resends the default-`True` `notification_sms`, which would have 422'd with no phone set) -
  caught by the deployed Playwright suite, not by local pytest, since the local suite's fixtures
  happened to always set a phone number first.

- **Issue #87 implemented** — Slice 7.2 SMS notifications via Twilio (branch `feature/slice-7.2-sms-notifications`). New `app/services/notifications/sms.py`: `SmsSender` Protocol, real `TwilioSmsSender`, `FakeSmsSender` test double — mirrors the `EmailSender` pattern. `RealNotificationSender` now sends SMS alongside email, independently gated on `user.notification_sms` and a non-empty `user.phone_number` (silently skipped, info-logged, if the toggle is on but no phone number is on file — never raises or blocks the run). Success SMS: event count + dashboard link. Failure SMS: error summary + log page link. New config: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER` (empty defaults). New `twilio` dependency + mypy override (no bundled type stubs). Proactively wired `TWILIO_*` secrets into `ci.yml`/`deploy.yml`. Improvement pass: `TwilioSmsSender` now raises a clear error if credentials are unset instead of a confusing SDK error, and caches its `twilio.rest.Client` at class level instead of rebuilding it (and its connection pool) on every send. 9 new tests; full suite (353+ tests) + `mypy --strict` green. Deferred (`modelsuggested`): E.164 phone-number validation on the Profile page (#120), generalizing email/SMS dispatch in `RealNotificationSender` (#124), concurrent email+SMS sends (#125).

- **Issue #111 implemented** — Redesigned `/logs` as an HTMX-driven spreadsheet grid (branch
  `feature/logs-grid-redesign`). `GET /api/v1/processing-runs` gains `status`/`date_from`/
  `date_to`/`sort_by`/`sort_dir` query params (`sort_by` one of `date`/`filename`/`status`), all
  composing with each other and with pagination — same filter-composition pattern as the
  dashboard's events endpoint (#55). New `ProcessingRunRead.detail_summary` field: the first
  error log line for a `failed` run (falling back to any captured log line, then a fixed
  placeholder, if no step itself was marked failed) or an `"N log lines"` count otherwise,
  computed by `build_run_detail_summaries()` from the page's already-fetched steps (avoids
  per-row queries). The `/logs` page's filter form (Status dropdown + date-range pickers) and
  three sortable column headers (Date/Filename/Status, with `aria-sort` + a ▲/▼ indicator) swap
  `#logs-body` in place via `partials/logs_body.html`/`partials/logs_grid.html`, mirroring
  `partials/dashboard_body.html`. Each row is a full click target (keyboard-operable via
  `tabindex`/Enter, not just mouse) linking to `/processing-runs/{id}`. Pagination keeps the
  original page's First/Last jump links alongside Previous/Next. 30 tests (filter/sort/pagination
  composition, detail-summary fallback + deterministic-ordering cases, HTMX partial response);
  `mypy --strict` clean. Improvement pass: keyboard accessibility for row-click navigation,
  `aria-sort` on active sort headers, and the detail-summary fallback chain for a FAILED run with
  no step-level FAILED status. A multi-agent `/code-review` pass then caught a real correctness
  bug: the steps query backing `detail_summary` had no `ORDER BY step_number`, so for a run with
  multiple FAILED steps the "first error line" shown wasn't guaranteed to be the chronologically
  earliest one — fixed by ordering both the API endpoint's and the page's steps query, locked in
  with a test using deliberately out-of-order inserts. Same review pass also restored the
  First/Last pagination links (present in the original table, silently dropped by the initial
  grid) and simplified `sort_url_for` to reuse the existing `url_for` partial. Two lower-priority
  duplication findings (`parse_date_param` duplicated from `app/api/v1/events.py`; the
  runs+steps+summary fetch duplicated between the JSON endpoint and the HTML page) deferred rather
  than bundled into this PR. Deferred model-suggested ideas filed as `modelsuggested`-labelled
  issues (human-friendly date formatting, free-text search on the grid, a step-breakdown
  alternative for the details column).

- **Issue #85 implemented** — Slice 6.3 Searchable log filter + log download (branch `feature/slice-6.3-log-search-download`). The live HTMX search filter on the run detail page already existed from Slice 6.2; this issue added the missing piece: `GET /api/v1/processing-runs/{id}/logs/download`, which returns a run's full structured logs across all steps as a downloadable JSON file (`Content-Disposition: attachment`), plus a "Download logs" link on `/processing-runs/{id}`. Improvement pass: fixed a pre-existing bug where the log search escaped `%`/`_` as if for a SQL `LIKE` pattern even though matching was always a plain Python substring check, which silently broke searches containing those characters; extracted the duplicated search/pagination logic (API route + HTMX partial) into a shared `app/services/processing_logs.py` helper. Filed #118 (Intake) for a lower-priority follow-up: using the run's filename in the download's `Content-Disposition` filename instead of just the run id.

- **Issue #86 implemented** — Slice 7.1 Branded email notifications (branch `feature/slice-7.1-email-notifications`). Real `NotificationSender` implementation sends branded HTML emails on processing-run completion (success, zero-event, failure). New `RealNotificationSender` in `app/services/notifications/sender.py` fetches the user's email and notification preference, renders Jinja2 templates with inline CSS, and respects the `user.notification_email` flag. Two email templates: `success.html.j2` (event summary table + dashboard link) and `failure.html.j2` (error details + log page link). Updated `get_pipeline_notifier()` factory to return the real sender instead of the logging stub. New configuration: `BASE_URL` (defaults to `https://organize-me.app`, overrideable for local dev). Comprehensive test coverage: 7 new tests verify success, zero-event, failure emails, the off-flag behavior, and link correctness. Template environment cached at class level for performance.

- **Issue #84 implemented** — Slice 6.2 Run detail page with logs (branch `feature/slice-6.2-run-detail`, PR #107). New endpoints: `GET /api/v1/processing-runs/{id}` (run detail with steps), `GET /api/v1/processing-runs/{id}/logs` (paginated logs JSON), `GET /api/html/processing-runs/{id}/logs` (HTMX HTML partial). New page `/processing-runs/{id}` displays run metadata, 7 pipeline steps with status indicators, and expandable per-step logs (searchable, paginated via HTMX, 50 lines per page). Reuses step status rendering and progress service from `/processing` page. User scoping matches other resources (404 for non-owners). Comprehensive test coverage: 14 new tests, all 39 processing tests pass.

### Changed
- **Issue #100** — Dashboard "Agreed by" chips now show initials (e.g. "Russ Cooper" → "RC")
  instead of the full name, with the full name available via a `title` tooltip. New pure helper
  `app/core/initials.py::to_initials()` (first letter of first word + first letter of last word,
  uppercased; single-word names fall back to first letter; empty input returns empty string),
  registered as a Jinja filter (`app/core/templating.py`) and used in
  `partials/events_panel.html`. Improvement pass: made the chip focusable (`tabindex="0"`) so the
  tooltip is reachable via keyboard, not just mouse hover. Filed #137 (Intake) — `title` tooltips
  don't appear on touch devices at all, needs a product decision on a touch-friendly pattern — and
  #138 (Intake) — two people sharing initials render identical, undistinguishable chips.
- **Issue #31** — Extracted a shared `card_page` Jinja macro (`app/templates/macros/ui.html`) that
  renders the centred DaisyUI card shell (centering wrapper + `card`/`card-body`/`card-title` +
  optional subtitle). All five auth/profile templates (`login`, `register`, `forgot_password`,
  `reset_password`, `profile`) now import and call the macro instead of repeating the wrapper
  markup. Alpine.js `x-data` is placed on an ancestor `<div>` outside the macro call so directives
  inside the card body still resolve against the reactive scope. Regression tests added in
  `tests/test_card_macro.py`.

- **Issue #72 (partial)** — wired `GEMINI_API_KEY` into the QA/prod Cloud Run env-vars files in
  `.github/workflows/ci.yml` and `deploy.yml`, and added `--no-cpu-throttling` to both
  `gcloud run deploy` commands so the in-process pipeline background task (#52) isn't frozen by
  Cloud Run's default CPU throttling once the HTTP response returns. This only wires the plumbing —
  the `GEMINI_API_KEY` GitHub Actions secret still needs to be created manually, and item 3 (live
  Google Drive QA) remains a manual step; see the issue for the full checklist.
- **Issue #72 improvement pass** — `GoogleDriveStorageProvider.upload_file` (#52) switched from a
  single `uploadType=multipart` request built with httpx's `files=` (which encodes
  `multipart/form-data`, not the `multipart/related` Drive's multipart upload expects — the exact
  risk #72 flagged as untested) to a two-request approach: a metadata-only `POST /drive/v3/files`
  create, then a `PATCH .../upload/drive/v3/files/{id}?uploadType=media` body upload. Avoids the
  encoding mismatch entirely without hand-rolling a `multipart/related` body. Unit test updated to
  assert both requests' shape via `httpx.MockTransport`.

### Fixed
- **Issue #78** — Live Google Drive connect crashed with a raw "Internal Error" page. Root cause:
  the `ENCRYPTION_KEY` GitHub secret (flagged as an outstanding human-setup step since #45/#61) had
  never actually been created, so `get_credential_cipher()`'s `RuntimeError` went unhandled inside
  `GET /callback`. Fixed on branch `fix/issue-78-encryption-key-callback`: generated a `Fernet` key
  and set the `ENCRYPTION_KEY` repo secret (shared by `ci.yml`/QA and `deploy.yml`/prod — resolves
  that part of #61 too), and the callback now catches the missing-cipher case and redirects to
  `/settings?error=storage_not_configured` with a clear banner instead of a 500. #61's remaining
  scope (Google Cloud Console redirect URI + `drive` scope registration) is still an open manual
  task.

### Added
- **Issue #56 implemented** — Slice 5.3 Getting Started onboarding checklist on the dashboard
  (branch `claude/admiring-carson-v5qr9b`). A 3-step checklist (Connect Storage → `/settings`,
  Set Notification Preferences → `/profile`, Upload First File → `/upload`) renders above the
  events table, its per-step done/incomplete state read from the `onboarding_storage_done` /
  `onboarding_notifications_done` / `onboarding_first_upload_done` booleans on the user record, and
  the whole block is hidden once all three are true. Server-rendered (state reflects on next page
  load); done steps show struck-through with an sr-only "(done)" marker for screen readers,
  incomplete steps link to their page. New pure `app/core/onboarding.py` view-model
  (`build_onboarding_steps` / `onboarding_complete`) with a unit test, plus dashboard page tests
  for the show / mixed / hidden states. `onboarding_notifications_done` stays unchecked until
  Slice 7 wires notifications — no blocker. Deferred e2e coverage filed as #91.

- **Issue #55 implemented** — Slice 5.2 events dashboard filters, sort & search (branch
  `feature/slice-5.2-events-filters`, isolated worktree). `GET /api/v1/events` gains `type`,
  `date_from`/`date_to`, `q` (free-text over `description`/`raw_date_text`, case-insensitive), and
  `sort` (`asc`/`desc`, default unchanged) query params, all composing with each other and with
  pagination (`app.api.v1.events.list_user_events`); a new `list_user_event_types` backs the type
  dropdown with the user's full distinct type list, unaffected by the currently-applied filters.
  The dashboard's filter bar (type dropdown, two date pickers, search box, sort toggle) is
  HTMX-driven: the form and every pagination/sort link target `#dashboard-body` and
  `app.pages.dashboard` returns just that fragment (`partials/dashboard_body.html`) for
  `HX-Request` requests, so narrowing the table never triggers a full page reload. The filter form
  and events table were deliberately kept as **one** HTMX swap unit (not table-only) after manual
  browser QA caught a real bug: the sort-toggle link and a hidden `sort` field live in the form, so
  swapping only the table left them stale after a filter change, silently dropping the active sort
  (or vice versa) on the next click. Manual QA also caught FastAPI rejecting `date_from=`/`date_to=`
  (empty string, submitted by an untouched HTML date input) with a 422 before business logic ever
  ran; both routes now take these as `str | None` and parse via `app.api.v1.events.parse_date_param`
  (empty → `None`). Improvement pass: distinguishing "no events at all" from "no events match these
  filters" in the empty state, and the `list_user_event_types` dropdown. A multi-agent code review
  (correctness + cleanup + altitude/conventions angles) surfaced two further real bugs, both fixed
  before merge: `parse_date_param` let a malformed (non-empty, non-ISO) date crash with an unhandled
  500 instead of a clean 422, and the free-text search built its `ILIKE` pattern from the raw
  user input, so a literal `%`/`_` in the search box acted as a SQL LIKE wildcard instead of a
  literal character (both now escaped). Also applied: `_dashboard_url`'s four call sites
  (prev/next/sort-toggle/redirect) bound their shared filter kwargs once via `functools.partial`
  rather than repeating all four on every call, removing the risk of a future filter param being
  added to three call sites and missed on the fourth. Three lower-priority suggestions from the
  same review (shared query-param model between the two routes, further DB round-trip reduction,
  minor filter-bar UX polish) were filed as issues #96/#97/#98 (`modelsuggested`, `slice5`) rather
  than built now. `mypy --strict` and the full suite (286 tests) are green; manually verified live
  against a seeded dashboard (type filter, date range, search, sort toggle, and pagination all
  composing correctly, HTMX swaps confirmed via the network panel — no full-page navigation on any
  filter/sort/page interaction).

- **Issue #53 implemented** — Slice 4.2 live SSE pipeline progress page (branch
  `claude/admiring-carson-bzzfow`). A `/processing` progress page renders the 7 pipeline-step
  indicators and streams each step's status transition live via the HTMX SSE extension — no manual
  refresh — backed by `GET /api/v1/processing-runs/{id}/sse` (sse-starlette). Per #53's resolved
  decision the stream **polls the `processing_steps` rows** on a ~0.75s interval (no Redis pub/sub;
  the #52 pipeline runs in-process and writes those rows as it advances), emits a `step-N` event
  only when a step's status changes plus a `run-status` event on run-status change, and closes with
  a `done` event once the run reaches a terminal state. A successful run shows all 7 steps
  completing (Extract shows *skipped* for a `.txt`/`.csv`); a failed run highlights the failing step
  with a link toward the logs. The endpoint only exposes runs owned by the requesting user (404
  otherwise); the page falls back to the user's latest run when opened without `?run=`, and renders
  an already-finished run statically (no wasted SSE connection). Progress logic
  (`app/services/pipeline/progress.py`) is split from the router and the step badge is a shared
  Jinja partial used by both the first paint and the SSE fragments, so the two never drift.
  `PIPELINE_STEPS` in `app/services/pipeline/runner.py` is now the single source of truth for the 7
  steps. To exercise the flow in CI, `get_gemini_client` returns a canned `FakeGeminiClient` under
  `E2E_TEST_MODE` (the real `examples/` fixture is excluded from the deployed image) and the Upload
  page enables its dropzone in that mode. Tests: unit tests for `build_step_views`, the SSE
  generator (terminal success/failure) + endpoint auth/ownership, the page (empty state, live wiring,
  terminal-static render, cross-user isolation), and a Playwright `processing.spec.ts` that drives an
  upload and asserts the 7 steps advance live to a successful terminal state (in the `e2e-qa` suite).
  Added the `sse-starlette` dependency. **Human setup for reliable live progress:** Cloud Run "CPU
  always allocated" so the in-process pipeline task keeps running between the upload response and the
  SSE connection (already a #52 human-setup item).

### Fixed
- **Issue #43** — `POST /api/v1/auth/login` returned fastapi-users' bare `204 No Content`, so a
  plain full-page form POST (JS disabled / any non-fetch caller) was stranded on `/login` with no
  navigation — it only appeared to work because `login.html`'s client-side JS did the redirect
  (the same class of bug as #27, masked by JS). Now the endpoint itself `302`s to `/profile`,
  carrying the auth cookie across from the backend login response, so it's correct without relying
  on client JS. The Set-Cookie-carrying redirect used by both this flow and the Google callback
  (#27) was extracted into a shared `_redirect_with_login_cookie` helper. Branch
  `fix/auth-login-302-redirect`.
- **Issue #27** — Google sign-in hung on Google's consent page and never returned to the app
  (branch `fix/google-oauth-callback-redirect`). The `/api/v1/auth/google/callback` success path
  returned fastapi-users' default cookie login response — a bare `204 No Content` — so the
  full-page browser redirect from Google had nothing to navigate to. Now it `302`s to `/profile`,
  carrying the auth cookie across from the backend login response. Follow-up #43 filed for the
  same latent `204` shape on `POST /auth/login` (currently masked by client-side JS).
- **Post-merge prod deploy hotfixes** (direct to `main`, after PR #19): Alembic `%`-interpolation
  crash, Supabase IPv6 → pooler URL, and asyncpg `statement_cache_size=0` under PgBouncer
  transaction mode. `main` green; prod `/health` live. → [archive](changelog-archive.md#post-merge-prod-deploy-hotfixes-direct-to-main-after-pr-19-merged)

### Added
- **Issue #54 implemented** — Slice 5.1 events dashboard (branch
  `feature/slice-5.1-events-dashboard`). The first user-visible payoff of the whole pipeline:
  `GET /api/v1/events` (current user's events only, 50/page, newest `resolved_date_earliest` first
  — `NULLS LAST` so unresolved "TBC" dates sort to the bottom, not the top) and
  `DELETE /api/v1/events/{id}` (owner-scoped; 404 for both "doesn't exist" and "someone else's
  event", never confirming another user's event exists). New `app/core/calendar_url.py`:
  `build_google_calendar_url` (Google's well-known `render?action=TEMPLATE` all-day-event
  convention; title=description, dates=`resolved_date_earliest`/`+1day`, details=raw date text +
  `agreed_by`) and `build_google_tasks_url` (a **best-effort** `title`/`due` query string — Google
  has no officially documented Tasks quick-add URL scheme, unlike Calendar's; needs manual
  verification against a real account). Both return `None` for an event with no resolvable date.
  Dashboard page (`app/pages/dashboard.py` + `dashboard.html`) replaces the `/dashboard` placeholder
  with a real table (type, description, resolved date, raw date text, `agreed_by` chips, Calendar/
  Tasks links, Delete gated behind a DaisyUI confirm modal), pagination, and a total-count line.
  New migration `f6a7b8c9d0e1` — `ix_events_user_id_resolved_date_earliest_created_at` index
  covering the dashboard's exact filter+sort (the existing UNIQUE constraint doesn't help this
  query). Improvement pass: the index migration, redirecting an out-of-range `page` to the last
  valid one (API still returns an honest empty list for the same case), and the total-count line.
  `mypy --strict` clean; full suite green.
- **Issue #52 implemented** — Slice 4.1 upload page + 7-step processing pipeline (branch
  `feature/slice-4.1-upload-pipeline`). The end-to-end path from uploading a WhatsApp export to
  extracted events landing in the DB, on the #51 foundation. `POST /api/v1/upload` (`.txt`/`.zip`/
  `.csv`, 10 MB cap, bounded read) gates on a connected Google Drive, writes the file into the
  user's watch folder, records a `processing_runs` row, flips `onboarding_first_upload_done`, and
  kicks off the pipeline as an **in-process asyncio background task** (NOT Celery — per #52's
  resolved decision; the `app/worker.py` Celery stub stays dormant). The 7 steps
  (`app/services/pipeline/runner.py`) each write a `processing_steps` row: File Received → Extract
  (unzip `.zip`; skip `.txt`/`.csv`) → Filter by Date (default 7-day window, parameterised) → Call
  Gemini (fatal on error, no retry) → Parse LLM Response (Pydantic `ExtractedEvent`) → Deduplicate &
  Save (`UNIQUE(user_id, description, resolved_date)` + `resolved_date_earliest` via
  `parse_earliest_date`) → Notify. Gemini/parse failure ⇒ run `failed`, file → `failed/`, error in
  the step log, failure notification; a zero-new-events run is a success (file → `processed/`,
  "0 new events" notice). New stubbed **notification boundary**
  (`app/services/notifications/pipeline.py`: `NotificationSender` Protocol + `LoggingNotificationSender`
  + `FakeNotificationSender` + `get_pipeline_notifier`) — real Resend/Twilio delivery is Slice 7.
  New concrete **`GoogleDriveStorageProvider`** (`app/services/storage/google_drive.py`, Drive REST
  v3 via httpx, on-demand token refresh, `aclose()` to release its client) plus a `build_storage_provider`
  factory that returns the `FakeStorageProvider` under `E2E_TEST_MODE`. New **Upload page**
  (`app/pages/upload.py` + `upload.html`) with drag-and-drop + file picker, moved off the
  placeholder router. Tests: a stubbed pipeline integration test (all 7 steps, events in DB), unit
  tests for the date filter / notifier / Drive provider (via `httpx.MockTransport`), endpoint gating/
  validation/onboarding, page render, and a skip-unless-`GEMINI_API_KEY` real-Gemini e2e test.
  `mypy --strict` clean. Improvement pass: bounded upload read + provider `aclose()` implemented;
  Drive token-persistence deferred as #68. **Human setup before live:** (1) wire a real
  `GEMINI_API_KEY` secret into QA/prod; (2) enable Cloud Run "CPU always allocated"
  (`--no-cpu-throttling` and/or `min-instances=1`) so the background task keeps running after the
  HTTP response returns; (3) verify `GoogleDriveStorageProvider` against a real connected Drive
  account — its live behaviour (esp. the multipart upload encoding) is not exercised by CI.
- **Issue #51 implemented** — Slice 4.0 pipeline foundation (branch
  `feature/slice-4.0-pipeline-foundation`). The reusable, no-UI foundation the upload pipeline
  (#52) and SSE progress page (#53) build on. Three new models + one migration
  (`e5f6a7b8c9d0`, up/down round-trip verified against QA): `processing_runs`
  (status enum pending/in_progress/success/failed, `events_extracted_count`),
  `processing_steps` (status enum incl. `skipped`, `log_lines` JSONB), and `events`
  (`resolved_date_earliest` DATE nullable, `agreed_by` JSONB, and the
  `UNIQUE(user_id, description, resolved_date)` duplicate-detection constraint). New
  `app/core/date_parser.py::parse_earliest_date` — reduces the LLM's free-text `resolved_date`
  (single, timed, or comma-separated multi-date) to the earliest calendar date, `None` for
  "TBC"/unparseable; validated against all 22 real `resolved_date` values in
  `examples/example.lmmoutput.txt`. New `app/services/llm/gemini.py` — a `GeminiClient` Protocol
  with `GoogleGeminiClient` (google-genai SDK, blocking call off the event loop, **raises
  immediately on error — no retry**), `FakeGeminiClient` (returns a canned payload, records
  calls), and a `get_gemini_client` factory overridable in tests, mirroring the email sender.
  Added deps `google-genai` + `python-dateutil`; new optional `GEMINI_API_KEY` setting (empty
  default, clear error when used unset — tests inject the fake and never call the live API).
  Deferred model-suggested improvements filed as #64 (structured-JSON Gemini output) and #65
  (configurable model name). **Human setup before the pipeline (#52) runs live:** wire a real
  `GEMINI_API_KEY` secret into QA/prod.
- **Issue #49 implemented** — Slice 3.1 prompt page + endpoints (branch
  `feature/slice-3.1-prompt-page`). The Prompt page and the API behind it, end to end, letting a
  user view/edit/reset the extraction prompt. New `app/api/v1/llm_prompt.py`:
  `GET /api/v1/llm-prompt` (returns the user's stored prompt, falling back to
  `FACTORY_DEFAULT_PROMPT` without writing for a legacy account with no seeded row),
  `PUT /api/v1/llm-prompt` (saves edited text; trims + rejects blank via a Pydantic validator,
  20 000-char cap), and `POST /api/v1/llm-prompt/reset` (restores the factory default). Edit and
  reset both funnel through one `set_user_prompt` create-or-update helper (unique on `user_id`, so
  never a second row) — reset is just that helper called with the #48 constant. New Prompt page
  (`app/pages/prompt.py` + `templates/prompt.html`): a textarea editor with Save + Reset-to-Default
  buttons wired to the endpoints via Alpine `fetch`, seeded from the server with the current prompt;
  `/prompt` moves off the placeholder router onto its own real page (sidebar/nav unchanged). New
  Playwright spec `e2e/tests/prompt.spec.ts` (edit → save → reload → reset round-trip) added to the
  `e2e-qa` job. pytest covers the endpoints (GET default, PUT round-trip, blank rejection, reset,
  single-row invariant, auth-gating), a direct reset-logic unit test on `set_user_prompt`, and the
  page (render, saved-edit reflection, `x-data` truncation guard).
- **Issue #48 implemented** — Slice 3.0 prompt foundation (branch
  `feature/slice-3.0-prompt-foundation`). New `llm_prompts` table (`id`, `user_id` FK→users
  `ON DELETE CASCADE` **UNIQUE**, `prompt_text` TEXT NOT NULL, `created_at`/`updated_at`) via
  Alembic migration `d3e4f5a6b7c8`. A single factory-default extraction prompt constant
  (`app/core/prompts.py::FACTORY_DEFAULT_PROMPT`, verbatim from the issue, based on
  `examples/example.lmmoutput.txt`) is the shared source of truth for both seeding and the later
  Reset button (#49). Every new account is seeded with exactly one prompt row via
  `UserManager.on_after_register` (`app/auth/users.py`) — a single seam that fastapi-users fires
  from both `create()` (email/password) and `oauth_callback()` when it creates a *new* Google
  user, and never when Google is merely linked to an existing account, so both registration paths
  are covered with no double-seed. Covered by `tests/test_llm_prompt_model.py` (persistence +
  unique-per-user) and `tests/test_prompt_seed.py` (email/password seed, Google seed, no
  double-seed on link).
- **Issue #23 implemented** — Slice 1.8 Playwright E2E suite (branch
  `feature/slice-1-e2e-playwright`). New `e2e/` TypeScript suite drives the deployed QA app
  end-to-end: landing page, register→login→logout, forgot→reset password, profile edit +
  server-side dark-mode persistence, account deletion, and sidebar nav (order + unauthenticated
  redirect). Wired into `ci.yml` as an `e2e-qa` job that runs after `deploy-qa` and uploads the
  Playwright HTML report as an artifact on failure. Backed by a test-only endpoint
  `GET /api/v1/internal/e2e/last-reset-token` (module `app/api/v1/internal_e2e.py`) that mints a
  valid reset-token JWT, gated behind the new `E2E_TEST_MODE` setting — hidden from the OpenAPI
  schema and 404 everywhere except QA, where `ci.yml` sets `E2E_TEST_MODE=true` on the Cloud Run
  env (never prod). Google OAuth stays out of E2E scope (unreliable headlessly), covered by #13's
  backend tests. Making `e2e-qa` a required status check on `main` is a one-time branch-protection
  step to apply after this merges. **The suite caught a real production bug on first run**:
  `register.html`'s Alpine `x-data` attribute was truncated by an embedded `type="email"` double
  quote inside a JS comment, so the register component threw `Unexpected token ')'` and never
  initialised — the email/password register form was broken in real browsers, yet passed every
  `pytest` check (which only string-match HTML, never run the JS). Fixed the comment and added a
  pytest guard that parses the page as a browser would and asserts the `x-data` expression isn't
  truncated. Two E2E hardening improvements applied after an improvement-pass review: the
  account-deletion test now replays the exact pre-deletion cookie against `/api/v1/users/me` and
  asserts `401` (proving the token is dead server-side, not just dropped by the browser), and a
  pytest guard asserts `E2E_TEST_MODE` never appears in `deploy.yml` (prod). A separate
  reset-password raw-JSON UX gap surfaced during this work was flagged for a follow-up
  (Suggestions for Future Review #21).
- **Issue #47** — Slice 2.2 Google Drive OAuth connect/disconnect + onboarding flag (branch
  `feature/slice-2-gdrive-oauth`). The live Drive connect/disconnect flow layered onto the Storage
  tab. New `app/api/v1/storage_google_drive.py`: `POST /auth` (same-origin fetch → returns Google's
  consent URL as JSON + sets a CSRF cookie; drive scope, `access_type=offline`/`prompt=consent` for
  a refresh token; a fetch, not a top-level form POST, because the SameSite=Lax auth cookie
  wouldn't ride a POST navigation), `GET /callback` (validates CSRF, exchanges the code, stores the
  access + refresh tokens **encrypted at rest** via the #45 Fernet cipher, records the token expiry,
  and flips `onboarding_storage_done` on first connect), and `POST /disconnect`. Distinct from the
  Slice 1 *login* Google OAuth: this authorizes Drive file access, not identity. Storage tab gains
  Connect/Disconnect controls (Connect gated behind a saved folder path) + result banners.
  Improvement pass (all three user-selected): Disconnect now **revokes the token at Google**
  (best-effort — local clear still succeeds on revoke failure); `POST /auth` returns **409** for the
  no-config case instead of a 200-with-error body; and the access-token **expiry is persisted** (new
  nullable `oauth_token_expires_at` column + migration `b2c3d4e5f6a7`) for the Slice 4 pipeline to
  refresh proactively. Callback/disconnect are tested with a fake OAuth client + fake revoker + a
  throwaway cipher key (no live Google creds, no dependency on a configured `ENCRYPTION_KEY`). Live
  Google consent stays out of the Playwright suite (unreliable headlessly, per #23); the E2E spec
  covers the in-app Connect-control appearing after save. **Human setup before this works live:**
  (1) register the Drive callback redirect URI
  (`https://organizeme-<qa|prod>-…/api/v1/storage-config/google-drive/callback`) on the Google OAuth
  client and add the `https://www.googleapis.com/auth/drive` scope (a Google "restricted" scope —
  may need verification); (2) create the `ENCRYPTION_KEY` secret (flagged since #45) — the callback
  can't store tokens without it.
- **Issue #46** — Slice 2.1 Settings > Storage tab + storage-config read/write (branch
  `feature/slice-2-storage-tab`). The Storage tab plus its config endpoints, end to end, using the
  reserved `storage_configs` row from #45 — no live OAuth yet (that's #47). New
  `GET`/`PUT /api/v1/storage-config` (`app/api/v1/storage_config.py`): GET returns the current
  user's `{provider, folder_path, is_connected}` or an all-null unset state; PUT upserts the single
  per-user row (create-or-update, never a second row). The read schema deliberately exposes only
  those three fields and **never** echoes the encrypted credential columns; `is_connected` is
  derived from OAuth-token presence (always false this slice, surfaced now so the tab shows
  connection state without a later schema change). New Settings page (`app/pages/settings.py` +
  `templates/settings.html`) with a Storage tab: a provider dropdown whose Alpine.js `x-show`
  reveals the Google Drive fields (folder path + a "not connected yet" hint) and hides the
  Dropbox/S3 stubs until selected — no page reload. `/settings` moves off the generic placeholder
  router onto its own real page. Folder path is trimmed + rejected-if-blank server-side and
  round-trips through save→reload. New Playwright spec `e2e/tests/storage.spec.ts` (conditional
  fields + folder-path persistence) added to the `e2e-qa` job, plus pytest coverage for the
  endpoints, page render/gating, credential non-leak, and an `x-data` truncation guard.
- **Issue #45** — Slice 2.0 storage foundation (branch `feature/slice-2-storage-foundation`).
  First piece of Slice 2, pure plumbing that #46/#47 build on. Adds: the `storage_configs` table
  (model `app/models/storage_config.py` + migration — one row per user, unique on `user_id`,
  native `storage_provider` enum with lowercase labels via `values_callable`, nullable
  encrypted-at-rest credential columns); the `StorageProvider` ABC
  (`app/services/storage/base.py`: async `list_new_files`/`download_file`/`move_file`, plus a
  `RemoteFile` value object and `FileDestination` enum) with an in-memory `FakeStorageProvider`
  for tests; and Fernet-based credential encryption helpers (`app/core/security.py` —
  `CredentialCipher` with an injectable key + a `get_credential_cipher()` factory reading the new
  `ENCRYPTION_KEY` setting, which raises a clear error if unset). `ENCRYPTION_KEY` is wired into
  `ci.yml`/`deploy.yml` (empty until the secret is created; tests inject their own keys so they
  pass regardless). No user-facing surface; verified by unit tests (encryption round-trip,
  provider contract, model persistence + unique constraint). **Human setup:** create an
  `ENCRYPTION_KEY` GitHub secret (a `Fernet.generate_key()` value) and the matching Cloud Run env
  before #46/#47's credential-write paths go live.
- **Issue #10** — project scaffold + CI/CD (branch `feature/slice-1-scaffold-cicd`). → [archive](changelog-archive.md#issue-10--project-scaffold--cicd-pipeline-branch-feature-slice-1-scaffold-cicd)
- **Issue #11** — DB foundation: Supabase connection + `users` table (branch `feature/slice-1-db-foundation`). → [archive](changelog-archive.md#issue-11--db-foundation-supabase-connection--users-table-branch-feature-slice-1-db-foundation)
- **Issue #12** — email/password auth: register, login, logout (branch `feature/slice-1-auth-register-login`). → [archive](changelog-archive.md#issue-12--emailpassword-auth-register-login-logout-branch-feature-slice-1-auth-register-login)
- **Issue #13** — Google OAuth login (branch `feature/slice-1-google-oauth`). → [archive](changelog-archive.md#issue-13--google-oauth-login-branch-feature-slice-1-google-oauth)
- **Issue #14** — forgot/reset password (branch `feature/slice-1-forgot-reset-password`). → [archive](changelog-archive.md#issue-14--forgotreset-password-branch-feature-slice-1-forgot-reset-password-picked-up-ahead-of-13-per-direct-request)
- **Issue #15** — profile view/edit, dark mode, account deletion (branch `feature/slice-1-profile`). → [archive](changelog-archive.md#issue-15--profile-viewedit-dark-mode-account-deletion-branch-feature-slice-1-profile)
- **Issue #16** — public landing page (branch `feature/slice-1-landing-page`). → [archive](changelog-archive.md#issue-16--public-landing-page-branch-feature-slice-1-landing-page)
- **Issue #17** — sidebar shell + placeholder pages (branch `feature/slice1-sidebar-shell`).
  Persistent left sidebar for authenticated users (Dashboard → Upload → Processing → Logs →
  Prompt → Settings → Profile) via a new `authenticated_base.html` layout, driven by a single
  `NAV_ITEMS` source (`app/pages/nav.py`). Six new auth-gated placeholder routes
  (`/dashboard`, `/upload`, `/processing`, `/logs`, `/prompt`, `/settings`), each redirecting to
  `/login` when anonymous; `/profile` re-parented onto the same layout. Current route is marked
  `aria-current="page"`; sidebar includes a Log out action. Sidebar is not shown on public
  (landing/login/register) pages.
- **Docs restructure** — split `implementation-plan.md`'s 9 slice specs into self-contained
  per-slice files under `docs/features/original-organize-me/slices/`; `implementation-plan.md` is now a thin index + shared
  reference (stack, full schema, endpoint map, utilities, testing). Reduces per-issue context read
  during implementation.
- **GitHub issues #10–#17** — Slice 1 (Project Scaffold + Auth + CI/CD) broken into 8 TDD-sized,
  independently-gradable vertical slices and published to the OrganizeMe project: scaffold +
  CI/CD (#10), DB foundation (#11), email/password auth (#12), Google OAuth (#13),
  forgot/reset password (#14), profile + dark mode + account deletion (#15), landing page (#16),
  sidebar shell (#17). See `docs/features/original-organize-me/slices/slice-1.md` for the source scope.
- **GitHub issue #23** — Slice 1.8: automated Playwright E2E UX tests, added at the user's request
  to validate Slice 1's overall delivery. Targets the deployed QA Cloud Run instance via a new
  `e2e-qa` CI job (runs after `deploy-qa`, becomes a required check). Google OAuth is out of scope
  for E2E (unreliable headlessly) and stays covered by #13's backend tests. Forgot/reset-password
  is tested via a debug-only `GET /api/v1/internal/e2e/last-reset-token` endpoint (gated by
  `E2E_TEST_MODE`, wired to QA env only, 404s when unset). Blocked by #15/#16/#17.
- **`docs/features/original-organize-me/implementation-plan.md`** — full implementation design spec: confirmed stack, complete
  database schema (5 tables), API endpoint map (21 endpoints), 9 vertical implementation slices,
  key utilities, testing approach, prerequisites. Produced from a structured Q&A session.

### Fixed
- **Issue #26 fixed** — `/register`/`/login` showed a raw JSON response instead of a page
  (branch `fix/auth-form-json-response`):
  - Root cause: `app/templates/auth/register.html` and `login.html` used plain
    `<form method="post" action="...">` elements posting directly to
    `POST /api/v1/auth/register`/`/login`, both JSON API endpoints. A plain form POST makes the
    browser navigate to whatever the endpoint returns, so users landed on the raw `UserRead`
    JSON body (register) or a blank `204 No Content` page (login) instead of anywhere useful —
    these routes had only ever been exercised via httpx `TestClient` assertions, never a real
    browser form submission
  - Both forms now submit via Alpine.js `fetch()` (`@submit.prevent`), keeping the native
    `action`/`method` attributes as markup (not a functional no-JS fallback — the API returns
    JSON regardless of how it's posted to). `POST /register` doesn't itself log the user in, so a
    successful registration now immediately calls `POST /login` with the same credentials
    (auto-login, matching the Google sign-up path's instant-login UX — confirmed via user
    clarifying question) and redirects to `/profile`; `POST /login` redirects to `/profile` on
    success or shows an inline error banner on failure
  - Five improvements applied after comparing the implementation against issue #26: (1) the
    register page's error handling now also parses FastAPI's own 422 pydantic-validation-error
    array shape (`detail[0].msg`), not just the two JSON-object error shapes it already handled;
    (2) the previously separate, server-rendered `?error=google_auth_failed` Jinja banner (added
    in #13) was unified into the same Alpine `error` reactive state via a new `init()` lifecycle
    hook reading the query string client-side, on both `register.html` and `login.html`; (3) a
    `registered=1` info banner added to `login.html` for the case where auto-login unexpectedly
    fails immediately after a successful registration, so the user lands somewhere explained
    rather than a bare `/login`; (4) email inputs are trimmed of leading/trailing whitespace
    before submit on both forms, so a pasted email with stray whitespace doesn't produce a
    confusing validation error; (5) `aria-live="polite"` added to both alert banners so
    screen readers announce registration/login errors and the new info banner
  - Self-reviewed directly (no multi-agent `/code-review` dispatch) given the diff's size and
    complexity — 3 files, template/test changes only, no new business logic. One real finding
    survived review, documented as an accepted trade-off rather than fixed: removing the static
    Jinja `google_auth_failed` block in favour of Alpine's `init()` means a visitor with
    JavaScript disabled no longer sees that banner at all (it previously rendered unconditionally
    server-side); accepted because that same visitor's actual form submission was already broken
    without JS regardless — restoring the no-JS banner in isolation wouldn't restore a working
    no-JS auth flow, which is exactly the JSON-response problem this issue exists to fix. Flagged
    as a site-wide "does this app require JavaScript" decision that's never been written down
  - Issue #27 (Google sign-in hangs on Google's own consent page after clicking "Continue") was
    also filed from the same user report but is **not** part of this fix — diagnosed via browser
    automation that the initial redirect to Google is well-formed (correct `client_id`/
    `redirect_uri`/scope/signed state); completing the actual Google consent flow to reproduce
    further would require granting OAuth/SSO permissions on the user's behalf, which needs
    explicit authorization rather than being implied by a bug-investigation request — left open
    with clarifying questions asked in the issue

### Changed
- `docs/project-status.md` — updated phase, milestones, open decisions, and next steps to
  reflect completion of implementation planning

---

## 2026-06-30

### Added
- `docs/features/original-organize-me/technical-approach.md` — full technology stack evaluation: backend framework, frontend
  rendering strategy, database, background jobs, real-time pipeline progress, auth, notifications,
  deployment architecture (GCP Cloud Run), CI/CD pipeline, cost summary, and prerequisites
  checklist
- `docs/features/original-organize-me/prd.md` — full product requirements document based on 34-question grilling session
- `docs/project-status.md` — current project phase, milestones, and next steps
- `docs/changelog.md` — this file
- `examples/example.whatsapp.txt` — canonical WhatsApp export sample (630 lines)
- `examples/example.lmmoutput.txt` — canonical LLM output sample (22 extracted events, JSON)

