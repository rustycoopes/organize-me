# OrganizeMe

Turn your WhatsApp and SMS conversation history into structured calendar events and tasks — automatically.

---

## What is it?

OrganizeMe is a web application that watches a connected cloud storage folder for conversation export files. When a new file arrives, it uses the Gemini LLM to extract agreed events, appointments, and actions from the conversation, stores them in a structured dashboard, and notifies you by SMS and email. You can also upload files manually at any time.

Every extracted event can be sent to Google Calendar or Google Tasks in one click.

---

## Who is it for?

Anyone who coordinates logistics, agreements, or commitments over chat — co-parents, caregivers, small business owners, project teams. If you've ever had to re-read a conversation to work out what was agreed and when, OrganizeMe is for you.

---

## How it works

1. Export your WhatsApp or SMS conversation as a `.txt`, `.zip`, or `.csv` file.
2. Drop it into your connected cloud storage watch folder (Dropbox, Google Drive, or S3).
3. OrganizeMe detects the file, runs it through a 7-step processing pipeline, and extracts structured events.
4. You receive an SMS and email summary with a link to the dashboard.
5. Review the events table, add items to Google Calendar or Google Tasks, and delete anything irrelevant.

---

## Features

### Events Dashboard
- Table of all extracted events: type, description, resolved date, raw date text, agreed-by (initials chips)
- One-click "Add to Google Calendar" and "Add to Google Task" buttons per row (opens pre-filled in a new tab)
- Filter by event type, date range, and free-text search
- Sort by date
- Delete individual events
- Duplicate events (same description + date) are automatically skipped on import

### Automated Storage Watching
- Connects to **Dropbox**, **Google Drive**, or **AWS S3** (one provider at a time)
- Watches a specific folder you configure
- Successfully processed files move to a `processed/` subfolder
- Failed files move to a `failed/` subfolder

### Manual Upload
- Upload a `.txt`, `.zip`, or `.csv` file directly from the app
- Goes through the identical processing pipeline as auto-detected files

### Processing Pipeline
- 7 visible steps: File Received → Extract → Filter by Date → Call Gemini LLM → Parse Response → Deduplicate & Save → Notify
- Real-time step progress with success/failure state per step — a live progress page (`/processing`)
  streams each step's status as it changes via Server-Sent Events (`GET /api/v1/processing-runs/{id}/sse`, HTMX SSE), no manual refresh
- Full processing history with drillable per-run detail and logs

### Logs
- Structured, searchable logs per processing run
- Downloadable for offline review or sharing

### Notifications
- **Success:** SMS (event count + dashboard link) and rich HTML email (event table + link)
- **Failure:** SMS and email with failure details and a direct link to the log page
- SMS and email notifications are independently toggleable

### LLM Prompt Management
- View and edit the Gemini prompt used for event extraction
- One active prompt per user — always editable, never deleted

### Settings
- **Storage tab:** Connect and configure your cloud storage provider
- **Notifications tab:** Toggle SMS and email on/off independently; manage your phone number
- **Preferences tab:** Set the message look-back window (default 7 days, max 90 days) and UI theme

### Authentication
- Sign in with Google or email + password
- Open self-registration — no invitation required
- Password reset by email
- Account self-deletion (removes all data)

### UI
- Laravel-inspired aesthetic
- Dark mode / light mode (persists across sessions)
- Left sidebar navigation: Dashboard · Upload · Processing · Logs · Prompt · Settings · Profile
- Getting Started checklist for new users, dismissed automatically once complete

---

## Development

**Stack:** Python 3.12 + FastAPI, managed with [uv](https://docs.astral.sh/uv/). See [Technical Approach](docs/technical-approach.md) for the full stack.

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

### Test & type-check

```bash
uv run pytest
uv run mypy app tests
```

### End-to-end tests (Playwright)

The `e2e/` folder holds a Playwright/TypeScript suite that drives the **real deployed QA app**
end-to-end (landing, register/login/logout, forgot/reset password, profile edit, dark-mode
persistence, account deletion, sidebar nav). It's separate from the Python `pytest` suite and
runs in CI as the `e2e-qa` job after QA deploys.

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

The container runs the FastAPI app and the Celery worker as separate processes under `supervisord`.

### CI/CD

GitHub Actions (`.github/workflows/ci.yml`, `deploy.yml`) run `pytest` + `mypy --strict`, then build and push the Docker image to Artifact Registry and deploy to Cloud Run — QA on every PR, prod on merge to `main`. On PRs, a final `e2e-qa` job runs the Playwright suite against the freshly-deployed QA instance and uploads an HTML report artifact on failure.

---

## Security

- All personal data and conversation content is encrypted at rest
- Cloud storage credentials (OAuth tokens, API keys) are stored securely and never exposed
- `.env` and `.env.local` files are excluded from source control

---

## Project Documentation

| Document | Description |
|----------|-------------|
| [PRD](docs/prd.md) | Full product requirements and user stories |
| [Technical Approach](docs/technical-approach.md) | Stack selection, infrastructure, CI/CD, cost summary, and prerequisites checklist |
| [Changelog](docs/changelog.md) | Release history |
| [Project Status](docs/project-status.md) | Current phase and next steps |

---

## Example Data

The `examples/` folder contains reference files used for development and testing:

- `examples/example.whatsapp.txt` — sample WhatsApp export (canonical input format)
- `examples/example.lmmoutput.txt` — sample Gemini LLM output (22 extracted events, JSON)

---

## Status

**In development** — Slice 1 (project scaffold, auth, CI/CD) and Slice 2 (Google Drive storage) complete: the storage foundation, the Settings > Storage tab (`GET`/`PUT /api/v1/storage-config`), and the Google Drive OAuth connect/disconnect flow (tokens encrypted at rest) are all in. Slice 3 (LLM Prompt page) complete: an `llm_prompts` table with a factory-default extraction prompt seeded into every new account, plus a Prompt page (`/prompt`) and `GET`/`PUT /api/v1/llm-prompt` + `POST /api/v1/llm-prompt/reset` endpoints letting a user view, edit, and reset that prompt. Slice 4 (upload + processing pipeline) complete: the `processing_runs`/`processing_steps`/`events` tables (with duplicate-detection), a `resolved_date` → earliest-date parser, an injectable Gemini call wrapper, the Upload page + `POST /api/v1/upload` + the 7-step pipeline (in-process asyncio, not Celery), and a live SSE progress page (`/processing` + `GET /api/v1/processing-runs/{id}/sse`, HTMX SSE, no manual refresh) are all in. Slice 5 (events dashboard) in progress: `GET /api/v1/events` (paginated, newest-date-first) + `DELETE /api/v1/events/{id}`, Google Calendar/Tasks link builders (`app/core/calendar_url.py`), a real Dashboard page (`/dashboard`) with a confirm-gated delete, and the Getting Started onboarding checklist (#56 — a 3-step checklist shown above the events table until all three onboarding flags are done) are now in place; filters/sort/search (#55) is next. See [Project Status](docs/project-status.md). **Human setup** to run things live: register the Drive OAuth callback redirect URI + `drive` scope on the Google client (Slice 2, `ENCRYPTION_KEY` secret now set — issue #78); set the `GEMINI_API_KEY` secret, enable Cloud Run "CPU always allocated", and verify `GoogleDriveStorageProvider` against a real connected Drive account (Slice 4.1, tracked in issue #72); and manually confirm whether Google's Tasks frontend honours the dashboard's pre-fill link (Slice 5.1, noted in the PR for #54).
