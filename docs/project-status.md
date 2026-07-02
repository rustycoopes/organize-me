# OrganizeMe — Project Status

**Last updated:** 2026-07-02

---

## Current Phase

**Slice 1 in progress.** All prerequisites provisioned (issues #1–#9, closed). Slice 1 broken into 8 TDD-sized issues (#10–#17). Issues #10 (project scaffold + CI/CD, PR #18), #11 (DB foundation, PR #19), #12 (email/password auth, PR #20), #13 (Google OAuth login, PR #22), and #14 (forgot/reset password, PR #21) are all merged into `main`; `ci.yml` (QA) and `deploy.yml` (prod) run green, and `/health`, `/register`/`/login` (incl. Google sign-in), and `/forgot-password`/`/reset-password` are confirmed live on both Cloud Run services. Next up: #15.

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

## Next Steps

1. **Implement Slice 1, in order:**
   - #10 Project scaffold + CI/CD pipeline — ✅ merged
   - #11 DB foundation — Supabase connection + `users` table — ✅ merged
   - #12 Email/password auth — register, login, logout — ✅ merged
   - #13 Google OAuth login — ✅ merged
   - #14 Forgot / reset password — ✅ merged
   - #15 Profile — view/edit, dark mode, account deletion
   - #16 Landing page
   - #17 Sidebar shell + placeholder pages
2. **Slice 2** — Google Drive storage integration
3. **Slice 3** — LLM Prompt page

## Open Decisions

- None — all design questions resolved in `docs/implementation-plan.md`

## Suggestions for Future Review

Surfaced comparing issue #14's implementation against `docs/prd.md`; not implemented (out of #14's
scope), flagged here for a deliberate decision before or during the slice that would own each one.

1. **Email verification (`is_verified`) not enforced.** Self-registration currently lets anyone
   register with an email address they don't own — nothing in the PRD's Security & Data Privacy
   section explicitly requires enforcing verification, but it's implied by "cloud storage
   credentials... never exposed" and general account-integrity expectations. Worth deciding whether
   to require a verified email before password reset / account actions, or accept the current
   open-registration model as-is.
2. **No shared email-template mechanism yet.** The forgot-password email
   (`app/auth/users.py::on_after_forgot_password`) is a hand-rolled HTML f-string. The PRD's
   Notifications section (user stories #40–#43) describes "rich HTML email" with branding and a
   summary table for Slice 7 — worth building a shared Jinja-based email template (header/footer,
   consistent styling) before Slice 7 adds 2+ more transactional email types, rather than each flow
   hand-rolling its own HTML.
3. **Duplicated DaisyUI auth template markup.** `login.html`, `register.html`,
   `forgot_password.html`, and `reset_password.html` now all repeat the same card/form wrapper
   markup four times. A shared Jinja include/macro would pay off before more auth-adjacent pages are
   added (e.g. Slice 1's own #15 profile page, or a future verify-email page).
4. **No rate limiting on `/api/v1/auth/forgot-password`.** Low risk at personal scale, but the
   endpoint can be used to spam an arbitrary user's inbox with reset emails with no cost to the
   caller. Worth a Redis-backed limiter once Slice 2 wires up Upstash Redis for the app (currently
   only referenced for Celery).
5. **Forgot-password response-timing side channel.** The response *body* is identical for
   known/unknown emails, but a known email pays for JWT generation + a live Resend network call the
   unknown-email path skips, so response latency can still distinguish registered from unregistered
   addresses. A full fix would need an equivalent-cost dummy operation on the unknown-email path;
   not attempted in #14 since it's awkward for a network-bound call. Documented as an accepted,
   unfixed risk in `docs/changelog.md`'s #14 entry.

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
