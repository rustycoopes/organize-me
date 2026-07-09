# OrganizeMe — Changelog

> Long-form implementation notes for completed issues live in
> [`changelog-archive.md`](changelog-archive.md). Keep this file lean: a short entry per change,
> with a pointer to the archive for full detail. Append new entries here; move them to the archive
> once they grow long or the issue is merged.

---

## [Unreleased]

### Added
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
  reset-password raw-JSON UX gap surfaced during this work is recorded in `project-status.md`
  (Suggestions for Future Review #21) for a follow-up.
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
  per-slice files under `docs/slices/`; `implementation-plan.md` is now a thin index + shared
  reference (stack, full schema, endpoint map, utilities, testing). Reduces per-issue context read
  during implementation.
- **GitHub issues #10–#17** — Slice 1 (Project Scaffold + Auth + CI/CD) broken into 8 TDD-sized,
  independently-gradable vertical slices and published to the OrganizeMe project: scaffold +
  CI/CD (#10), DB foundation (#11), email/password auth (#12), Google OAuth (#13),
  forgot/reset password (#14), profile + dark mode + account deletion (#15), landing page (#16),
  sidebar shell (#17). See `docs/slices/slice-1.md` for the source scope.
- **GitHub issue #23** — Slice 1.8: automated Playwright E2E UX tests, added at the user's request
  to validate Slice 1's overall delivery. Targets the deployed QA Cloud Run instance via a new
  `e2e-qa` CI job (runs after `deploy-qa`, becomes a required check). Google OAuth is out of scope
  for E2E (unreliable headlessly) and stays covered by #13's backend tests. Forgot/reset-password
  is tested via a debug-only `GET /api/v1/internal/e2e/last-reset-token` endpoint (gated by
  `E2E_TEST_MODE`, wired to QA env only, 404s when unset). Blocked by #15/#16/#17.
- **`docs/implementation-plan.md`** — full implementation design spec: confirmed stack, complete
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
    in `docs/project-status.md`'s Suggestions for Future Review as a site-wide "does this app
    require JavaScript" decision that's never been written down
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
- `docs/technical-approach.md` — full technology stack evaluation: backend framework, frontend
  rendering strategy, database, background jobs, real-time pipeline progress, auth, notifications,
  deployment architecture (GCP Cloud Run), CI/CD pipeline, cost summary, and prerequisites
  checklist
- `docs/prd.md` — full product requirements document based on 34-question grilling session
- `docs/project-status.md` — current project phase, milestones, and next steps
- `docs/changelog.md` — this file
- `examples/example.whatsapp.txt` — canonical WhatsApp export sample (630 lines)
- `examples/example.lmmoutput.txt` — canonical LLM output sample (22 extracted events, JSON)

