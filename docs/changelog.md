# OrganizeMe — Changelog

---

## [Unreleased]

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
- GitHub issues #10–#17 — Slice 1 (Project Scaffold + Auth + CI/CD) broken into 8 TDD-sized,
  independently-gradable vertical slices and published to the OrganizeMe project: scaffold +
  CI/CD (#10), DB foundation (#11), email/password auth (#12), Google OAuth (#13),
  forgot/reset password (#14), profile + dark mode + account deletion (#15), landing page (#16),
  sidebar shell (#17). See `docs/implementation-plan.md` § Slice 1 for the source scope.
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
