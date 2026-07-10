# OrganizeMe — Project Status

**Last updated:** 2026-07-10 (issue #144 — notification delivery visibility fix)

---

## Current Phase

**Slice 1 in progress.** All prerequisites provisioned (issues #1–#9, closed). Slice 1 broken into 8 TDD-sized issues (#10–#17), plus a 9th (#23) added 2026-07-02 to validate the whole slice with automated Playwright E2E tests. Issues #10 (project scaffold + CI/CD, PR #18), #11 (DB foundation, PR #19), #12 (email/password auth, PR #20), #13 (Google OAuth login, PR #22), #14 (forgot/reset password, PR #21), #15 (profile — view/edit, dark mode, account deletion, PR #24), and #16 (landing page, PR #25) are all merged into `main`; `ci.yml` (QA) and `deploy.yml` (prod) run green, and `/health`, `/`, `/register`/`/login` (incl. Google sign-in), `/forgot-password`/`/reset-password`, `/profile`, and `/api/v1/users/me` are confirmed live on both Cloud Run services. Two live bugs reported by the user after #16 shipped: `/register`/`/login`'s plain HTML forms landed users on a raw JSON response instead of any page (filed as issue #26, fixed on branch `fix/auth-form-json-response`, PR #28) and Google sign-in hanging on Google's consent page (filed as issue #27). #26 is merged (PR #28). #27 root cause found and fixed on branch `fix/google-oauth-callback-redirect`: the `/api/v1/auth/google/callback` success path returned fastapi-users' bare `204 No Content`, so the full-page redirect from Google had nothing to navigate to — now `302`s to `/profile` with the auth cookie. Follow-up #43 (same latent `204` on `POST /auth/login`, masked today by client-side JS) is now fixed on branch `fix/auth-login-302-redirect`: the endpoint itself `302`s to `/profile` carrying the auth cookie, and the Set-Cookie-carrying redirect shared with the Google callback was extracted into a `_redirect_with_login_cookie` helper. #27 has since merged (PR #44). Issue #17 (sidebar shell + placeholder pages) merged into `main` (PR #50). Issue #23 (Playwright E2E) — the last Slice 1 issue — is now implemented on branch `feature/slice-1-e2e-playwright`: an `e2e/` Playwright/TypeScript suite driving the deployed QA app (landing, register→login→logout, forgot→reset password, profile edit + dark-mode persistence, account deletion, sidebar nav), wired into `ci.yml` as an `e2e-qa` job after `deploy-qa`, backed by a test-only `GET /api/v1/internal/e2e/last-reset-token` endpoint gated behind a new `E2E_TEST_MODE` flag (QA-only, 404 + schema-hidden elsewhere). With #23, Slice 1 is functionally complete.

**Slice 2 (Google Drive storage) done.** Slice 1 fully drained. Issue #45 (storage foundation, PR #58), #46 (Settings > Storage tab + `GET`/`PUT /api/v1/storage-config`, PR #59), and #47 (Slice 2.2 — Google Drive OAuth connect/disconnect + onboarding flag, PR #60) are all merged. #47 added `POST /auth` → Google consent URL (drive scope, offline/refresh), `GET /callback` (stores access+refresh tokens encrypted at rest + token expiry, flips `onboarding_storage_done`), `POST /disconnect` (revokes at Google then clears), plus Storage-tab Connect/Disconnect controls, Google-side token revocation, a 409 for the no-config case, and a persisted `oauth_token_expires_at` (migration `b2c3d4e5f6a7`). **Human setup before it works live:** (1) register the Drive callback redirect URI + add the `drive` scope on the Google OAuth client (a "restricted" scope, may need verification); (2) create the `ENCRYPTION_KEY` secret (a `Fernet.generate_key()` value; wired into `ci.yml`/`deploy.yml` since #45, empty until then) — the callback can't store tokens without it.

**Slice 3 (LLM Prompt page) in progress.** Slice 2 fully drained. Issue #48 (Slice 3.0 — prompt foundation) is **merged** (PR #62): the `llm_prompts` table (one row per user, unique on `user_id`, `prompt_text` NOT NULL; migration `d3e4f5a6b7c8`), a single factory-default extraction-prompt constant (`app/core/prompts.py::FACTORY_DEFAULT_PROMPT`) shared by seeding and reset, and seed-on-registration via `UserManager.on_after_register` (one seam covering email/password + new-Google-user creation, not Google-link, so no double-seed). Issue #49 (Slice 3.1 — prompt page + endpoints), the last Slice 3 issue, is implemented on branch `feature/slice-3.1-prompt-page` in an isolated worktree: `GET`/`PUT /api/v1/llm-prompt` + `POST /api/v1/llm-prompt/reset` (`app/api/v1/llm_prompt.py`), with edit and reset funnelling through one `set_user_prompt` create-or-update helper (reset = that helper called with the factory constant) and GET falling back to the factory default for a legacy account with no seeded row; a Prompt page (`app/pages/prompt.py` + `prompt.html`) with a textarea editor + Save + Reset-to-Default wired to the endpoints via Alpine `fetch`, moved off the placeholder router. Playwright `prompt.spec.ts` covers the edit → save → reload → reset round-trip. With #49, Slice 3 is functionally complete.

**Slice 4 (upload + processing pipeline) complete.** Slice 3 fully drained (#48 + #49 merged). Issue #51 (Slice 4.0 — pipeline foundation), the no-UI base the rest of Slice 4 builds on, is implemented on branch `feature/slice-4.0-pipeline-foundation` in an isolated worktree: the `processing_runs` / `processing_steps` / `events` tables (migration `e5f6a7b8c9d0`, incl. the `UNIQUE(user_id, description, resolved_date)` duplicate-detection constraint and the `resolved_date_earliest` DATE column), `app/core/date_parser.py::parse_earliest_date` (free-text `resolved_date` → earliest date, validated against all 22 real values in `examples/example.lmmoutput.txt`), and `app/services/llm/gemini.py` (a `GeminiClient` Protocol + real google-genai client that fails immediately with no retry + an injectable `FakeGeminiClient`, mirroring the email-sender seam). Verified by unit tests + `mypy --strict`; no user-facing surface. Deferred model-suggested ideas filed as #64/#65. #52 (upload page + 7-step pipeline) is implemented on branch `feature/slice-4.1-upload-pipeline` in an isolated worktree: `POST /api/v1/upload` (`.txt`/`.zip`/`.csv`, 10 MB cap, gated on a connected Google Drive) writes the file to the watch folder, records a `processing_runs` row, flips `onboarding_first_upload_done`, and runs the 7-step pipeline as an **in-process asyncio background task** (NOT Celery — per #52's resolved decision) that writes a `processing_steps` row per step and lands events in the DB (Gemini failure ⇒ run `failed`, file → `failed/`, failure notice; zero-new-events ⇒ success + "0 new events"). New stubbed notification boundary (`app/services/notifications/pipeline.py`, real delivery is Slice 7), concrete `GoogleDriveStorageProvider` (Drive REST v3, fake under `E2E_TEST_MODE`), and a drag-and-drop Upload page. Stubbed pipeline integration test + unit tests (date filter, notifier, Drive via `MockTransport`, endpoint gating, page) + a skip-unless-`GEMINI_API_KEY` real-Gemini e2e test; `mypy --strict` clean. Improvement pass applied (bounded upload read, provider `aclose()`); Drive token-persistence deferred as #68. #53 (live SSE progress page) is implemented on branch `claude/admiring-carson-bzzfow`: a `/processing` page renders the 7 step indicators and streams each step's status transition live via the HTMX SSE extension, backed by `GET /api/v1/processing-runs/{id}/sse` (sse-starlette) which **polls the `processing_steps` rows** (~0.75s; no Redis pub/sub — the #52 pipeline runs in-process and writes those rows) and closes on a terminal state. Success shows all 7 steps done (Extract *skipped* for `.txt`/`.csv`); failure highlights the failing step with a link toward the logs. The stream only exposes runs owned by the requester (404 otherwise); the page falls back to the latest run without `?run=` and renders a finished run statically (no wasted stream). `get_gemini_client` returns a canned fake under `E2E_TEST_MODE` so the Playwright `processing.spec.ts` drives upload → pipeline → SSE to success in CI without a live key. With #53, Slice 4 is functionally complete. **Human setup before Slice 4 runs fully live:** (1) a real `GEMINI_API_KEY` secret in QA/prod; (2) Cloud Run "CPU always allocated" so the background task survives past the HTTP response; (3) manual QA of `GoogleDriveStorageProvider` against a real connected account (its live behaviour isn't exercised by CI). All three tracked in issue #72 with detailed steps.

**Slice 5 (events dashboard) complete.** Slice 4 fully drained. Issue #54 (Slice 5.1 — events dashboard table + calendar/tasks links + delete), the first user-visible payoff of the whole pipeline, is implemented on branch `feature/slice-5.1-events-dashboard` in an isolated worktree: `GET /api/v1/events` (50/page, newest `resolved_date_earliest` first, `NULLS LAST` so unresolved dates sort to the bottom) and `DELETE /api/v1/events/{id}` (owner-scoped, 404 either way for a non-owned/nonexistent id). New `app/core/calendar_url.py` — `build_google_calendar_url` (the well-known Calendar "quick add" URL convention) and `build_google_tasks_url` (a **best-effort, unverified** URL scheme — Google has no documented Tasks equivalent). Dashboard page replaces the `/dashboard` placeholder: table with Calendar/Tasks links + a DaisyUI-confirm-gated Delete, pagination, and a total-count line. New migration `f6a7b8c9d0e1` adds an index covering the dashboard's filter+sort. Improvement pass: the index migration, redirecting an out-of-range page to the last valid one, and the total-count line. `mypy --strict` clean; full suite green. **Manual verification needed:** whether Google's Tasks frontend actually honours the pre-fill query params (flagged in the PR, same class of caveat as #52's Drive verification). Issue #55 (Slice 5.2 — filters, sort & search) is implemented on branch `feature/slice-5.2-events-filters`, in an isolated worktree: `GET /api/v1/events` gains `type`/`date_from`/`date_to`/`q`/`sort` query params, all composing with each other and with pagination; a new `list_user_event_types` backs the type dropdown. The dashboard's filter bar (type dropdown, date-range pickers, search box, sort toggle) is HTMX-driven — the form and every pagination/sort link swap `#dashboard-body` in place via `partials/dashboard_body.html`, so no filter/sort/page interaction triggers a full page reload. Manual browser QA (not just pytest) caught two real bugs before merge: FastAPI 422'd on the empty-string `date_from`/`date_to` an untouched HTML date input actually submits (fixed via `parse_date_param`, both routes now take these as `str | None`), and the sort-toggle link/hidden `sort` field lived in the filter form outside the original table-only swap target, going stale after a filter change (fixed by making the form + table one swap unit, `partials/dashboard_body.html`, rather than table-only). A code-review pass then caught two more: a malformed date string crashing with a 500 instead of a 422 (`parse_date_param` now catches `ValueError`), and unescaped `%`/`_` in the free-text search acting as SQL LIKE wildcards (now escaped) — plus a DRY cleanup binding the four `_dashboard_url` call sites' shared filter kwargs via `functools.partial`. Three lower-priority review suggestions deferred to issues #96/#97/#98 (`modelsuggested`). `mypy --strict` clean; full suite (286 tests) green. #56 (Slice 5.3 — onboarding checklist) is next. Issue #113 (reviewed flag + filter) implemented on branch `feature/slice-5-events-reviewed-flag`, in an isolated worktree: new `reviewed` boolean column on `events` (migration `a7b8c9d0e1f2`, default `false`) plus a partial index `ix_events_user_id_unreviewed_sort` (migration `b8c9d0e1f2a3`, `WHERE reviewed = false`) covering the now-default `reviewed = false` query, a `show_reviewed` param on `GET /api/v1/events`/`/dashboard` (default `false`, composes with the existing filters), and a new `PATCH /api/v1/events/{id}` endpoint (owner-scoped via shared `get_owned_event`, same 404-either-way semantics as `DELETE`) to toggle it. Dashboard gets a per-row checkbox (Alpine `fetch` PATCH, reverts on failure) and a "Show reviewed" filter checkbox. A code-review pass caught two real bugs pre-merge: hand-written JS that removed a reviewed row and decremented a count client-side desynced from the server at pagination boundaries (fixed by re-rendering `#dashboard-body` via `htmx.ajax()` after a successful PATCH, reusing the page's existing swap mechanism), and `has_active_filters` didn't count the default reviewed-hiding as a filter, so an all-reviewed returning user saw a misleading "No events yet" (fixed using the already-fetched `event_types` list as a free "has any events at all" signal). Also fixed: a redundant `db.refresh()` and duplicated owner-lookup code. 15 new tests; full suite green; `mypy --strict` clean. Two suggestions deferred to #135/#136 (`modelsuggested`).

**Slice 6 (processing history + logs) complete.** Slice 5 fully drained. Issue #83 (Slice 6.1 — processing history list page) is implemented on branch `feature/slice-6.1-logs-page` and merged into `main`. Issue #84 (Slice 6.2 — run detail page + logs viewer) is implemented on branch `feature/slice-6.2-run-detail` (PR #107) and merged into `main`. New endpoints: `GET /api/v1/processing-runs/{id}` (run detail with steps, JSON), `GET /api/v1/processing-runs/{id}/logs` (paginated logs JSON), `GET /api/html/processing-runs/{id}/logs` (HTMX HTML partial). New page `/processing-runs/{id}` displays run metadata, 7 pipeline steps with status indicators, and expandable per-step logs (searchable, paginated 50/page via HTMX). Reuses step rendering from `/processing` page. User scoping (404 for non-owners). Comprehensive test coverage: 14 new tests, all 39 processing tests pass, no regressions. New schemas: `ProcessingStepRead`, `ProcessingRunDetailRead`, `ProcessingLogLineRead`. With #84, Slice 6.2 is functionally complete. Issue #85 (Slice 6.3 — searchable log filter + log download) is implemented on branch `feature/slice-6.3-log-search-download`, in an isolated worktree: the live HTMX search filter already existed from #84, so the remaining scope was `GET /api/v1/processing-runs/{id}/logs/download` (a run's full structured logs across all steps as a downloadable JSON file, `Content-Disposition: attachment`) plus a "Download logs" link on the run detail page. Improvement pass: fixed a pre-existing bug where log search escaped `%`/`_` as if for a SQL `LIKE` pattern despite matching being a plain substring check, which silently broke searches containing those characters, and deduplicated the search/pagination logic (API route + HTMX partial) into a shared `app/services/processing_logs.py` helper. Lower-priority follow-up (download filename using the run's original filename) filed as #118 (Intake). With #85, Slice 6 is complete.

**Slice 7.1 (email notifications) implemented.** Slice 6 fully drained. Issue #86 (Slice 7.1 — branded email notifications) is implemented on branch `feature/slice-7.1-email-notifications`: real `NotificationSender` implementation (`RealNotificationSender` in `app/services/notifications/sender.py`) replaces the logging stub behind the same protocol. Sends branded HTML emails on processing-run completion (success, zero-event, failure) using Jinja2 templates with inline CSS. Two templates (`success.html.j2`, `failure.html.j2`) render the OrganizeMe header, event summary or error details, and appropriate CTA links (dashboard for success, log page for failure). Respects the `user.notification_email` flag (stored at user registration, defaults to `True`). New config: `BASE_URL` (defaults to `https://organize-me.app`, overrideable for local dev). Updated factory `get_pipeline_notifier()` wires the real sender without touching the pipeline itself. Comprehensive test coverage: 7 tests verify success/zero-event/failure emails, the off-flag behavior, unknown-user graceful handling, and link correctness. Template environment cached at class level for performance (avoid re-reading filesystem on each send). SMS support deferred to Slice 7.2. Slice 7.1 is functionally complete.

**Slice 7.2 (SMS notifications) implemented.** Issue #87 (Slice 7.2 — SMS notifications via Twilio) is implemented on branch `feature/slice-7.2-sms-notifications`: new `app/services/notifications/sms.py` mirroring the `EmailSender` Protocol pattern — an `SmsSender` Protocol, a real `TwilioSmsSender` (blocking Twilio REST client run via `asyncio.to_thread`, same pattern as `ResendEmailSender`), and a `FakeSmsSender` test double. `RealNotificationSender` (`app/services/notifications/sender.py`) now sends both channels independently per run: email gated on `user.notification_email`, SMS gated on `user.notification_sms` **and** a non-empty `user.phone_number` — if SMS is toggled on but no phone number is on file, the send is silently skipped (info-level log only, no error surfaced, run unaffected). Success SMS carries the event count + dashboard link; failure SMS carries the error summary + link to the run's log page; zero-event runs use the success copy with count 0. New config: `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_PHONE_NUMBER` (empty defaults, same pattern as `RESEND_API_KEY`/`GEMINI_API_KEY` — `TwilioSmsSender` only needs real values once SMS is actually exercised live; `.env.local.example` already had a `# --- SMS (Twilio) ---` section stubbed out for this). New `twilio` dependency in `pyproject.toml` (with a `[[tool.mypy.overrides]]` entry — the package ships no type stubs). Improvement pass: `TwilioSmsSender.send()` now raises a clear `RuntimeError` naming the missing env vars if Twilio credentials are unset, rather than surfacing a confusing Twilio SDK error (mirrors the `get_credential_cipher`/`GoogleGeminiClient` "fail loud with a clear message" convention) — caught by `RealNotificationSender`'s existing catch-all so a misconfigured environment still can't block a run. Proactively wired `TWILIO_ACCOUNT_SID`/`TWILIO_AUTH_TOKEN`/`TWILIO_PHONE_NUMBER` into `ci.yml`/`deploy.yml`'s Cloud Run env-vars (same gap class as #10/#12 that the Slice 1 forgot-password work flagged). A multi-angle code review (correctness + cleanup/reuse + efficiency + altitude + conventions) surfaced one real efficiency gap, fixed before merge: `TwilioSmsSender` was constructing a fresh `twilio.rest.Client` (and its underlying `requests.Session`/connection pool) on every send — now cached at class level, mirroring `RealNotificationSender`'s existing class-level Jinja env cache. Three lower-priority review suggestions deferred to `modelsuggested` issues: E.164 phone-number validation on the Profile page (#120), generalizing the per-channel dispatch in `RealNotificationSender` to reduce email/SMS duplication and give `ResendEmailSender` the same clear-error-on-unset-config guard `TwilioSmsSender` has (#124), and sending email + SMS concurrently via `asyncio.gather` instead of sequentially (#125). 9 new tests (including one exercising the new config-validation error, which briefly caught this worktree's `.env.local` carrying real Twilio credentials — the test now explicitly nulls the Twilio fields via `Settings(...)` rather than relying on env state) cover success/zero-event/failure SMS, the toggle-off case, the missing-phone-number silent-skip case, and unknown-user handling; full suite (353+ tests) + `mypy --strict` green. **Human setup before it works live:** a real Twilio account SID/auth token/from-number in QA/prod secrets (tracked alongside the other Slice 4/7 live-config gaps in issue #72's pattern — no blocking dependency on it for this issue to merge). Slice 7.2 is functionally complete; Slice 7.3 (Settings > Notifications tab) is next.

**Slice 7.3 (#88, Settings > Notifications tab) paused, picked up #111 instead.** #88 turned out
to be blocked in practice: its acceptance criteria require an integration test proving the SMS
toggle blocks Twilio sends, but Slice 7.2 (#87, SMS via Twilio) was `In Progress` under a
concurrent session with no SMS sender in the codebase yet. Rather than build the toggle UI/schema
now and leave the SMS half of the test unwritten, picked up #111 (Slice 7 `future`/enhancement
tier, no cross-issue blocker) instead and left #88 in `Todo` for a session after #87 lands.
**Issue #111 (redesign `/logs` as an HTMX-driven spreadsheet grid) implemented** on branch
`feature/logs-grid-redesign`, in an isolated worktree. `GET /api/v1/processing-runs` gains
`status`/`date_from`/`date_to`/`sort_by`/`sort_dir` query params (composing with each other and
pagination, mirroring the dashboard's #55 filter pattern) and a new `detail_summary` field per
run (first error line for a `failed` run, falling back through any captured log line to a fixed
placeholder if no step itself was marked failed; an `"N log lines"` count otherwise — computed
from the page's already-fetched steps, no per-row queries). The `/logs` page's filter form
(Status + date range) and three sortable column headers (Date/Filename/Status, `aria-sort` +
▲/▼) swap `#logs-body` in place via new `partials/logs_body.html`/`partials/logs_grid.html`. Each
row is a full, keyboard-operable click target to `/processing-runs/{id}`. 27 tests; `mypy
--strict` clean on the changed files and on the full `app`/`tests` tree. Improvement pass:
keyboard accessibility for row navigation, `aria-sort`, and the FAILED-with-no-failed-step
detail-summary fallback. Deferred ideas (human-friendly date formatting, free-text search, a
step-breakdown alternative for Details) filed as `modelsuggested` issues rather than built now.
**Issue #88 (Slice 7.3 — Settings > Notifications tab) implemented** on branch
`feature/slice-7.3-notifications-tab`, in an isolated worktree. A new Notifications tab sits
alongside Storage on `/settings` (Alpine-driven client-side tab switching within one card), with
independent email/SMS toggles backed by the existing `PATCH /api/v1/users/me` (no new endpoint) —
`UserRead`/`UserUpdate` gained `notification_email`/`notification_sms` (mirroring the
`dark_mode` NOT-NULL/explicit-null-rejection pattern). Email toggle is disabled unless
`user.email` is set (always true in practice today, kept per the acceptance criteria for
defensiveness); SMS toggle is disabled unless `user.phone_number` is set, with hint text either
way and a read-only display of the current email/phone linking to `/profile`. Saving flips
`onboarding_notifications_done = True` the first time either toggle is included in a PATCH
payload (idempotent on repeat saves). The "toggle off ⇒ channel doesn't send" criterion is
covered on both sides: email by Slice 7.1's existing disabled-user test, and SMS by a new test
added once Slice 7.2 (#87, merged to `main` the same day as this work) landed the SMS sender —
closing the gap `modelsuggested` issue #129 had flagged while #87 was still on its own branch.
Also filed #128 (`modelsuggested`): both Settings tabs hand-roll the same card/tab markup instead
of the shared `card_page` macro — a structural cleanup deferred to avoid scope creep into the
already-shipped Storage tab. New Playwright `e2e/tests/notifications.spec.ts` covers the
disabled→enabled SMS toggle transition (set phone in Profile, return to Settings) and an
email-toggle save/reload round-trip. 17 new/updated backend tests (schema, API incl. onboarding-
flag idempotency, page render/disabled-state/round-trip); full suite + `mypy --strict` green.
A code-review pass caught and fixed three real issues: a stale onboarding-checklist link
(`/profile` → `/settings`), a redundant second DB commit for the onboarding flag (folded into the
existing one), and a tab-bar accessibility regression (static `aria-selected`/`tab-active`
restored for pre-hydration clients). A fourth candidate fix from that pass - rejecting a channel
toggle turned on with no matching contact info - was tried and reverted after breaking `e2e-qa`:
it contradicted Slice 7.2's already-shipped design (silent-skip on a missing phone number, not an
error; `notification_sms` defaults `True` regardless of phone). Also fixed two Playwright locator
collisions in `storage.spec.ts`/`notifications.spec.ts` - both Settings tab panels stay in the DOM
(only `x-show`-hidden), so an unscoped `form button[type="submit"]` matched two buttons; scoped to
new `#storage-tab-panel`/`#notifications-tab-panel` ids. With #88, Slice 7 has only #128
(tab/card-shell refactor) outstanding as a `modelsuggested` follow-up.

**Issue #115 (verify onboarding checklist hides once all steps complete) verified.** #115 was a
verification task blocked on #88 (Notifications tab) — now shipped — which was the only piece
missing to flip `onboarding_notifications_done` outside a test. Traced the mechanism end to end:
`app/core/onboarding.py::onboarding_complete()` (all three `onboarding_*_done` booleans true) and
the dashboard template's `{% if not onboarding_complete %}` were already correct, and #88's own
review pass had already fixed the stale `/profile` link on the notifications step — so there was
no code to fix, only verification to add. Existing coverage (`test_onboarding_checklist.py`'s
`onboarding_complete()` unit tests, `test_dashboard_page.py`'s show/mixed/hidden page tests) already
exercised the flag logic directly, but by *setting the User booleans on the DB row*, not by driving
the endpoints that are supposed to set them — so a regression in, say, the upload endpoint's
onboarding-flip logic wouldn't have been caught by the "hides" test. Added
`test_dashboard_hides_onboarding_checklist_after_completing_flow_through_real_endpoints` to
`tests/test_dashboard_page.py`: walks a fresh user through all three real endpoints (Google Drive
OAuth connect via the existing fake-client pattern from `test_storage_google_drive.py`, the
notification-prefs `PATCH /api/v1/users/me`, and `POST /api/v1/upload` with a faked storage
provider/scheduler) and asserts the checklist is gone from the next `/dashboard` load. A true
Playwright e2e version of the full flow remains out of scope, per the standing #23 decision to keep
real Google OAuth out of the e2e suite (also noted in #91, the already-tracked and still-open
`modelsuggested` issue for onboarding e2e coverage) — the new pytest integration test is the
strongest regression coverage achievable without relitigating that decision. No code changes; full
suite + `mypy --strict` green.

**Issue #110 (Import pending files button) implemented** on branch
`feature/slice-7-import-pending-files`, in an isolated worktree. New `POST
/api/v1/import-pending-files` (`app/api/v1/import_pending_files.py`) scans the user's connected
storage watch folder via the existing `StorageProvider.list_new_files()` (already excludes
`processed/`/`failed/` by contract — no new dedup bookkeeping needed) and creates one
`processing_runs` row per pending file. Resolved design decision (asked and confirmed with the
user before building): files are processed **sequentially**, one after another in a single
background task, not fire-and-forget-per-file like the manual upload path — added
`PipelineScheduler.schedule_batch()`/`BackgroundPipelineScheduler._run_batch()` alongside the
existing single-file `schedule()`/`_run()` in `app/api/v1/upload.py` for this. The endpoint returns
only the *first* file's `run_id`, so the client follows it to `/processing` exactly like a manual
upload; the rest of the batch keeps processing in the background and is visible afterward via the
`/logs` history page rather than a second live SSE stream — the simplest workable v1 UX given the
existing single-run progress page, with the alternative (auto-advancing the live view across a
whole batch) explicitly deferred rather than built now. New `get_import_storage` dependency has no
ephemeral-storage fallback (unlike uploads) since there's no watch folder to scan without a real
connected provider — 400 `storage_not_connected` if none. New shared `is_drive_connected()` helper
in `app/api/v1/storage_config.py` (extracted from `app/pages/upload.py`'s pre-existing inline
check) backs the Import button's disabled state on both `/upload` and `/dashboard` via one new
`partials/import_pending_button.html`, so the two pages share one Alpine fetch/redirect
implementation instead of duplicating it. New Playwright `e2e/tests/import-pending-files.spec.ts`
covers what's deterministic under `E2E_TEST_MODE` (the button is enabled, and clicking it
surfaces "no pending files" — `E2E_TEST_MODE`'s per-request fake storage provider has no
persistence across requests, so genuinely populating "pending files" needs a real connected
Drive account, out of e2e scope per the standing #23 decision). Improvement pass (before review):
importing also flips `onboarding_first_upload_done`, matching manual upload, so a user who only
ever imports (never uses the Upload page directly) doesn't have that onboarding step stuck
incomplete forever. A multi-angle code review pass then caught and fixed three real issues,
independently confirmed by multiple review angles: (1) `_run_batch`'s per-file `except` block
logged an unexpected failure but never rolled back the shared session, so one file's unhandled
error would poison every remaining file in the batch (a real correctness bug contradicting the
method's own "one failure doesn't stop the batch" docstring claim) — fixed by rolling back before
continuing the loop; (2) `get_import_storage` re-derived "is Drive connected" inline instead of
calling the `is_drive_connected()` helper this same diff introduced specifically to prevent that
duplication — fixed by extracting a shared `config_is_connected()` predicate both now call; (3) a
dead `db.refresh()` loop after `db.commit()` issued one wasted SELECT per pending file, even though
`get_db`'s sessionmaker uses `expire_on_commit=False` (nothing is expired, so nothing needs
refreshing) — removed. Also fixed a minor `StorageProvider` HTTP-client leak on the
no-pending-files early-return path, and updated README.md (a repo CLAUDE.md requirement the diff
had initially missed). One lower-priority finding (a double-click/multi-tab race that could enqueue
duplicate batches — same class of gap the pre-existing single-file upload endpoint already has, and
backstopped by the `events` table's existing dedup constraint) deferred as `modelsuggested` #133;
auto-advancing `/processing` across a whole batch instead of only showing the first file live
deferred as `modelsuggested` #132. No dedicated automated test for the session-rollback fix itself:
`BackgroundPipelineScheduler`'s background-task methods open their own DB session via `get_engine()`
directly (bypassing the request-scoped `get_db` override), which the test suite's SAVEPOINT-based
isolation (each test's writes live in a rolled-back transaction on one connection) can't observe —
the same reason no test in the codebase exercises `_run`/`schedule` directly either; the fix is the
standard, well-understood SQLAlchemy rollback-after-failed-flush pattern. 9 new/updated backend
tests; full suite + `mypy --strict` green.

**Issue #112 (log notification silent modes as warnings) implemented** on branch
`feature/slice-7-notify-silent-mode-warnings`, in an isolated worktree. New
`_silent_notification_modes_warning()` in `app/services/pipeline/runner.py` runs during the Notify
step (step 7, shared by both the success and failure paths via the existing `_notify()` helper) and
adds one extra log line — `"Warning: disabled email; disabled SMS"` / `"Warning: no phone
number"` etc., only the modes actually silent, omitted entirely when every configured channel is
live — to the step's existing `"Notified user: ..."` log line. Deliberately mirrors
`RealNotificationSender`'s own gating exactly (email: `notification_email`; SMS:
`notification_sms` **and** a non-empty `phone_number`) so the warning can never disagree with what
the real sender actually does — "no phone number" is only reported when SMS is otherwise enabled,
since if SMS itself is off the missing phone number isn't why nothing sent. The warning never
affects the step's or run's status (still `SUCCESS`) and needed no new endpoint wiring — the
existing `/processing-runs/{id}/logs` machinery already surfaces arbitrary `ProcessingStep.log_lines`
generically. 6 new tests (`test_pipeline_runner.py`: all-disabled, email-only, SMS-only, SMS-on-
without-phone, and no-warning-when-fully-configured; `test_processing_run_detail.py`: one true
end-to-end test driving a real pipeline run through to the actual logs endpoint, closing the loop
on the issue's explicit "warning appears in `/processing-runs/{id}/logs`" acceptance criterion
rather than only asserting on the ProcessingStep row directly). No improvement-pass changes needed
and no `modelsuggested` issues filed — the implementation matched the issue's acceptance criteria
exactly with no gaps found. `mypy --strict` clean; targeted test files green (full local suite hit
repeated sandbox-infra kills unrelated to the change - see below - so CI's `test` job is the
authoritative full-suite confirmation before merge).

**Slice 5.3 (#56 — Getting Started onboarding checklist) implemented.** On branch
`claude/admiring-carson-v5qr9b`: a 3-step checklist (Connect Storage → `/settings`, Set
Notification Preferences → `/profile`, Upload First File → `/upload`) renders above the events
table on `/dashboard`, its per-step done/incomplete state read from the `onboarding_storage_done` /
`onboarding_notifications_done` / `onboarding_first_upload_done` user booleans, and the whole block
is hidden once all three are true. Server-rendered (state reflects on next page load); done steps
render struck-through with an sr-only "(done)" marker, incomplete steps link to their page. New
pure `app/core/onboarding.py` view-model (`build_onboarding_steps` / `onboarding_complete`) with a
unit test, plus dashboard page tests for the show / mixed / hidden states; `mypy --strict` clean.
`onboarding_notifications_done` isn't flipped until Slice 7 (notifications), so that step stays
unchecked and the checklist stays visible until then — per the issue's resolved decision, no
blocker. Deferred e2e coverage filed as #91. #55 (5.2 filters/sort/search) is the remaining Slice 5
issue (In Progress on another branch).

**Bug #78 fixed (live Google Drive connect crashed with "Internal Error").** Root cause: the `ENCRYPTION_KEY` GitHub secret (flagged as an outstanding human-setup step since #45/#61) had never actually been created, so `get_credential_cipher()` raised `RuntimeError` unhandled inside `GET /callback`. Fixed on branch `fix/issue-78-encryption-key-callback`, in an isolated worktree: (1) generated a `Fernet` key and set it as the `ENCRYPTION_KEY` repo secret (shared by both `ci.yml`/QA and `deploy.yml`/prod) — resolves that part of #61 too; (2) the callback now catches a missing-cipher `RuntimeError` and redirects to `/settings?error=storage_not_configured` with a clear banner instead of a raw 500, so any future misconfiguration degrades gracefully. Regression test added. Issue #61's remaining scope (registering the Drive redirect URI + `drive` scope on the Google OAuth client) is Google-Cloud-Console-side and still an open manual task.

**Slice 8.1 (Dropbox StorageProvider) implemented.** Slice 7 has only #128 (deferred cleanup)
outstanding, so work moved to Slice 8 (Dropbox + S3 storage providers) — picked over Slice 8.2 (S3)
as the higher-value half of the pair since it reuses more of Slice 2's existing OAuth-connect
plumbing (Google Drive is also OAuth-based; S3's manual-credential shape is a bigger departure).
Issue #93 is implemented on branch `feature/slice-8.1-dropbox-storage-provider`, in an isolated
worktree: `DropboxStorageProvider` (`app/services/storage/dropbox.py`) implements the
`StorageProvider` ABC against the Dropbox API v2 via `httpx` (no official SDK dependency, mirroring
`google_drive.py`), addressing files by Dropbox's stable `id:...` identifier rather than path.
`app/api/v1/storage_dropbox.py` mirrors the Google Drive OAuth connect/disconnect flow, requesting
explicit `files.content.write`/`files.content.read` scopes (a scoped Dropbox app grants nothing
without them, unlike Google's client) and `token_access_type=offline` for a refresh token; its
revoke call bypasses `httpx_oauth` since Dropbox's revoke endpoint authenticates via the token being
revoked, not one passed in the request body. `app/services/storage/factory.py`'s
`build_storage_provider` now actually branches on `config.provider` — previously it always resolved
to Google Drive regardless of the stored provider, a latent placeholder from before Dropbox/S3
existed, now fixed (and raises for S3 until #94 lands). New `DROPBOX_OAUTH_CLIENT_ID`/
`DROPBOX_OAUTH_CLIENT_SECRET` settings (empty defaults) wired into `ci.yml`/`deploy.yml`'s Cloud Run
env vars alongside the other provider credentials. 25 new tests (provider unit tests via
`httpx.MockTransport`, OAuth flow tests, factory branching tests); `mypy --strict` clean. Deferred
lower-priority idea (persisting the refreshed access token back to `storage_configs`, mirroring the
existing Google Drive gap in #68) filed as `modelsuggested` issue #140. **Human setup before it
works live:** register a Dropbox app (scoped access, `files.content.write`/`files.content.read`
permissions) and set `DROPBOX_OAUTH_CLIENT_ID`/`DROPBOX_OAUTH_CLIENT_SECRET` as repo secrets — same
class of gap as issue #72's other provider setup steps. Settings > Storage tab UI support for
Dropbox (#95, blocked on this issue and #94) is next once #94 (S3) lands.

**Slice 8.2 (S3 StorageProvider) implemented.** Issue #94 is implemented on branch
`feature/s3-storage-provider`, in an isolated worktree: `S3StorageProvider`
(`app/services/storage/s3.py`) implements the `StorageProvider` ABC against a user's manually-
entered AWS credentials (access key, secret, bucket, region — no OAuth, the other half of the
Slice 8 pair alongside Dropbox's OAuth flow), using `boto3` with every blocking call wrapped in
`asyncio.to_thread` (per the issue's specified approach, mirroring `ResendEmailSender` rather than
adding `aioboto3`). `list_new_files` lists with `Delimiter="/"` so S3's natively-recursive prefix
listing matches the non-recursive, direct-children-only semantics Dropbox/Google Drive already
have; `move_file` is copy-then-delete (S3 has no native move). `app/services/storage/factory.py`
gains `build_s3_provider`, decrypting all four stored credential columns and completing
`build_storage_provider`'s provider branching (previously raised `unsupported storage provider`
for S3). 14 new provider tests + 2 new factory tests via a hand-rolled fake S3 client (no live AWS
credentials touched in CI); full suite (455 tests) + `mypy --strict` clean. Improvement pass:
wrapped boto3 errors in a (previously-defined-but-unused) `S3Error`, matching `DropboxError`'s
error-wrapping convention, and added a factory test asserting decrypted credentials actually reach
`boto3.client(...)`. Two lower-priority ideas deferred to `modelsuggested` issues #149
(retry/backoff on S3 throttling) and #150 (`boto3.client()` construction blocking the event loop).
With #94, Slice 8 has only #95 (Settings > Storage tab UI for all three providers) outstanding.

**Bug #143 fixed (import-pending-files failed in prod with no error detail).** Root cause: a
Drive/Dropbox API failure while listing pending files (`POST /api/v1/import-pending-files`) or
writing an uploaded file (`POST /api/v1/upload`) propagated as an unhandled exception — FastAPI's
default handler turns that into a bare 500 with no `detail` body, so the client's `messageFor()`
map had nothing to key off and always showed the generic "Import/Upload failed. Please try again.",
exactly the reported symptom (files visibly waiting in Drive, the button fails anyway with no
explanation). Fixed on branch `fix/import-pending-files-error-detail`, in an isolated worktree: both
endpoints now catch `GoogleDriveError`/`DropboxError` around the storage call, `logger.exception` it
(with the user id, for support/log correlation), close the provider, and return `502` with detail
`storage_error`, mapped by `import_pending_button.html`/`upload.html` to "Could not reach your storage
provider. Try reconnecting it in Settings, or try again in a moment." 2 new regression tests; full
suite green; `mypy --strict` clean. The first draft wrote "Couldn't" - a literal apostrophe inside
the single-quoted `x-data='...'` Alpine attribute, terminating it early and breaking Alpine init for
the whole button (the same bug class #23's `register.html` fix already warned about in this file).
`e2e-qa` caught it live against deployed QA (`import-pending-files.spec.ts`/`processing.spec.ts`
failing even though the backend was independently verified correct via direct API calls); reworded
to "Could not" to sidestep the apostrophe. Two lower-priority improvements deferred to
`modelsuggested` issues #146 (distinguish auth-failure from transient errors with a dedicated
`storage_reauth_required` detail) and #147 (e2e coverage for the `storage_error` path).

**Bug #144 fixed (notifications silently not delivered in prod, no error shown).** Root cause: a
real email/SMS delivery failure inside `RealNotificationSender._send_with_session` was swallowed by
a bare `except Exception: logger.exception(...)` per channel - the pipeline's Notify step still
logged "Notified user: ..." and reported success regardless, so the failure was indistinguishable
from a real send anywhere the user or support could see, exactly the reported symptom (preferences
correctly set to notify, no error, but nothing arrived). Fixed on branch
`fix/notification-delivery-visibility`, in an isolated worktree: `NotificationSender.send()` now
returns `list[str]` describing each channel that raised, and `_notify()`
(`app/services/pipeline/runner.py`) appends each as a `Warning: ...` log line on the Notify step,
visible via `/processing-runs/{id}/logs` - the same convention #112 already established for
silently-disabled channels, extended to genuine delivery failures. Also gave `ResendEmailSender` the
fail-fast-on-unset-config guard `TwilioSmsSender` already had (closing issue #124's deferred
email-side half): a missing `RESEND_API_KEY` now raises a clear error immediately instead of a
confusing Resend SDK error. 4 new regression tests; full suite green; `mypy --strict` clean.
Investigating surfaced the likely actual root cause: `Settings.email_from` defaults to Resend's
shared sandbox sender (`onboarding@resend.dev`), which only delivers to the Resend account's own
verified address - if prod hasn't verified a custom domain, this is an account/DNS-level fix outside
the repo, filed as `modelsuggested` issue #152 (**human setup**, same class of gap as #61/#72's
other provider-account setup steps).

## Completed Milestones

| Date | Milestone |
|------|-----------|
| 2026-07-09 | Issue #113 (reviewed flag + filter on dashboard events) implemented on branch `feature/slice-5-events-reviewed-flag`, in an isolated worktree. New `reviewed` boolean column on `events` (migration `a7b8c9d0e1f2`, default `false`) plus a partial index `ix_events_user_id_unreviewed_sort` (migration `b8c9d0e1f2a3`) covering the default `reviewed = false` query. `GET /api/v1/events`/`/dashboard` gain a `show_reviewed` param (default `false`, composes with the other filters/pagination). New `PATCH /api/v1/events/{id}` (owner-scoped via shared `get_owned_event`, 404 either way, mirrors `DELETE`) toggles the flag. Dashboard: per-row "Reviewed" checkbox (Alpine `fetch` PATCH, no reload, re-renders `#dashboard-body` via `htmx.ajax()` on success, reverts on failure) + a "Show reviewed" filter checkbox. Code-review pass fixed two real bugs (client-side row-removal desync at pagination boundaries; `has_active_filters` missing the default reviewed-hiding, causing a misleading "No events yet" for all-reviewed users) plus a redundant `db.refresh()` and duplicated owner-lookup code. 15 new tests; full suite green; `mypy --strict` clean |
| 2026-07-09 | Issue #100 (Dashboard "Agreed by" chips show initials, not full name) implemented directly on `main` (small, self-contained UI tweak, no branch per CLAUDE.md's minor-change rule), in an isolated worktree. New pure helper `app/core/initials.py::to_initials()` (first + last word initials, uppercased; single-word falls back to first letter; empty input → empty string), registered as a Jinja filter and used in `partials/events_panel.html` — chip text is now initials with the full name in a `title` tooltip. Improvement pass: made the chip focusable (`tabindex="0"`) so the tooltip is keyboard-reachable. Follow-ups filed as #137 (Intake — `title` tooltips don't appear on touch devices) and #138 (Intake — two people sharing initials render identical chips). `mypy --strict` clean; targeted test suite green |
| 2026-07-09 | Issue #85 (Slice 6.3 — searchable log filter + log download) implemented on branch `feature/slice-6.3-log-search-download`, in an isolated worktree. The HTMX search filter already existed from #84; added `GET /api/v1/processing-runs/{id}/logs/download` (full structured logs across all steps as a downloadable JSON file) + a "Download logs" link on the run detail page. Improvement pass fixed a pre-existing search bug (`%`/`_` wrongly escaped for a SQL `LIKE` pattern that was never used) and deduplicated search/pagination logic into `app/services/processing_logs.py`. Follow-up filed as #118 (Intake). With #85, Slice 6 is complete |
| 2026-07-04 | Issue #83 (Slice 6.1 — processing history list page) implemented on branch `feature/slice-6.1-logs-page`, in an isolated worktree. `GET /api/v1/processing-runs` (50/page, newest `created_at` first) with user scoping + pagination. New `/logs` page replaces the placeholder: table showing run date, filename, status, and event count per row, each row linking to `/processing-runs/{id}`. New `ProcessingRunRead` and `ProcessingRunListRead` Pydantic schemas. Comprehensive test suite (12 tests) covering API pagination, user scoping, and page rendering. `mypy --strict` clean. Follows the Events dashboard (Slice 5) patterns. With #83, Slice 6.1 is functionally complete. Slice 6.2 (run detail page) next |
| 2026-07-04 | Issue #31 (shared card_page macro) implemented on branch `feature/shared-card-page-macro`. Extracted a `card_page` Jinja call-block macro (`app/templates/macros/ui.html`) that renders the centred DaisyUI card shell. All five auth/profile templates now use it. Alpine.js `x-data` placed on an ancestor wrapper outside the macro call to preserve reactive scope. Regression tests in `tests/test_card_macro.py`. |
| 2026-07-04 | Issue #56 (Slice 5.3 — Getting Started onboarding checklist) implemented on branch `claude/admiring-carson-v5qr9b`. A 3-step checklist (Connect Storage → `/settings`, Set Notification Preferences → `/profile`, Upload First File → `/upload`) renders above the events table on `/dashboard`, per-step done state from the `onboarding_*_done` user booleans, hidden once all three are true. Server-rendered; done steps struck-through with an sr-only "(done)" marker, incomplete steps link to their page. New pure `app/core/onboarding.py` view-model + unit test; dashboard page tests for show/mixed/hidden; `mypy --strict` clean. `onboarding_notifications_done` stays unchecked until Slice 7 (no blocker, per the issue's resolved decision). Deferred e2e coverage filed as #91 |
| 2026-07-04 | Issue #55 (Slice 5.2 — events dashboard filters, sort & search) implemented on branch `feature/slice-5.2-events-filters`, in an isolated worktree. `GET /api/v1/events` gains `type`/`date_from`/`date_to`/`q`/`sort` query params, composing with each other and with pagination (`app.api.v1.events.list_user_events`); new `list_user_event_types` backs the type dropdown. HTMX-driven filter bar: the form and pagination/sort links swap `#dashboard-body` via `partials/dashboard_body.html`, so no full page reload. Manual browser QA caught two real bugs pre-merge (empty-string date params 422ing; sort-toggle/hidden field going stale outside the swap target); a code-review pass caught two more (malformed-date 500, unescaped `%`/`_` LIKE wildcards in search) plus a `functools.partial` DRY cleanup on `_dashboard_url`. Three lower-priority suggestions deferred to #96/#97/#98. `mypy --strict` clean; full suite (286 tests) green |
| 2026-07-04 | Issue #72 (Slice 4 human-setup checklist) partially automated on branch `ops/issue-72-gemini-key-cpu-throttling`: wired `GEMINI_API_KEY` into `ci.yml`/`deploy.yml`'s Cloud Run env-vars files and added `--no-cpu-throttling` to both `gcloud run deploy` commands so the in-process pipeline task survives past the HTTP response. Improvement pass also fixed `GoogleDriveStorageProvider.upload_file`'s multipart encoding (httpx `files=` produces `multipart/form-data`, not the `multipart/related` Drive expects) by switching to a two-request create-then-media-upload approach. Creating the `GEMINI_API_KEY` GitHub Actions secret and manual QA of the live `GoogleDriveStorageProvider` remain human/ops steps — see the issue |
| 2026-07-04 | Bug #78 (live Google Drive connect returned "Internal Error") fixed on branch `fix/issue-78-encryption-key-callback`, in an isolated worktree. Root cause: the `ENCRYPTION_KEY` GitHub secret (flagged since #45/#61) had never been created, so `get_credential_cipher()`'s `RuntimeError` went unhandled inside `GET /callback`. Generated a `Fernet` key and set the `ENCRYPTION_KEY` repo secret (shared by `ci.yml`/QA and `deploy.yml`/prod) — resolves that part of #61 too. Callback now catches the missing-cipher case and redirects to `/settings?error=storage_not_configured` with a banner instead of a 500; regression test added. #61's remaining scope (Google Cloud Console redirect URI + `drive` scope registration) is still an open manual task |
| 2026-07-04 | Issue #54 (Slice 5.1 — events dashboard) implemented on branch `feature/slice-5.1-events-dashboard`, in an isolated worktree. `GET /api/v1/events` (50/page, newest `resolved_date_earliest` first, `NULLS LAST`) + `DELETE /api/v1/events/{id}` (owner-scoped, 404 either way). New `app/core/calendar_url.py` (Calendar's well-known quick-add convention; Tasks is a best-effort, unverified scheme — no official Google URL exists). Dashboard page replaces the `/dashboard` placeholder: table, Calendar/Tasks links, confirm-gated Delete, pagination, total count. New index migration `f6a7b8c9d0e1` covering the dashboard's filter+sort. Improvement pass: the index, out-of-range-page redirect, total-count line. `mypy --strict` clean; full suite green. Manual verification needed: does Google Tasks actually honour the pre-fill params. #55 next, blocked by this |
| 2026-07-04 | Issue #53 (Slice 4.2 — live SSE pipeline progress page) implemented on branch `claude/admiring-carson-bzzfow`. New `/processing` page (`app/pages/processing.py` + `processing.html`) renders the 7 step indicators and streams live via the HTMX SSE extension; `GET /api/v1/processing-runs/{id}/sse` (`app/api/v1/processing_runs.py`, sse-starlette) polls `processing_steps` (~0.75s, no Redis) and closes with a `done` event on a terminal state. Progress logic in `app/services/pipeline/progress.py` (`build_step_views` + `stream_run_progress`); step badge is a shared Jinja partial used by both first paint and SSE fragments. Owner-only (404 otherwise); latest-run fallback without `?run=`; finished runs render statically (no stream). `PIPELINE_STEPS` added to the runner as the single 7-step source of truth; `get_gemini_client` returns a canned fake under `E2E_TEST_MODE` for the new Playwright `processing.spec.ts`. Added `sse-starlette`. Unit + endpoint + page tests + e2e; `mypy --strict` clean. With #53, Slice 4 is functionally complete |
| 2026-07-03 | Issue #52 (Slice 4.1 — upload page + 7-step pipeline) implemented on branch `feature/slice-4.1-upload-pipeline`, in an isolated worktree. `POST /api/v1/upload` (gated on a connected Drive, 10 MB bounded read, `.txt`/`.zip`/`.csv`) → `processing_runs` row → **in-process asyncio** 7-step pipeline (NOT Celery, per #52's resolved decision) writing `processing_steps` + `events`; Gemini/parse failure ⇒ `failed` + file → `failed/` + failure notice, zero-new-events ⇒ success + "0 new events". New stubbed notification boundary (`app/services/notifications/pipeline.py`), concrete `GoogleDriveStorageProvider` (Drive REST v3; fake under `E2E_TEST_MODE`), drag-and-drop Upload page. Stubbed pipeline integration test + unit tests (filter/notifier/Drive-`MockTransport`/endpoint/page) + skip-unless-`GEMINI_API_KEY` real-Gemini e2e; `mypy --strict` clean. Improvement pass: bounded read + provider `aclose()` done, token-persistence deferred → #68. **Human setup before live:** real `GEMINI_API_KEY`, Cloud Run "CPU always allocated", and manual QA of the Drive provider against a real account. #53 next |
| 2026-07-03 | Issue #51 (Slice 4.0 — pipeline foundation) implemented on branch `feature/slice-4.0-pipeline-foundation`, in an isolated worktree. Three models + migration `e5f6a7b8c9d0` (`processing_runs`, `processing_steps` with JSONB `log_lines`, `events` with the `UNIQUE(user_id, description, resolved_date)` constraint + `resolved_date_earliest` DATE; up/down round-trip verified against QA). `app/core/date_parser.py::parse_earliest_date` reduces the LLM's free-text `resolved_date` to the earliest calendar date (`None` for "TBC"/unparseable), validated against all 22 real values in `examples/example.lmmoutput.txt`. `app/services/llm/gemini.py` — `GeminiClient` Protocol, `GoogleGeminiClient` (google-genai, raises immediately, no retry), `FakeGeminiClient`, `get_gemini_client` factory. New optional `GEMINI_API_KEY` setting (empty default; tests inject the fake). Deferred improvements filed as #64 (structured-JSON output) + #65 (configurable model). First Slice 4 issue; #52 next |
| 2026-06-30 | 34-question requirements grilling session completed |
| 2026-06-30 | `docs/prd.md` written — full user requirements captured |
| 2026-06-30 | `docs/technical-approach.md` written — full stack and infrastructure decisions |
| 2026-06-30 | `docs/implementation-plan.md` written — implementation design spec, 9 vertical slices defined |
| 2026-06-30 | Slice 1 prerequisites provisioned — GCP, Cloud Run (QA + prod), Artifact Registry, Supabase, Upstash Redis, Google OAuth app, Resend, Twilio, Gemini key (issues #1–#9) |
| 2026-07-01 | Slice 1 broken into 8 TDD-ready issues (#10–#17) and published to the OrganizeMe project |
| 2026-07-01 | Issue #10 (project scaffold + CI/CD) implemented — FastAPI skeleton, Docker + supervisord, GitHub Actions ci.yml/deploy.yml — on branch `feature/slice-1-scaffold-cicd` |
| 2026-07-01 | Issue #11 (DB foundation — Supabase connection + `users` table) implemented — SQLAlchemy 2.0 async engine/session, Alembic async migrations, pydantic-settings config, transaction-rollback pytest fixture against real Supabase QA DB — on branch `feature/slice-1-db-foundation` |
| 2026-07-01 | Issues #10 and #11 merged into `main` (PRs #18, #19). Post-merge, `deploy.yml`'s prod gate caught that the `SUPABASE_PROD_URL` secret still used Supabase's IPv6-only direct-connection host (same issue QA's secret had) and that prod's transaction-mode pooler needed asyncpg's prepared-statement cache disabled (`statement_cache_size=0`) — both fixed directly on `main`; `test` + `deploy-prod` are green and prod `/health` is confirmed live |
| 2026-07-02 | Issue #12 (email/password auth — register/login/logout) implemented — FastAPI-Users v15, bcrypt password hashing, JWT-in-HTTPOnly-cookie (7-day expiry), DaisyUI register/login pages. Discovered and fixed a live-deployment gap: QA/prod Cloud Run services had zero environment variables wired in at all; added `JWT_SECRET_QA`/`JWT_SECRET_PROD` secrets and `--env-vars-file` deploy wiring for `DATABASE_URL`+`JWT_SECRET`. Merged into `main` (PR #20); `deploy.yml` green and prod `/health`, `/register`, `/login` confirmed live |
| 2026-07-02 | Issue #13 (Google OAuth login) implemented on branch `feature/slice-1-google-oauth` — `httpx-oauth`, `OAuthAccount` table/migration, custom redirect-based `GET /api/v1/auth/google` + `/callback` (fastapi-users' built-in OAuth router returns JSON, not a redirect), signed-JWT + double-submit-cookie CSRF state, account linking by email, Google sign-in buttons on login/register pages. Multi-agent code review (8 finder angles + verification) caught and fixed three real bugs: unhandled Google token/profile exchange failures surfacing as raw 500s, an unguarded `IntegrityError` race on concurrent first-time Google logins, and a `TypeError` crash from comparing a non-ASCII CSRF cookie value. Built in an isolated git worktree after discovering another session was concurrently using the shared working directory for issue #14. Merged into `main` (PR #22); `deploy.yml` green and prod `/health`, `/api/v1/auth/google` (redirects to Google's real consent screen with the correct `client_id`/`redirect_uri`) confirmed live |
| 2026-07-02 | Issue #13 merging to `main` stamped the shared Supabase QA database's Alembic revision ahead of issue #14's branch (still checked out in the primary working directory, not a worktree), breaking #14's CI `alembic upgrade head` step with `Can't locate revision`. Resolved by merging `main` into `feature/slice-1-forgot-reset-password` once #13 landed |
| 2026-07-02 | Issue #14 (forgot/reset password) implemented on branch `feature/slice-1-forgot-reset-password` — `POST /api/v1/auth/forgot-password` + `/reset-password`, DaisyUI forgot/reset-password pages, and `app/services/notifications/email.py` (`EmailSender` protocol, `ResendEmailSender`, `FakeEmailSender`) — the first cut of the email interface Slice 7 (Notifications) will reuse. Proactively wired `RESEND_API_KEY` into both `ci.yml`/`deploy.yml` Cloud Run env-vars (closing the same "secret exists but isn't wired to the running service" gap class that bit #10 and #12) instead of discovering it post-merge |
| 2026-07-02 | Issue #15 (profile — view/edit, dark mode, account deletion) implemented on branch `feature/slice-1-profile`, built in an isolated worktree with two parallel agents (backend endpoints, frontend page/template) working disjoint file sets. `PATCH`/`DELETE /api/v1/users/me` added; `GET /profile` is the app's first authenticated page route; Alpine.js introduced (named in `docs/technical-approach.md` since #10, never wired in until now) for the dark/light toggle and delete-confirm modal; `base.html`'s theme is now server-rendered from the user's persisted preference. A TDD test written specifically because issue #15's own comment thread asked for it (confirming the `oauth_accounts` cascade-delete) caught a real ORM bug — `passive_deletes="all"` added to `User.oauth_accounts`. Multi-agent code review before commit caught two further real bugs (explicit `{"email": null}`/`{"dark_mode": null}` PATCH bodies bypassed validation and hit the DB's NOT NULL constraint, mislabeled as an email conflict; a delete-failure path tried to close the confirm modal via a variable never wired to it) — both fixed pre-merge. Merged into `main` (PR #24); `deploy.yml` green and prod `/profile`, `/api/v1/users/me` confirmed live. See `docs/changelog.md` for full detail |
| 2026-07-02 | Issue #16 (landing page) implemented on branch `feature/slice-1-landing-page` — `GET /` (public, no auth) renders a DaisyUI hero/features/CTA landing page with nav links to `/login`/`/register`; added a reusable `{% block head %}` extension point to `base.html` (used here for a meta description, available to future pages). Small enough in scope to implement directly rather than dispatch multiple agents. 5 improvements applied after comparing against issue #16's acceptance criteria: a meta description tag, a second CTA path (login) for returning visitors, broadened test coverage confirming the hero's CTA (not just the dedicated CTA section) links to `/register`, a nav-links-present test, and a regression test that `/login`/`/register` actually resolve to 200 (guards against a typo'd `href` silently breaking navigation). Merged into `main` (PR #25); `deploy.yml` green and prod `/` confirmed live |
| 2026-07-02 | Added issue #23 (Slice 1.8: automated Playwright E2E tests) to validate Slice 1's overall UX delivery against the deployed QA Cloud Run instance, at the user's request. Decided with the user: tests target the real QA deploy (new `e2e-qa` CI job after `deploy-qa`, becomes a required check going forward); Google OAuth is excluded from E2E (unreliable to drive headlessly) and stays on backend tests only; the forgot/reset-password flow uses a new debug-only `/api/v1/internal/e2e/last-reset-token` endpoint (gated by `E2E_TEST_MODE`, QA-only) instead of a real inbox. Blocked by #15/#16/#17 since it exercises profile, landing, and sidebar pages that don't exist yet |
| 2026-07-02 | User reported two live bugs post-#16: registering with email/password lands on a raw JSON response instead of any page, and Google sign-in hangs on Google's consent screen without returning to the app. Investigated both; filed as issues #26 and #27 rather than guessing at fixes blind |
| 2026-07-02 | Issue #26 (register/login plain forms show raw JSON) implemented on branch `fix/auth-form-json-response` — root cause was `register.html`/`login.html` using plain `<form method="post">` against JSON API endpoints with no redirect. Both forms now submit via Alpine.js `fetch` (progressive enhancement — native `action`/`method` kept as markup, not a functional no-JS fallback given the API returns JSON either way); register auto-logs in after a successful signup (matching Google sign-up's instant-login UX) and redirects to `/profile`. 5 improvements applied comparing against the issue: (1) register's error handling now also parses FastAPI's 422 pydantic-validation array shape; (2) the previously server-rendered `?error=google_auth_failed` Jinja banner unified into the same Alpine `error` reactive state (via a new `init()` reading the query string) on both pages; (3) a `registered=1` info banner added to `login.html` for the case where auto-login unexpectedly fails right after a successful registration; (4) email inputs are trimmed of leading/trailing whitespace before submit on both forms; (5) `aria-live="polite"` added to both alert banners for screen-reader accessibility. Self-reviewed directly (no multi-agent dispatch) given the diff's size (3 files, template/test only, no business logic) — one real finding survived: removing the static Jinja `google_auth_failed` block means a no-JS visitor no longer sees that banner at all, whereas it previously rendered unconditionally; accepted as a known trade-off rather than fixed, since the same visitor's actual form submission was already broken without JS regardless (the entire point of this fix) |
| 2026-07-02 | Issue #17 (sidebar shell + placeholder pages) implemented on branch `feature/slice1-sidebar-shell`, built in an isolated worktree. Added a shared `authenticated_base.html` DaisyUI-drawer layout rendering a persistent left sidebar from a single `NAV_ITEMS` source (`app/pages/nav.py`, exposed as a Jinja global); six new auth-gated placeholder routes (`/dashboard`, `/upload`, `/processing`, `/logs`, `/prompt`, `/settings`) derived from that same list, each redirecting anonymous visitors to `/login`; `/profile` re-parented onto the layout (form/logic unchanged). Current route marked `aria-current="page"`; a Log out action added to the sidebar footer. TDD: `tests/test_sidebar.py` (auth-gating on all 7 routes, nav presence + documented order across ≥2 routes, active-highlight, logout presence, sidebar absent on public pages); full suite (96) + `mypy app tests` green |
| 2026-07-02 | Issue #23 (Slice 1.8 — Playwright E2E) implemented on branch `feature/slice-1-e2e-playwright`, built in an isolated worktree. New `e2e/` TypeScript/Playwright suite (9 tests) drives the deployed QA app end-to-end: landing, register→login→logout, forgot→reset password, profile edit + server-side dark-mode persistence, account deletion (incl. replaying the pre-deletion cookie to prove it no longer authenticates), sidebar nav order + unauthenticated redirect. Wired into `ci.yml` as an `e2e-qa` job after `deploy-qa` (uploads the Playwright HTML report artifact on failure). Backed by a test-only `GET /api/v1/internal/e2e/last-reset-token` endpoint (`app/api/v1/internal_e2e.py`) that mints a valid reset-token JWT, gated behind a new `E2E_TEST_MODE` setting — hidden from the OpenAPI schema and 404 everywhere except QA (where `ci.yml` sets it; a pytest guard asserts `deploy.yml`/prod never does). **The suite immediately earned its keep**: it caught a latent production bug where `register.html`'s Alpine `x-data` was truncated by an embedded `type="email"` double-quote inside a JS comment (breaking the entire register form in real browsers, invisible to pytest's HTML-only assertions) — fixed here, with a new pytest guard against recurrence. Making `e2e-qa` a required status check on `main` is a one-time branch-protection step to apply post-merge |
| 2026-07-03 | Issue #49 (Slice 3.1 — prompt page + endpoints) implemented on branch `feature/slice-3.1-prompt-page`, in an isolated worktree. New `app/api/v1/llm_prompt.py`: `GET`/`PUT /api/v1/llm-prompt` + `POST /api/v1/llm-prompt/reset`, with edit and reset funnelling through one `set_user_prompt` create-or-update helper (unique on `user_id`, never a second row; reset = that helper with `FACTORY_DEFAULT_PROMPT`), GET falling back to the factory default without writing for a legacy account with no seeded row, and a strip + non-blank + 20 000-char validator on writes. New Prompt page (`app/pages/prompt.py` + `templates/prompt.html`): textarea editor + Save + Reset-to-Default wired to the endpoints via Alpine `fetch`, seeded from the server; `/prompt` moved off the placeholder router (sidebar/nav unchanged, `test_sidebar.py` still green). Playwright `e2e/tests/prompt.spec.ts` (edit → save → reload → reset round-trip) in the `e2e-qa` job; pytest covers endpoints, a direct reset-logic unit test on `set_user_prompt`, and the page (render, saved-edit reflection, `x-data` truncation guard). Full suite + `mypy app tests` green. Last Slice 3 issue |
| 2026-07-03 | Issue #48 (Slice 3.0 — prompt foundation) implemented on branch `feature/slice-3.0-prompt-foundation`, in an isolated worktree. New `llm_prompts` table (one row per user, unique on `user_id`, `prompt_text` TEXT NOT NULL, timestamps; migration `d3e4f5a6b7c8`, up/down verified). Single factory-default extraction-prompt constant `app/core/prompts.py::FACTORY_DEFAULT_PROMPT` (verbatim from the issue, based on `examples/example.lmmoutput.txt`) shared by seeding and the later #49 Reset button. Seed-on-registration via `UserManager.on_after_register` — a single seam fastapi-users fires from both `create()` (email/password) and `oauth_callback()` on new-Google-user creation, and never on Google-link, so both paths seed exactly one prompt with no double-seed. Tests: `test_llm_prompt_model.py` (persistence + unique-per-user), `test_prompt_seed.py` (email/password seed, Google seed, no double-seed on link). First Slice 3 issue; #49 (blocked by #48) is next |
| 2026-07-03 | Issues #23 (Playwright E2E, PR #57) and #45 (Slice 2.0 storage foundation, PR #58) merged into `main`; both prod deploys green. Slice 1 fully drained; Slice 2 underway |
| 2026-07-03 | Issue #47 (Slice 2.2 — Google Drive OAuth connect/disconnect + onboarding flag) implemented on branch `feature/slice-2-gdrive-oauth`, in an isolated worktree. New `app/api/v1/storage_google_drive.py`: `POST /auth` (returns Google's consent URL as JSON + CSRF cookie; drive scope, offline/consent for a refresh token), `GET /callback` (CSRF-validated, exchanges the code via an injected OAuth client, stores access+refresh tokens encrypted at rest via the #45 cipher + the token expiry, flips `onboarding_storage_done`), `POST /disconnect` (revokes at Google best-effort, then clears). Storage tab gains Connect/Disconnect controls (Connect gated on a saved folder path) + banners; the connect POST is a same-origin fetch since the SameSite=Lax auth cookie wouldn't ride a top-level form POST. Improvement pass (all three user-selected): Google-side token revocation on disconnect, a 409 for the no-config `/auth` case, and a persisted `oauth_token_expires_at` column (migration `b2c3d4e5f6a7`). Tested with a fake OAuth client + fake revoker + throwaway cipher key (no live Google creds; independent of `ENCRYPTION_KEY`). **Human setup before live:** register the Drive callback redirect URI + add the `drive` scope on the Google OAuth client, and create the `ENCRYPTION_KEY` secret |
| 2026-07-03 | Issue #46 (Slice 2.1 — Settings > Storage tab + storage-config read/write) implemented on branch `feature/slice-2-storage-tab`, in an isolated worktree. `GET`/`PUT /api/v1/storage-config` (`app/api/v1/storage_config.py`): credential-safe read exposing only `{provider, folder_path, is_connected}`, single-row-per-user upsert. New Settings page (`app/pages/settings.py` + `settings.html`) with a Storage tab — Alpine.js provider dropdown conditionally shows the Google Drive fields (folder path + not-connected hint) and hides Dropbox/S3 stubs, no reload; `/settings` moved off the placeholder router. Two improvement-pass items applied (user-selected): server-side folder-path trim + blank-rejection, and a derived `is_connected` flag surfaced on the tab ahead of #47. New `e2e/tests/storage.spec.ts` (conditional fields + folder-path round-trip) in the `e2e-qa` job; pytest covers endpoints, page render/gating, credential non-leak, and `x-data` truncation. Full suite + `mypy app tests` green |
| 2026-07-02 | Issue #27 (Google sign-in hangs on Google's consent page, never returns) fixed on branch `fix/google-oauth-callback-redirect`, built in an isolated worktree. Root cause: the `GET /api/v1/auth/google/callback` success path returned `auth_backend.login(...)` — fastapi-users' default cookie login response, a bare `204 No Content` — and a browser following Google's full-page redirect renders a 204 as nothing, leaving the user stranded on Google's consent page. Every failure path already `302`ed correctly; only the success path didn't. Fix: on success, `302` to `/profile` (extracted to a `GOOGLE_OAUTH_SUCCESS_REDIRECT` constant, kept in sync with the email/password login's client-side redirect target) and carry the auth cookie across by copying the backend login response's `Set-Cookie` header(s) onto the redirect — so cookie name/max-age/secure/samesite stay defined once in `app.auth.backend`. TDD: three success-path tests were flipped from accepting `204` to asserting `302 → /profile`, plus a named regression test for #27; full suite (77) + `mypy app tests` green. Follow-up #43 filed for the identical latent `204` on `POST /auth/login` (works today only because PR #28 added client-side JS) |

## Next Steps

1. **Implement Slice 1, in order:**
   - #10 Project scaffold + CI/CD pipeline — ✅ merged
   - #11 DB foundation — Supabase connection + `users` table — ✅ merged
   - #12 Email/password auth — register, login, logout — ✅ merged
   - #13 Google OAuth login — ✅ merged
   - #14 Forgot / reset password — ✅ merged
   - #15 Profile — view/edit, dark mode, account deletion — ✅ merged
   - #16 Landing page — ✅ merged
   - #17 Sidebar shell + placeholder pages — ✅ merged (PR #50)
   - #23 Automated E2E UX tests (Playwright, against QA deploy) — ✅ merged (PR #57); last Slice 1 issue
2. **Slice 2** — Google Drive storage integration
   - #45 Storage foundation (`storage_configs` + `StorageProvider` ABC + encryption helpers) — ✅ merged (PR #58)
   - #46 Settings > Storage tab + storage-config read/write — ✅ merged (PR #59)
   - #47 Google Drive OAuth connect/disconnect + onboarding flag — ✅ merged (PR #60; last Slice 2 issue)
3. **Slice 3** — LLM Prompt page
   - #48 Prompt foundation (`llm_prompts` table + factory-default constant + seed on user creation) — ✅ merged (PR #62)
   - #49 Prompt page + `/api/v1/llm-prompt` GET/PUT/reset — 🔨 implemented on `feature/slice-3.1-prompt-page` (last Slice 3 issue)

## Open Decisions

- None — all design questions resolved in `docs/implementation-plan.md`

## Suggestions for Future Review

The improvement/decision items surfaced while reviewing Slice 1 issues #14–#16 against
`docs/prd.md` are now tracked as GitHub issues **#29–#42** in the OrganizeMe project, each tagged
`future-enhancement` + `slice1`. (The duplicated-DaisyUI-markup item, flagged during both #14 and
#15, was consolidated into a single issue.) See the OrganizeMe project board for current status.

Surfaced comparing issue #26's implementation (fixing `/register`/`/login`'s raw-JSON-response bug)
against `docs/prd.md`; not implemented (out of #26's scope), flagged here for a deliberate decision
before or during the slice that would own each one.

16. **Auto-login on registration bypasses email verification and immediately issues a working
    session.** #26 wires password-based registration to auto-login (matching the Google sign-up
    path), but since `is_verified` still isn't enforced anywhere (suggestion #1), anyone can
    register with an email address they don't own and land on `/profile` with a live session
    instantly — no verification gate ever gets a chance to run. Worth weighing alongside
    suggestion #1 now that auto-login makes this concretely reachable, not just theoretical.
17. **Registration's "account already exists" error aids account enumeration.** The register
    page's JS now surfaces `REGISTER_USER_ALREADY_EXISTS` as a clean, friendly banner —
    functionally correct, but it makes confirming whether an email is already registered easier
    than before (the raw JSON 400 was there since #12, just less discoverable). `forgot-password`
    deliberately returns an identical response for known/unknown emails to avoid exactly this
    (suggestion #5); worth deciding if registration should follow the same non-enumeration
    pattern, or if this trade-off is accepted for open self-registration.
18. **Duplicated DaisyUI card/form markup — now a third alert variant (`alert-info`) layered on
    top.** Suggestions #3/#6 already flagged the four (now five, with `profile.html`) auth/page
    templates repeating the same card/form wrapper. #26 adds an `alert-info` "registered"
    banner alongside the existing `alert-error` pattern on `login.html`, independently
    hand-rolled rather than through a shared component — the divergence between templates grows
    with each issue that touches them.
19. **No documented decision on whether the app requires JavaScript.** #26's fix necessarily makes
    `/register` and `/login` depend on JS to work correctly, since the underlying API endpoints
    return JSON and a plain form POST has no way to redirect afterward. This is a structural,
    site-wide decision (interacts with the public landing page's audience, accessibility policy,
    and SEO crawlability) that has never been written down in `docs/technical-approach.md`.
20. **No standardized alert/banner convention across severities.** `login.html`/`register.html`
    now each hand-roll their own `x-show`/`x-cloak`/`aria-live` alert markup per severity
    (`alert-error`, `alert-info`); worth defining a documented DaisyUI alert component/macro
    (colour, icon, ARIA attributes per severity) before a `alert-success`/`alert-warning` variant
    gets added ad hoc by some future issue.

Surfaced while building the Slice 1.8 Playwright E2E suite (issue #23):

21. **`/reset-password` still shows a raw JSON response after submit — same class as #26.** The
    reset-password page uses a plain `<form method="post" action="/api/v1/auth/reset-password">`,
    so a successful submit navigates the browser to the endpoint's JSON body
    (`{"detail": "Your password has been reset."}`) instead of redirecting to `/login`. This is
    the identical raw-JSON-after-form-POST problem #26 fixed for `/register` and `/login` (and a
    sibling of #43); reset-password was simply out of #26's scope. The #23 E2E test asserts on the
    raw JSON text as a workaround. Recommend converting the reset form to Alpine `@submit.prevent`
    + `fetch` with a redirect to `/login` on success (handling the existing bad-token / mismatch /
    min-length / inactive-user error cases inline), then tightening the E2E test to assert the
    friendly redirect. **Not filed as a GitHub issue** (issue creation was blocked this session);
    file one before or when picking this up.
22. **Real bug caught by the E2E suite and fixed in #23: `register.html`'s Alpine `x-data` was
    silently broken in production.** A JS comment inside the double-quoted `x-data` attribute
    contained `type="email"`; those embedded double quotes terminated the HTML attribute early,
    truncating the Alpine expression so the register component threw `Unexpected token ')'` and
    never initialised — the whole email/password register form was dead in a real browser. It
    passed every `pytest` check because those only string-match the rendered HTML and never
    execute the JS. Fixed by removing the quotes from the comment, plus a new pytest guard
    (`test_register_page_x_data_attribute_is_not_truncated_by_a_stray_quote`) that parses the page
    as a browser would and asserts the expression isn't truncated. This is exactly the class of
    regression the E2E suite exists to catch.

## Known Constraints

- Gemini is the LLM provider (fixed for v1); fail immediately on LLM error (no retry)
- One cloud storage provider active per user at a time; Google Drive built first
- Pre-filled URL approach for Google Calendar / Tasks (no OAuth write)
- Open self-registration (no invite flow)
- Desktop-first UI (mobile responsiveness not required for v1)
- DaisyUI component library on top of Tailwind CSS
- Upstash Redis used for both local dev and production (no local Docker for Redis or DB)
- Celery worker co-located in same Cloud Run container as FastAPI app (supervisord)
- Cloud Scheduler polls every 15 minutes (not 5)
