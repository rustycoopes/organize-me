# OrganizeMe — Changelog

> Long-form implementation notes for completed issues live in
> [`changelog-archive.md`](changelog-archive.md). Keep this file lean: a short entry per change,
> with a pointer to the archive for full detail. Append new entries here; move them to the archive
> once they grow long or the issue is merged.

---

## [Unreleased]

### Fixed
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
