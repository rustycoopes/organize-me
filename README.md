# OrganizeMe (Host)

The **Host** application in the OrganizeMe platform: owns authentication, account/profile
management, the Settings-page shell, and the sidebar/nav chrome shared by every hosted app.

---

## What is it?

`organize-me` used to be a single monolith that also watched cloud storage, ran an LLM
extraction pipeline, and served an events dashboard. As of the Platform Restructure (see
[`docs/features/platform-restructure/`](docs/features/platform-restructure/)), all of that event-extraction
functionality — upload, the processing pipeline, storage connections, LLM prompt config, the
events dashboard, and processing logs — has moved to its own independent service,
**[event-creator](https://github.com/rustycoopes/event-creator)**. Slice R13 (issue #168) removed
the Host's now-dead copies of that code.

The Host is now purely the platform's identity provider and shared UI chrome:

- **Auth** — registration, login/logout, Google OAuth, password reset, JWT issuance
  (`organizeme_auth` HTTPOnly cookie) that every hosted app trusts.
- **Profile** — name, email, phone number, dark-mode preference, account deletion.
- **Settings shell** — renders the tab-bar chrome; each tab's actual content is an HTML fragment
  served by whichever app owns it (today, entirely `event-creator`).
- **Nav shell** — the sidebar, merged from every hosted app's app-registry entry
  (`organizeme_chrome.registry`), so users see one consistent sidebar regardless of which service
  rendered the current page.

For "what does OrganizeMe do end-to-end" (the WhatsApp/SMS-to-calendar-events product), see
`event-creator`'s own README — that's where the extraction pipeline, dashboard, storage
integrations, and notifications now live.

---

## Adding a new hosted app

See [`docs/how-to-add-a-hosted-app.md`](docs/how-to-add-a-hosted-app.md)
for the concrete playbook (app-registry entry, LB URL-map regeneration, the `organizeme-chrome`
shared package, and the JWT-verify pattern), validated against the real `event-creator`
integration.

---

## Development

**Stack:** Python 3.12 + FastAPI, managed with [uv](https://docs.astral.sh/uv/). See [Technical Approach](docs/features/original-organize-me/technical-approach.md) for the full stack.

### Setup

```bash
uv sync --group dev          # install runtime + dev dependencies into .venv
cp .env.local.example .env.local   # fill in real values (never commit .env.local)
```

### Run locally

```bash
uv run uvicorn app.main:app --reload
```

The app serves `GET /health` for a liveness check. Local dev connects directly to the Supabase QA database and Upstash Redis via `.env.local` — no local Docker required for either.

### CSS (Tailwind)

The compiled stylesheet (`app/static/css/app.css`) isn't wired into `uvicorn --reload` — run its
own watcher in a second terminal alongside the app:

```bash
uv sync --group build           # installs pytailwindcss (build-only; not part of `dev`)
uv run python scripts/build_css.py --watch
```

This recompiles on every change to this app's own templates or `packages/chrome`'s shared
templates/tokens. A one-shot, minified build (what the Docker build stage runs) is the same
command without `--watch`:

```bash
uv run python scripts/build_css.py
```

See [ADR: per-service Tailwind build](docs/adr/design-refresh-per-service-tailwind-build.md) and
[ADR: dark-mode CSS strategy](docs/adr/design-refresh-dark-mode-css-strategy.md) for why each
service compiles its own CSS and how dark mode stays DB-driven.

### Test & type-check

```bash
uv run pytest
uv run mypy app tests
```

### End-to-end tests (Playwright)

The `e2e/` folder holds a Playwright/TypeScript suite that drives the **real deployed QA app**
end-to-end (landing, register/login/logout, forgot/reset password, profile edit, dark-mode
persistence, account deletion, sidebar nav). It's separate from the Python `pytest` suite and runs
in CI as the `e2e-qa` job after QA deploys. It also keeps `host-event-creator-boundary.spec.ts`,
which asserts the Host↔Event-Creator seam (JWT cookie flowing cross-app, shared sidebar rendering)
rather than either app's internals — the rest of the former event-extraction specs
(upload/processing/storage/prompt/logs/dashboard/notifications) moved to `event-creator`'s own
`e2e/` suite in R13 (#168), since that's the code they exercise.

```bash
cd e2e
npm ci
npx playwright install --with-deps chromium
npx playwright test                     # targets QA by default
PLAYWRIGHT_BASE_URL=http://localhost:8000 npx playwright test   # or a local run
```

The forgot/reset test reads a reset token from a **test-only** endpoint
(`GET /api/v1/internal/e2e/last-reset-token`) that only exists when `E2E_TEST_MODE=true`.
That flag is set on QA's Cloud Run env vars **only** — never prod, where the endpoint 404s.

### Docker

```bash
docker build -t organize-me .
docker run --env-file .env.local -p 8000:8000 organize-me
```

The container runs the FastAPI app under `supervisord` (a single process now — the Celery worker
that used to run alongside it was removed in R13 along with the Host's other event-extraction
code; see `supervisord.conf`). The image build is multi-stage: a build stage compiles
`app/static/css/app.css` via `pytailwindcss`; only that compiled artifact (never the ~35-40MB
Tailwind CLI binary or the `build` dependency group) is copied into the runtime stage.

### CI/CD

GitHub Actions (`.github/workflows/ci.yml`, `deploy.yml`) run `pytest` + `mypy --strict`, then build and push the Docker image to Artifact Registry and deploy to Cloud Run — QA on every PR, prod on merge to `main`. On PRs, a final `e2e-qa` job runs the Playwright suite against the freshly-deployed QA instance and uploads an HTML report artifact on failure.

---

## Security

- Passwords are bcrypt-hashed; auth JWTs live in an HTTPOnly, Secure cookie
- `.env` and `.env.local` files are excluded from source control
- Cloud storage credentials, conversation content, and other event-extraction data are entirely
  `event-creator`'s concern now — see that repo for its own security notes

---

## Project Documentation

| Document | Description |
|----------|-------------|
| [PRD](docs/features/original-organize-me/prd.md) | Full product requirements and user stories |
| [Technical Approach](docs/features/original-organize-me/technical-approach.md) | Stack selection, infrastructure, CI/CD, cost summary, and prerequisites checklist |
| [Changelog](docs/changelog.md) | Release history — one line per merged issue, linking to full detail |

---

## Example Data

The `examples/` folder contains reference files used for development and testing:

- `examples/example.whatsapp.txt` — sample WhatsApp export (canonical input format)
- `examples/example.lmmoutput.txt` — sample Gemini LLM output (22 extracted events, JSON)

---

## Status

**Platform Restructure complete through R13** — `organize-me` is now the Host-only app: auth,
profile, settings-shell, and nav-shell, with all event-extraction functionality (upload,
processing pipeline, storage connections, LLM prompt config, events dashboard, logs) split out
into the independent `event-creator` service and removed from this repo (Slice R13, issue #168).
See [`docs/features/platform-restructure/`](docs/features/platform-restructure/) for the full restructure design
and slice-by-slice WBS, and [Changelog](docs/changelog.md) for the complete history (including the
pre-restructure monolith slices this repo used to carry).
