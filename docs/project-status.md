# OrganizeMe — Project Status

**Last updated:** 2026-07-02

---

## Current Phase

**Slice 1 in progress.** All prerequisites provisioned (issues #1–#9, closed). Slice 1 broken into 8 TDD-sized issues (#10–#17). Issues #10 (project scaffold + CI/CD, PR #18), #11 (DB foundation, PR #19), #12 (email/password auth, PR #20), #13 (Google OAuth login, PR #22), #14 (forgot/reset password, PR #21), and #15 (profile — view/edit, dark mode, account deletion, PR #24) are all merged into `main`; `ci.yml` (QA) and `deploy.yml` (prod) run green, and `/health`, `/register`/`/login` (incl. Google sign-in), `/forgot-password`/`/reset-password`, `/profile`, and `/api/v1/users/me` are confirmed live on both Cloud Run services. Issue #16 (landing page) implemented on branch `feature/slice-1-landing-page`, PR pending. Next up: merge #16, then #17.

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

Surfaced comparing issue #15's implementation against `docs/prd.md`; not implemented (out of #15's
scope), flagged here for a deliberate decision before or during the slice that would own each one.

6. **Duplicated DaisyUI card/form markup — now five templates deep, not four.** Suggestion #3 above
   named issue #15's own profile page as the trigger point to fix this before it recurred again;
   `app/templates/profile.html` shipped with the same copy-pasted `card`/`card-body`/`form-control`
   wrapper anyway, since extracting a shared macro would have meant touching four already-shipped,
   tested auth templates outside #15's scope. This is the second time this has been flagged without
   action — strongly worth doing before #16 (landing page) and #17 (sidebar shell) add more page
   chrome on top.
7. **No re-authentication required for account deletion.** PRD story #8 ("permanently delete my
   account") doesn't specify a confirmation mechanism; #15 implements a DaisyUI confirm modal but no
   password re-entry. For an immediate, no-grace-period deletion, consider requiring the current
   password before the DELETE fires, guarding against a hijacked-but-unattended session.
8. **Email change permanently strands `is_verified` at `False` with no way back.** `PATCH
   /api/v1/users/me` correctly resets `is_verified` when email changes (reusing fastapi-users'
   own `_update()` logic), but since no verify-email flow exists yet (see suggestion #1), there's
   currently no way for a user to ever become verified again after changing their email. Worth
   deciding this alongside suggestion #1 rather than independently.
9. **No security-notification email on email change.** A common baseline for account-integrity is
   notifying the *old* address when the login email changes, so a hijacker changing it doesn't go
   unnoticed. Not built for #15 — worth adding once the shared email-template mechanism (suggestion
   #2) exists.
10. **No documented decision on column-level encryption for `phone_number`.** PRD story #51 requires
    personal data "stored encrypted... at rest." Supabase/Postgres provides disk-level encryption by
    default, which likely satisfies this, but no explicit decision has been recorded confirming
    that's sufficient versus requiring column-level encryption for PII specifically — worth settling
    before Slice 2+ adds more PII (SMS numbers, storage credentials).

Surfaced comparing issue #16's implementation against `docs/prd.md`; not implemented (out of #16's
scope), flagged here for a deliberate decision before or during the slice that would own each one.

11. **No Open Graph / social-preview meta tags.** PRD story #50 wants "a clear, structured
    introduction to the product" for visitors; a link to `/` shared on social media or in a chat
    (ironically, exactly the kind of message OrganizeMe itself processes) currently renders as a bare
    URL with no preview card. Worth adding `og:title`/`og:description`/`og:image` once there's a
    product screenshot or logo asset to point `og:image` at.
12. **No `robots.txt` / sitemap / SEO discoverability decision.** The PRD doesn't mention search
    discoverability at all, and no explicit decision has been made on whether this product wants to
    be indexed by search engines pre-launch. Worth a deliberate call rather than defaulting to
    whatever crawlers do with an unconfigured site.
13. **No footer with privacy policy / terms of service links.** PRD stories #51/#52 (Security & Data
    Privacy) imply data-handling commitments to users, but there's nowhere on the public site linking
    to a privacy policy or terms of service — those pages don't exist yet either. Worth planning
    before public self-registration launches for real users.
14. **No favicon configured.** `base.html` (shared by every page, not just the landing page) has no
    `<link rel="icon">` — browsers show a default blank tab icon. Minor, but it's the kind of
    first-impression polish a public marketing page in particular should have.
15. **Undecided behaviour for an already-authenticated visitor landing on `/`.** Right now every
    visitor sees the marketing page regardless of session state. Once a dashboard exists (#17+),
    worth deciding whether a logged-in user hitting `/` should see the marketing page (current
    behaviour) or get redirected straight to their dashboard.

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
