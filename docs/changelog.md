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
