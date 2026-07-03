# OrganizeMe — Project Status

**Last updated:** 2026-07-03

---

## Current Phase

**Slice 1 in progress.** All prerequisites provisioned (issues #1–#9, closed). Slice 1 broken into 8 TDD-sized issues (#10–#17), plus a 9th (#23) added 2026-07-02 to validate the whole slice with automated Playwright E2E tests. Issues #10 (project scaffold + CI/CD, PR #18), #11 (DB foundation, PR #19), #12 (email/password auth, PR #20), #13 (Google OAuth login, PR #22), #14 (forgot/reset password, PR #21), #15 (profile — view/edit, dark mode, account deletion, PR #24), and #16 (landing page, PR #25) are all merged into `main`; `ci.yml` (QA) and `deploy.yml` (prod) run green, and `/health`, `/`, `/register`/`/login` (incl. Google sign-in), `/forgot-password`/`/reset-password`, `/profile`, and `/api/v1/users/me` are confirmed live on both Cloud Run services. Two live bugs reported by the user after #16 shipped: `/register`/`/login`'s plain HTML forms landed users on a raw JSON response instead of any page (filed as issue #26, fixed on branch `fix/auth-form-json-response`, PR #28) and Google sign-in hanging on Google's consent page (filed as issue #27). #26 is merged (PR #28). #27 root cause found and fixed on branch `fix/google-oauth-callback-redirect`: the `/api/v1/auth/google/callback` success path returned fastapi-users' bare `204 No Content`, so the full-page redirect from Google had nothing to navigate to — now `302`s to `/profile` with the auth cookie. Follow-up #43 filed for the same latent `204` on `POST /auth/login` (masked today by client-side JS). #27 has since merged (PR #44). Issue #17 (sidebar shell + placeholder pages) merged into `main` (PR #50). Issue #23 (Playwright E2E) — the last Slice 1 issue — is now implemented on branch `feature/slice-1-e2e-playwright`: an `e2e/` Playwright/TypeScript suite driving the deployed QA app (landing, register→login→logout, forgot→reset password, profile edit + dark-mode persistence, account deletion, sidebar nav), wired into `ci.yml` as an `e2e-qa` job after `deploy-qa`, backed by a test-only `GET /api/v1/internal/e2e/last-reset-token` endpoint gated behind a new `E2E_TEST_MODE` flag (QA-only, 404 + schema-hidden elsewhere). With #23, Slice 1 is functionally complete.

**Slice 2 (Google Drive storage) nearly done.** Slice 1 fully drained. Issue #45 (storage foundation, PR #58) and #46 (Settings > Storage tab + `GET`/`PUT /api/v1/storage-config`, PR #59) are both merged, prod-verified. Issue #47 (Slice 2.2 — Google Drive OAuth connect/disconnect + onboarding flag), the last Slice 2 issue, is implemented on branch `feature/slice-2-gdrive-oauth`: `POST /auth` → Google consent URL (drive scope, offline/refresh), `GET /callback` stores access+refresh tokens encrypted at rest + token expiry and flips `onboarding_storage_done`, `POST /disconnect` revokes at Google then clears locally; Storage tab gains Connect/Disconnect controls. Improvement pass added Google-side token revocation, a 409 for the no-config case, and a persisted `oauth_token_expires_at` (migration `b2c3d4e5f6a7`). **Human setup before it works live:** (1) register the Drive callback redirect URI + add the `drive` scope on the Google OAuth client (a "restricted" scope, may need verification); (2) create the `ENCRYPTION_KEY` secret (a `Fernet.generate_key()` value; wired into `ci.yml`/`deploy.yml` since #45, empty until then) — the callback can't store tokens without it.

## Completed Milestones

| Date | Milestone |
|------|-----------|
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
   - #47 Google Drive OAuth connect/disconnect + onboarding flag — 🔨 implemented on `feature/slice-2-gdrive-oauth` (last Slice 2 issue)
3. **Slice 3** — LLM Prompt page

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
