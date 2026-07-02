# OrganizeMe — Changelog

---

## [Unreleased]

### Fixed
- **Post-merge prod deploy hotfixes** (direct to `main`, after PR #19 merged): `alembic upgrade
  head` failed in CI with `ValueError: invalid interpolation syntax` — Alembic's `env.py` routed
  `DATABASE_URL` through `config.set_main_option()`/`async_engine_from_config()`, both backed by
  Python's `configparser`, whose `BasicInterpolation` treats a literal `%` (present in the real
  `SUPABASE_QA_URL` secret's percent-encoded password) as an interpolation reference. Fixed by
  bypassing configparser storage entirely and passing the URL straight to `create_async_engine`.
  Separately, `deploy.yml`'s prod deploy gate then failed with `OSError: Network is unreachable`
  — the `SUPABASE_PROD_URL` secret still used Supabase's IPv6-only direct-connection host, same
  as `SUPABASE_QA_URL` had; updated to the Session/Transaction Pooler URL. Prod's pooler runs in
  transaction mode (port 6543, vs QA's session mode on 5432), which breaks asyncpg's default
  prepared-statement cache under PgBouncer — every async engine construction in the repo
  (`app/db/session.py`, `migrations/env.py`, `tests/conftest.py`) now passes
  `connect_args={"statement_cache_size": 0}` to work around it. `test` and `deploy-prod` are now
  green on `main`; prod `/health` confirmed live.

### Added
- **Issue #10 implemented** — project scaffold + CI/CD pipeline (branch `feature/slice-1-scaffold-cicd`):
  - `pyproject.toml` (uv-managed), FastAPI app skeleton (`app/main.py`) with `GET /health`,
    Jinja2 templates + static file wiring, `app/worker.py` Celery stub
  - `Dockerfile` + `supervisord.conf` — app (uvicorn) and worker (Celery) run as separate
    processes in one container
  - `.github/workflows/ci.yml` (PR: pytest + mypy --strict + Docker build/push + deploy to
    Cloud Run QA) and `deploy.yml` (main merge: same gate + deploy to Cloud Run prod), targeting
    the already-provisioned `organizeme` Artifact Registry repo and `organizeme-qa`/`organizeme-prod`
    Cloud Run services in `gen-lang-client-0791944342` / `northamerica-northeast1`
  - `.env.local.example` documenting every variable used by `.env.local`
  - `tests/test_health.py` — first test, written before the implementation (TDD red/green)
  - Multi-agent code review surfaced and fixed: the Celery worker was set to autostart under
    supervisord with no `REDIS_URL` wired through the deploy workflows, which would have
    crash-looped it silently in QA/prod while `/health` stayed green — worker autostart is now
    `false` until a later slice wires the secret through; CI's `uv sync` now uses `--frozen` so a
    stale `uv.lock` fails fast in the test job instead of only in the Docker build; CI dependency
    caching enabled via `setup-uv`'s `enable-cache`. Remaining lower-priority review notes
    (ci.yml/deploy.yml step duplication, no fork-PR secret guard) logged as follow-ups, not fixed
    in this issue.
- **Issue #11 implemented** — DB foundation: Supabase connection + `users` table (branch
  `feature/slice-1-db-foundation`):
  - New dependencies: `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `fastapi-users-db-sqlalchemy`,
    `pydantic-settings`
  - `app/core/config.py` — pydantic-settings `Settings` class reading `DATABASE_URL` and other
    env vars
  - `app/db/base.py` and `app/db/session.py` — SQLAlchemy 2.0 async engine/session setup wired to
    Supabase QA via `DATABASE_URL`
  - `app/models/user.py` — `users` table built on fastapi-users-db-sqlalchemy's
    `SQLAlchemyBaseUserTableUUID` mixin, plus `name`, `phone_number`, `dark_mode`,
    `notification_sms`, `notification_email`, `onboarding_storage_done`,
    `onboarding_notifications_done`, `onboarding_first_upload_done`, `created_at`, `updated_at`
  - Alembic initialised in async mode, with a first migration creating the `users` table
  - `tests/conftest.py` — pytest fixture that opens a transaction/savepoint against the real
    Supabase QA database and rolls it back after each test; chosen over a local Docker Postgres
    (none is used in this project) so tests exercise the real QA database while guaranteeing no
    test data is ever persisted
  - `tests/test_db_session.py` — smoke test inserting and reading back a user row
  - `.github/workflows/ci.yml` and `deploy.yml` test jobs updated to pass
    `secrets.SUPABASE_QA_URL` / `secrets.SUPABASE_PROD_URL` as `DATABASE_URL` and run
    `alembic upgrade head` before pytest
  - Discovered Supabase's direct-connection host (`db.<project-ref>.supabase.co`) is IPv6-only
    and unreachable from networks without an IPv6 route; switched `.env.local`'s `DATABASE_URL`
    to the Session Pooler connection string (IPv4-compatible) instead, and updated
    `.env.local.example` to document the pooler format and this gotcha. Also fixed
    `.env.local`'s `DATABASE_URL` password, which had been left wrapped in literal square
    brackets (`[password]`) from Supabase's dashboard placeholder template
  - `alembic upgrade head` / `alembic downgrade base` verified against the real Supabase QA
    database (table created, then cleanly dropped, then re-created to leave QA in the expected
    state)
  - Five improvements applied after comparing the implementation against the PRD and issue #11:
    (1) `email` uniqueness enforced case-insensitively via a functional unique index on
    `lower(email)`, matching how `fastapi-users-db-sqlalchemy`'s `get_by_email` already looks
    users up — without this, `Foo@x.com` and `foo@x.com` could register as two accounts (covered
    by `test_email_uniqueness_is_case_insensitive`); (2) `name` made nullable — issue #12's
    register endpoint only accepts email/password, so a `NOT NULL` `name` with no default would
    have made every registration fail at the DB layer; (3) `app/main.py`'s lifespan now calls
    `await engine.dispose()` on shutdown so the async connection pool doesn't leak across app
    restarts/reloads; (4) `tests/test_config.py` added to confirm `Settings` reads `DATABASE_URL`
    from a bare environment variable with no `.env.local` file present, matching how CI actually
    supplies it; (5) an automated `alembic downgrade base` / `upgrade head` round-trip test was
    initially added, then **removed** after multi-agent review (see below) — running destructive
    DDL inside the regular pytest suite is unsafe once that suite is wired to real QA/prod
    databases in CI, so migration reversibility remains a manually-verified step instead
  - Multi-agent code review (4 parallel finder agents: correctness, reuse/simplification/
    efficiency, altitude, CLAUDE.md conventions) caught a critical issue before commit: the
    `tests/test_migrations.py` round-trip test (added as improvement 5 above) ran
    `alembic downgrade base` — a `DROP TABLE users` — inside `deploy.yml`'s `test` job, which
    gates every merge to `main` and was wired to `secrets.SUPABASE_PROD_URL`. Every push to
    `main` would have dropped and recreated the production `users` table as a side effect of
    running the test suite. Fixed by deleting that test entirely; `alembic upgrade head` (additive,
    idempotent) is the only migration command CI ever runs automatically. Review also caught:
    `_asyncpg_url`'s naive `str.replace` didn't handle the `postgres://` URL scheme some hosts use
    — replaced with `sqlalchemy.engine.make_url()`-based rewriting and moved to `app/db/url.py`
    (`to_asyncpg_url`) so importing it no longer has the side effect of constructing the app's
    singleton engine (previously happened on every Alembic invocation via `app.db.session`); model
    registration for Alembic's autogenerate centralised in `app/models/__init__.py` instead of a
    one-off import per model in `migrations/env.py`; and `tests/conftest.py`'s `db_session` fixture
    now builds and disposes its own dedicated engine per test instead of reusing
    `app.db.session`'s process-wide singleton, which let the earlier `asyncio_default_fixture_loop_scope`/
    `asyncio_default_test_loop_scope = "session"` workaround in `pyproject.toml` (a global change
    affecting every async test in the repo) be reverted back to pytest-asyncio's per-test default
  - A second review pass (re-running the same 8-angle finder set against the post-fix diff)
    caught two more real issues: `to_asyncpg_url` rewrote the URL scheme but left any query
    string untouched, so a `DATABASE_URL` with `?sslmode=require` (a common libpq-style
    connection-string convention) would reach `asyncpg.connect()`, which has no `sslmode` kwarg,
    and raise `TypeError` on the first real connection — `sslmode` is now stripped before
    rendering the URL. Separately, `app/main.py` had gained a top-level
    `from app.db.session import engine` (for the shutdown-dispose fix above), which meant even
    `tests/test_health.py` — a test with no DB involvement — now required `DATABASE_URL`/
    `.env.local` just to import `app.main`; the import was moved inside the `lifespan` function
    body so DB config is only resolved when the app actually starts, not merely when the module
    is imported. Verified by importing `app.main` directly with `DATABASE_URL` unset — succeeds.
  - Known, accepted forward-looking risk (not fixed here, flagged for #12): `app/db/session.py`'s
    `engine` remains a single process-wide singleton, which is correct for the real running app
    (one process, one event loop under uvicorn) but would hit the same asyncpg-connection/
    event-loop-binding problem `tests/conftest.py` was fixed for if a future test suite (e.g.
    issue #12's auth tests) uses `TestClient`/`get_db` against this singleton across multiple
    pytest-asyncio test functions. #12's DB-backed test fixtures should follow the same
    dedicated-per-test-engine pattern established in `tests/conftest.py::db_session`, not reuse
    `app.db.session.engine` directly, if they exercise real DB-backed endpoints.
- **Issue #12 implemented** — email/password auth: register, login, logout (branch
  `feature/slice-1-auth-register-login`):
  - FastAPI-Users v15 wired up with a **bcrypt-only** `PasswordHelper` (the library defaults to
    Argon2 for new hashes; `docs/technical-approach.md` and issue #12 both specify bcrypt), a
    cookie-based JWT backend (`organizeme_auth` cookie, HttpOnly, `SameSite=Lax`, 7-day
    max-age/token lifetime), and a `UserManager` enforcing an 8-character minimum password
  - Custom `POST /api/v1/auth/register`, `/login`, `/logout` under `app/api/v1/auth.py` rather
    than fastapi-users' built-in routers: the built-in login route returns 400 on bad
    credentials, but issue #12's acceptance criteria require 401; register/login accept
    `application/x-www-form-urlencoded` (`Form(...)`) instead of JSON so the plain HTML
    `<form method="post">` pages work without any JS
  - `GET /api/v1/users/me` (protected, `app/api/v1/users.py`) and matching DaisyUI (CDN)
    Jinja2 register/login pages at `GET /register` / `GET /login` (`app/templates/auth/`)
  - Resolved the "known, accepted forward-looking risk" #11 flagged for #12: `app/db/session.py`'s
    `engine` singleton was rebuilt as a lazily-constructed, `lru_cache`d `get_engine()` instead of
    an import-time side effect, so wiring the auth routers permanently into `app/main.py` doesn't
    force `DATABASE_URL`/`JWT_SECRET` resolution just by importing the module (`test_health.py`
    still imports `app.main` with no DB config). Tests use a new `client` fixture
    (`tests/conftest.py`) that overrides `get_db` with the existing `db_session` fixture's
    dedicated-per-test engine, exactly the pattern #11 called out — not the process-wide singleton
  - Discovered and fixed a live-deployment gap while wiring this up: the QA/prod Cloud Run
    `gcloud run deploy` steps in `ci.yml`/`deploy.yml` had **zero** environment variables set on
    the actual running services (only the CI *test job* had `DATABASE_URL`) — register/login
    would have 500'd in the real deployed app despite green CI. Added a `JWT_SECRET_QA`/
    `JWT_SECRET_PROD` GitHub secret pair and a `--env-vars-file` deploy step (secrets piped through
    a step `env:` block and shell `${VAR}` expansion, not GH Actions' `${{ }}` template
    substitution directly in the script body, to avoid the injection footgun that approach has
    with secret values containing shell-special characters)
  - `cookie_secure` defaults to `true` (required for the `Secure` flag Cloud Run's real HTTPS
    needs) but is a plain `os.environ` read (`COOKIE_SECURE`), not routed through the pydantic
    `Settings` class, so building the cookie transport at import time never requires
    `DATABASE_URL`. Real browsers treat `http://localhost` as a secure context and accept `Secure`
    cookies there regardless, but non-browser HTTP clients (httpx, curl) don't get that exception
    and would silently never resend the cookie over plain `http://`; `tests/conftest.py` sets
    `COOKIE_SECURE=false` before any app module import so the test suite's httpx client works
  - Five improvements applied after comparing the implementation against the PRD and issue #12:
    (1) login hashes the submitted password even when the email doesn't exist (result discarded),
    mirroring `BaseUserManager.authenticate`'s own mitigation, so response timing doesn't leak
    which emails are registered; (2) register catches `IntegrityError` from a concurrent
    duplicate-email insert racing past the pre-insert existence check (Cloud Run runs multiple
    instances) and returns the same clean 400 instead of a raw 500; (3) `register`/`login` bind
    `email` as `pydantic.EmailStr` at the FastAPI parameter layer instead of `str` — with `str`,
    a malformed email reached `UserCreate(...)`'s own `EmailStr` validation *inside* the handler
    body, which FastAPI doesn't auto-convert to a 4xx the way it does for route-parameter
    validation, so malformed input 500'd instead of 400ing (caught by a new
    `test_register_with_malformed_email_returns_4xx_not_500`); (4) the lazy `get_engine()` refactor
    and (5) the `--env-vars-file` Cloud Run wiring, both described above
  - `app/models/user.py`'s `email` column is now typed as plain `str` under `TYPE_CHECKING`
    (matching `SQLAlchemyBaseUserTableUUID`'s own convention) rather than `Mapped[str]`, so `User`
    keeps satisfying fastapi-users' `UserProtocol` structurally under `mypy --strict` — re-declaring
    it as `Mapped[str]` to override the base mixin's unique index shadowed the base class's
    Protocol-compatible annotation. This is a known, deliberate trade-off in the
    fastapi-users-db-sqlalchemy package itself (not something #12 introduced) that makes
    SQLAlchemy query expressions like `User.email == ...` type as `bool` instead of
    `ColumnElement[bool]` under mypy; `tests/test_db_session.py`'s pre-existing query needed one
    scoped `# type: ignore[arg-type]`
- **Issue #13 implemented** — Google OAuth login (branch `feature/slice-1-google-oauth`):
  - New dependency `httpx-oauth`; `app/auth/oauth.py`'s `get_google_oauth_client()` builds a
    `GoogleOAuth2` client lazily from `GOOGLE_OAUTH_CLIENT_ID`/`_SECRET` settings (mirrors
    `app/auth/backend.py`'s `get_jwt_strategy()` pattern) — overridable in tests with a fake
    client that never calls Google, per the issue's "no live Google credentials touched" requirement
  - `app/models/oauth_account.py` — `OAuthAccount` table (`fastapi-users-db-sqlalchemy`'s
    `SQLAlchemyBaseOAuthAccountTableUUID` mixin, with `user_id`'s FK re-pointed at this app's
    `users` table instead of the mixin's hardcoded default `user`); `User.oauth_accounts`
    relationship wired in; new Alembic migration
  - Custom `GET /api/v1/auth/google` (redirects to Google's consent URL — issued as a real
    302, unlike fastapi-users' built-in `get_oauth_router`, which returns JSON) and
    `GET /api/v1/auth/google/callback` (exchanges the code, then reuses fastapi-users'
    `UserManager.oauth_callback()` — same create-or-reuse-by-oauth-account logic the library
    uses internally — and logs in through the existing `auth_backend`, setting the identical
    `organizeme_auth` JWT cookie as email/password login)
  - Anti-CSRF `state`: a short-lived signed JWT (embedding a random token + the originating
    page) plus a matching HTTPOnly double-submit cookie, checked at the callback — the same
    pattern fastapi-users' own OAuth router uses internally, hand-rolled here because the
    redirect requirement above rules out reusing the router directly
  - Account linking: a Google sign-in whose email matches an existing email/password account is
    linked to it (`associate_by_email=True`) rather than rejected, and marked verified without a
    separate step since Google already verified the address (`is_verified_by_default=True`) —
    documented in `docs/technical-approach.md`'s Authentication section
  - "Sign in with Google" button (with Google's four-colour "G" mark) added to the login and
    register DaisyUI pages
  - Five improvements applied after comparing the implementation against issue #13's acceptance
    criteria: (1) Google consent errors/cancellations (`error=access_denied`) now redirect back to
    the originating page with a friendly banner instead of a raw 400 body, since this endpoint is
    only ever reached via full-page browser navigation; (2) the originating page (login vs
    register) is preserved through the OAuth round trip via a `next` param embedded in the signed
    state, restricted to an allowlist to avoid an open redirect; (3) the CSRF cookie is cleared on
    every exit path, not just success; (4) the sign-in buttons render Google's own four-colour "G"
    icon instead of plain text; (5) test coverage added for the cancellation/error-redirect path
    on both origin pages
  - Multi-agent code review (8 parallel finder angles, then 1-vote verification) caught three real
    bugs before commit, all fixed: Google's token/profile exchange
    (`get_access_token`/`get_id_email`) wasn't wrapped in error handling, so a replayed/expired
    authorization code raised an unhandled exception → raw 500 instead of the graceful redirect
    every other failure path uses; concurrent first-time Google logins for the same email had no
    `IntegrityError` guard around the race (unlike the identical race `register()` already
    guards, whose comment explains the Cloud Run multi-instance scenario), and the paired
    `except UserAlreadyExists` was unreachable dead code since `associate_by_email=True` is always
    passed; `secrets.compare_digest` raises `TypeError` (not a clean `False`) on a non-ASCII CSRF
    cookie value, which an attacker-controlled raw HTTP client can send directly. Also fixed: the
    `next`-path allowlist validation was duplicated with slightly different shapes between the two
    endpoints, unified into one `_sanitize_next()` helper. One finding was confirmed but
    deliberately left unchanged: `User.oauth_accounts`'s `lazy="joined"` (required by
    fastapi-users' own async-SQLAlchemy pattern for `add_oauth_account`) puts a `LEFT JOIN`
    against `oauth_accounts` on every `User` load app-wide, not just the Google login path —
    documented as an accepted trade-off in `app/models/user.py` rather than reworked, since
    `selectin` would only trade the join for an equally-unconditional second query
  - Discovered mid-implementation that another Claude Code session was concurrently working on
    issue #14 in the same shared working directory (`C:\dev\organize-me`), which had already
    checked out `feature/slice-1-forgot-reset-password` and made uncommitted changes; moved this
    issue's work into an isolated git worktree (`.claude/worktrees/slice-1-google-oauth`) rather
    than risk clobbering it
- **Issue #14 implemented** — forgot/reset password (branch `feature/slice-1-forgot-reset-password`,
  picked up ahead of #13 per direct request):
  - `app/services/notifications/email.py` — the first cut of the email-sending interface Slice 7
    (Notifications) will reuse: an `EmailSender` protocol (`to`/`subject`/`html`), `ResendEmailSender`
    (wraps the `resend` SDK's blocking client in `asyncio.to_thread`), and `FakeEmailSender` (records
    sent messages; used everywhere in the test suite so no test ever calls the real Resend API)
  - `app/core/config.py` — `resend_api_key` (default `""`) and `email_from` (default Resend's shared
    sandbox sender, `OrganizeMe <onboarding@resend.dev>`, which works without a verified custom
    domain but only delivers to the Resend account owner's own address until one is verified)
  - `UserManager.on_after_forgot_password` (`app/auth/users.py`) sends the reset-link email; the
    link's origin is built from the *incoming request's* `base_url` rather than a static `BASE_URL`
    setting, so it's correct on both the QA and prod Cloud Run domains with no extra per-environment
    config. Token single-use behaviour comes for free from fastapi-users' own design: the JWT embeds
    a fingerprint of the current password hash, so a token stops verifying the moment the password
    it was issued for has already been changed
  - `POST /api/v1/auth/forgot-password` / `/reset-password` (`app/api/v1/auth.py`) and matching
    DaisyUI pages at `GET /forgot-password` / `/reset-password` (`app/templates/auth/`)
  - `tests/conftest.py`'s `client` fixture now also overrides `get_email_sender` with a
    `FakeEmailSender`, exposed via a new `fake_email_sender` fixture so tests can assert on the
    stub's call args
  - Five improvements applied after comparing the implementation against issue #14: (1) a "Forgot
    password?" link added to the login page — without it, #14's flow would have been functionally
    complete but undiscoverable from the existing UI; (2) a confirm-password field added to the
    reset-password form, with a server-side match check (`RESET_PASSWORD_PASSWORD_MISMATCH`, 400 on
    mismatch) so a typo in the new password can't silently lock the user out; (3)
    `test_forgot_password_email_lookup_is_case_insensitive` added — forgot-password relies on the
    same case-insensitive `get_by_email` lookup #11/#12 already established, but this was previously
    unverified for this endpoint; (4)
    `test_reset_password_below_minimum_length_returns_400` added — confirms the 8-character minimum
    password policy (`UserManager.validate_password`) is also enforced on the reset path, not just
    register; (5) `RESEND_API_KEY` proactively wired into both `ci.yml` and `deploy.yml`'s Cloud Run
    `--env-vars-file` step, closing the exact "secret exists in GitHub but was never wired to the
    running service" gap class that #10 (Celery worker env vars) and #12 (`JWT_SECRET`) both hit
    post-merge, instead of discovering it after this merges
  - Found a pre-existing uncommitted change on `main` when starting this issue (an `httpx-oauth`
    dependency added to `pyproject.toml`/`uv.lock`, unrelated to #14 — likely unfinished local prep
    for #13's Google OAuth work); stashed separately rather than discarding or folding it into this
    branch
  - Multi-angle code review (8 finder angles, 1-vote verify) caught three real issues, all fixed:
    (1) a failure calling the email provider (bad/missing `RESEND_API_KEY`, Resend outage) inside
    `on_after_forgot_password` was unhandled and would 500 — but *only* for registered emails,
    which itself leaks account existence via status code even though the response body was
    already identical for both cases; now caught and logged, endpoint always returns 200;
    (2) `reset_password`'s exception handling didn't cover `UserNotExists`, which
    `BaseUserManager.reset_password` raises internally if the account the token was issued for
    was deleted before the token was used — now mapped to the same generic bad-token 400; (3)
    uvicorn's default `--forwarded-allow-ips=127.0.0.1` doesn't trust Cloud Run's actual proxy
    peer address, so `request.base_url` (used to build the emailed reset link) could report
    `http://` instead of `https://` in prod/QA — fixed by adding `--proxy-headers
    --forwarded-allow-ips='*'` to `supervisord.conf`'s uvicorn command (safe here because Cloud
    Run containers are only ever reachable through Google's own proxy, never directly; confirmed
    with the user before applying since it's a deploy-config security setting). Two more
    review-flagged findings were accepted as known, unfixed follow-ups: forgot-password's response
    *body* is identical for known/unknown emails, but response *timing* isn't (a known email pays
    for JWT generation + a live Resend network call the unknown-email path skips) — a full fix
    would need to fire an equivalent-cost dummy operation on the unknown-email path, which isn't
    straightforward for a network-bound call and wasn't attempted here; and the four DaisyUI auth
    templates (`login.html`, `register.html`, and the two new pages) now duplicate the same
    card/form markup four times over — flagged as a good trigger point for a shared Jinja
    include/macro in a future cleanup pass, not done here to avoid touching `login.html`/
    `register.html` beyond issue #14's scope
- GitHub issues #10–#17 — Slice 1 (Project Scaffold + Auth + CI/CD) broken into 8 TDD-sized,
  independently-gradable vertical slices and published to the OrganizeMe project: scaffold +
  CI/CD (#10), DB foundation (#11), email/password auth (#12), Google OAuth (#13),
  forgot/reset password (#14), profile + dark mode + account deletion (#15), landing page (#16),
  sidebar shell (#17). See `docs/implementation-plan.md` § Slice 1 for the source scope.
- GitHub issue #23 — Slice 1.8: automated Playwright E2E UX tests, added at the user's request to
  validate Slice 1's overall delivery rather than just its individual pieces. Targets the deployed
  QA Cloud Run instance via a new `e2e-qa` CI job (runs after `deploy-qa`, becomes a required check
  going forward). Google OAuth is out of scope for E2E (unreliable to drive headlessly against
  Google's real consent screen) and stays covered by #13's backend tests. Forgot/reset-password
  is tested via a new debug-only `GET /api/v1/internal/e2e/last-reset-token` endpoint (gated by
  `E2E_TEST_MODE`, wired to QA's Cloud Run env vars only, 404s when unset) instead of a real inbox
  or mail-testing service. Blocked by #15/#16/#17 since it exercises profile, landing, and sidebar
  pages those issues haven't built yet.
- `docs/slice-1-plan.md` — full implementation design spec: confirmed stack decisions, complete
  database schema (5 tables), API endpoint map (21 endpoints), 9 vertical implementation slices,
  key utilities, testing approach, and prerequisites checklist. Produced from structured Q&A
  session resolving all open design questions (component library, auth session length, storage
  provider build order, pagination, sort defaults, pipeline failure handling, notifications
  styling, onboarding steps, and more).

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
