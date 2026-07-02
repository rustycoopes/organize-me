# OrganizeMe — Project Status

**Last updated:** 2026-07-02

---

## Current Phase

**Slice 1 in progress.** All prerequisites provisioned (issues #1–#9, closed). Slice 1 broken into 8 TDD-sized issues (#10–#17), plus a 9th (#23) added 2026-07-02 to validate the whole slice with automated Playwright E2E tests. Issues #10 (project scaffold + CI/CD, PR #18), #11 (DB foundation, PR #19), #12 (email/password auth, PR #20), #13 (Google OAuth login, PR #22), #14 (forgot/reset password, PR #21), and #15 (profile — view/edit, dark mode, account deletion, PR #24) are all merged into `main`; `ci.yml` (QA) and `deploy.yml` (prod) run green, and `/health`, `/register`/`/login` (incl. Google sign-in), `/forgot-password`/`/reset-password`, `/profile`, and `/api/v1/users/me` are confirmed live on both Cloud Run services. Issue #16 (landing page) implemented on branch `feature/slice-1-landing-page`, PR pending. Next up: merge #16, then #17.

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
| 2026-07-02 | Issue #16 (landing page) implemented on branch `feature/slice-1-landing-page` — `GET /` (public, no auth) renders a DaisyUI hero/features/CTA landing page with nav links to `/login`/`/register`; added a reusable `{% block head %}` extension point to `base.html` (used here for a meta description, available to future pages). Small enough in scope to implement directly rather than dispatch multiple agents. 5 improvements applied after comparing against issue #16's acceptance criteria: a meta description tag, a second CTA path (login) for returning visitors, broadened test coverage confirming the hero's CTA (not just the dedicated CTA section) links to `/register`, a nav-links-present test, and a regression test that `/login`/`/register` actually resolve to 200 (guards against a typo'd `href` silently breaking navigation) |
| 2026-07-02 | Added issue #23 (Slice 1.8: automated Playwright E2E tests) to validate Slice 1's overall UX delivery against the deployed QA Cloud Run instance, at the user's request. Decided with the user: tests target the real QA deploy (new `e2e-qa` CI job after `deploy-qa`, becomes a required check going forward); Google OAuth is excluded from E2E (unreliable to drive headlessly) and stays on backend tests only; the forgot/reset-password flow uses a new debug-only `/api/v1/internal/e2e/last-reset-token` endpoint (gated by `E2E_TEST_MODE`, QA-only) instead of a real inbox. Blocked by #15/#16/#17 since it exercises profile, landing, and sidebar pages that don't exist yet |

## Next Steps

1. **Implement Slice 1, in order:**
   - #10 Project scaffold + CI/CD pipeline — ✅ merged
   - #11 DB foundation — Supabase connection + `users` table — ✅ merged
   - #12 Email/password auth — register, login, logout — ✅ merged
   - #13 Google OAuth login — ✅ merged
   - #14 Forgot / reset password — ✅ merged
   - #15 Profile — view/edit, dark mode, account deletion — ✅ merged
   - #16 Landing page — ✅ implemented, PR pending
   - #17 Sidebar shell + placeholder pages
   - #23 Automated E2E UX tests (Playwright, against QA deploy) — validates the full slice; blocked by #15–#17
2. **Slice 2** — Google Drive storage integration
3. **Slice 3** — LLM Prompt page

## Open Decisions

- None — all design questions resolved in `docs/implementation-plan.md`

## Suggestions for Future Review

The improvement/decision items surfaced while reviewing Slice 1 issues #14–#16 against
`docs/prd.md` are now tracked as GitHub issues **#29–#42** in the OrganizeMe project, each tagged
`future-enhancement` + `slice1`. (The duplicated-DaisyUI-markup item, flagged during both #14 and
#15, was consolidated into a single issue.) See the OrganizeMe project board for current status.

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
