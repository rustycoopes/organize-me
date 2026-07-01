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
