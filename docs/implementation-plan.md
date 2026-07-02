# OrganizeMe — Implementation Design Spec

**Date:** 2026-06-30  
**Source:** PRD (docs/prd.md) + Technical Approach (docs/technical-approach.md) + design Q&A session

---

## Context

This document captures all design decisions made during a structured Q&A session on top of the PRD and tech design doc. Its purpose is to provide enough detail to generate a concrete, ordered set of implementation tasks. The build strategy is **vertical slices** — each slice delivers a complete end-to-end user-facing feature (DB migration + API endpoints + Jinja2/HTMX frontend + tests) in one go.

---

## Confirmed Stack (no changes from tech-approach.md)

| Layer | Decision |
|---|---|
| Backend | Python 3.12 + FastAPI |
| Frontend | Jinja2 + HTMX + Tailwind CSS + **DaisyUI** + Alpine.js |
| Database | PostgreSQL via Supabase (hosted — no local Docker for DB) |
| ORM / migrations | SQLAlchemy 2.0 async + Alembic |
| Background jobs | Celery + **Upstash Redis** (same instance for local dev and prod — no local Docker for Redis) |
| Worker deployment | Same Docker container as FastAPI app, separate process via **supervisord** |
| File-watch scheduler | GCP Cloud Scheduler → POST /internal/trigger-scan every **15 minutes** |
| Real-time pipeline UI | SSE via sse-starlette + HTMX SSE extension |
| Auth | FastAPI-Users (email/password + Google OAuth), JWT in HTTPOnly cookies, **7-day expiry** |
| LLM | google-genai SDK (Gemini), fail immediately on error (no retry) |
| Storage SDKs | **Google Drive first** (reference impl), then Dropbox, then AWS S3 |
| Email | Resend — **styled HTML with OrganizeMe branding** |
| SMS | Twilio |
| Testing | pytest + httpx + pytest-asyncio + factory_boy |
| Containerisation | Dockerfile (app + supervisord for Celery worker); no docker-compose for external services |
| CI/CD | GitHub Actions: PR → QA Cloud Run deploy; merge to main → Prod deploy |

---

## Design Decisions (Q&A Outputs)

### Infrastructure
- **Local dev**: No Docker Compose for external services. Connect directly to Supabase QA database and Upstash Redis via `.env.local`.
- **Celery worker**: Runs inside the same Cloud Run container as the FastAPI app. Managed by `supervisord` (`[program:app]` + `[program:worker]`).
- **Polling frequency**: Cloud Scheduler fires every 15 minutes (not 5).
- **CI/CD**: Two workflows — `ci.yml` (PR: test + mypy + build + deploy to QA), `deploy.yml` (main merge: test + deploy to prod).

### API
- All REST endpoints under `/api/v1/` prefix.
- HTML pages served via FastAPI + Jinja2 at root-level paths (`/`, `/dashboard`, `/upload`, etc.).

### Frontend / UX
- **Component library**: DaisyUI on top of Tailwind CSS.
- **Mobile**: Desktop-first. No responsive sidebar required.
- **Sidebar order** (top → bottom): Dashboard → Upload → Processing → Logs → Prompt → Settings → Profile.
- **Settings tabs**: Storage | Notifications | Preferences.

### Events Dashboard
- **Pagination**: 50 events per page.
- **Default sort**: Newest `resolved_date` first.
- **Multi-date `resolved_date`** (e.g. "Sunday 28 June, Monday 29 June"):
  - Parse and store `resolved_date_earliest` (date column) alongside the raw string — used for sorting and calendar URL.
  - Calendar link uses the earliest date; full raw text goes into the description field.
- **Google Calendar URL pre-fill**: Title (event description) + date (resolved_date_earliest) + description (includes raw_date_text and agreed_by list).
- **Google Tasks URL pre-fill**: Title + due date.

### LLM / Prompt
- A **factory default prompt** is seeded into the DB on every new user account creation (based on the example.lmmoutput.txt format).
- The Prompt page has a **Reset to Default** button that restores the factory prompt.
- **LLM failure**: Fail the pipeline run immediately at the Gemini step. Move file to `failed/`. Record error in ProcessingStep logs. Notify user by SMS and email with link to logs.

### Pipeline
- **7 steps**: File Received → Extract (unzip if needed) → Filter by Date → Call Gemini LLM → Parse LLM Response → Deduplicate & Save → Notify.
- **Zero-event run** (all events are duplicates): Treated as success. File moves to `processed/`. Notification sent ("0 new events found").
- **Processing history**: Kept forever — no auto-deletion.

### Notifications
- **Success SMS**: Event count + dashboard link.
- **Success email**: Styled branded HTML with event summary table + dashboard link.
- **Failure SMS**: Failure summary + link to log page.
- **Failure email**: Failure details + link to log page.
- **Zero-event**: Sends success notification with count = 0.
- Both channels independently toggled in Settings > Notifications.

### Onboarding
- **3-step checklist** shown on dashboard for new users:
  1. Connect Storage
  2. Set Notification Preferences
  3. Upload First File
- Checklist hidden once all 3 are marked complete (tracked as boolean fields on the user record).

### Account
- **Deletion**: Immediate and permanent — all user data deleted, user logged out. No soft delete or grace period.

---

## Database Schema

### `users` (FastAPI-Users base + extensions)
```
id                            UUID PK
email                         TEXT UNIQUE NOT NULL
hashed_password               TEXT
is_active                     BOOL
is_verified                   BOOL
is_superuser                  BOOL
name                          TEXT
phone_number                  TEXT NULLABLE
dark_mode                     BOOL DEFAULT FALSE
notification_sms              BOOL DEFAULT TRUE
notification_email            BOOL DEFAULT TRUE
onboarding_storage_done       BOOL DEFAULT FALSE
onboarding_notifications_done BOOL DEFAULT FALSE
onboarding_first_upload_done  BOOL DEFAULT FALSE
created_at                    TIMESTAMPTZ
updated_at                    TIMESTAMPTZ
```

### `storage_configs`
```
id                  UUID PK
user_id             UUID FK → users (UNIQUE — one active config per user)
provider            ENUM(google_drive, dropbox, s3)
folder_path         TEXT
oauth_access_token  TEXT NULLABLE (encrypted at rest)
oauth_refresh_token TEXT NULLABLE (encrypted at rest)
s3_access_key       TEXT NULLABLE (encrypted at rest)
s3_secret_key       TEXT NULLABLE (encrypted at rest)
s3_bucket_name      TEXT NULLABLE
s3_region           TEXT NULLABLE
created_at          TIMESTAMPTZ
updated_at          TIMESTAMPTZ
```

### `llm_prompts`
```
id          UUID PK
user_id     UUID FK → users (UNIQUE — one prompt per user)
prompt_text TEXT NOT NULL
created_at  TIMESTAMPTZ
updated_at  TIMESTAMPTZ
```

### `processing_runs`
```
id                      UUID PK
user_id                 UUID FK → users
filename                TEXT
status                  ENUM(pending, in_progress, success, failed)
events_extracted_count  INT DEFAULT 0
started_at              TIMESTAMPTZ NULLABLE
completed_at            TIMESTAMPTZ NULLABLE
created_at              TIMESTAMPTZ
```

### `processing_steps`
```
id           UUID PK
run_id       UUID FK → processing_runs
step_number  INT (1–7)
step_name    TEXT
status       ENUM(pending, in_progress, success, failed, skipped)
log_lines    JSONB (array of strings)
started_at   TIMESTAMPTZ NULLABLE
completed_at TIMESTAMPTZ NULLABLE
```

### `events`
```
id                      UUID PK
user_id                 UUID FK → users
run_id                  UUID FK → processing_runs
type                    TEXT (dynamic, LLM-provided)
description             TEXT
resolved_date           TEXT (human-readable, may be multi-date)
resolved_date_earliest  DATE NULLABLE (parsed from resolved_date for sort/calendar)
raw_date_text           TEXT
agreed_by               JSONB (array of strings)
created_at              TIMESTAMPTZ
UNIQUE(user_id, description, resolved_date)  -- duplicate detection
```

---

## API Endpoint Map (Summary)

All under `/api/v1/`:

| Method | Path | Purpose |
|---|---|---|
| POST | /auth/register | Email/password registration |
| POST | /auth/login | Login, set JWT cookie |
| POST | /auth/logout | Clear cookie |
| GET/POST | /auth/google | Google OAuth flow |
| POST | /auth/forgot-password | Send reset email |
| POST | /auth/reset-password | Apply new password |
| GET/PATCH | /users/me | Get/update profile |
| DELETE | /users/me | Delete account |
| GET/PUT | /storage-config | Get/set storage config |
| POST | /storage-config/google-drive/auth | Start Google Drive OAuth |
| GET | /storage-config/google-drive/callback | OAuth callback |
| GET/PUT | /llm-prompt | Get/update user's prompt |
| POST | /llm-prompt/reset | Reset to factory default |
| POST | /upload | Upload file for immediate processing |
| GET | /processing-runs | List processing history |
| GET | /processing-runs/{id} | Run detail (steps + status) |
| GET | /processing-runs/{id}/logs | Structured log lines |
| GET | /processing-runs/{id}/logs/download | Download logs as JSON |
| GET | /processing-runs/{id}/sse | SSE stream for live step updates |
| GET | /events | List events (paginated, filtered, sorted) |
| DELETE | /events/{id} | Delete single event |
| POST | /internal/trigger-scan | Cloud Scheduler webhook (internal) |

---

## Vertical Implementation Slices

### Slice 1 — Project Scaffold + Auth + CI/CD
**Delivers:** Runnable app deployed to Cloud Run. Users can register, log in (email or Google), reset password, view/edit profile, toggle dark mode, delete account.

**Includes:**
- `pyproject.toml`, `Dockerfile`, `supervisord.conf`
- `.env.local` structure + `.gitignore`
- FastAPI app skeleton (`app/main.py`, routers, lifespan)
- Supabase connection + SQLAlchemy async engine + Alembic init migration
- FastAPI-Users setup: User model, auth backends (email/password + Google OAuth)
- `users` table migration
- Landing page (hero + features + CTA sections)
- Login / register / forgot-password / reset-password pages (DaisyUI forms)
- Profile page (name, email, phone, dark/light mode toggle)
- Sidebar shell (all nav items present but links to placeholder pages)
- GitHub Actions `ci.yml` + `deploy.yml`
- GCP Cloud Run services (QA + prod), Artifact Registry, Secret Manager secrets
- Playwright E2E suite validating the full slice against the deployed QA instance (`e2e-qa` CI job)

---

### Slice 2 — Settings: Google Drive Storage
**Delivers:** User can connect Google Drive, set a folder path, and disconnect.

**Includes:**
- `storage_configs` table migration
- `StorageProvider` abstract base class (`list_new_files()`, `move_file()`, `download_file()`)
- Google Drive implementation of `StorageProvider`
- Google Drive OAuth flow (auth redirect + callback + token storage encrypted)
- Settings page > Storage tab (shows Drive fields; Dropbox/S3 stubs hidden)
- Form shows/hides fields based on selected provider (Alpine.js)
- `onboarding_storage_done` flag set on first successful connection

---

### Slice 3 — LLM Prompt Page
**Delivers:** User can view, edit, and reset their extraction prompt.

**Includes:**
- `llm_prompts` table migration
- Factory default prompt constant + seed on user creation
- Prompt page: textarea editor, Save button, Reset to Default button
- `/api/v1/llm-prompt` GET/PUT/reset endpoints

---

### Slice 4 — Manual Upload + Processing Pipeline + SSE Progress
**Delivers:** User uploads a file, sees live pipeline progress, and extracted events appear in the dashboard.

**Includes:**
- Upload page (drag-and-drop + file picker, `.txt`/`.zip`/`.csv`)
- `processing_runs` + `processing_steps` + `events` table migrations
- Celery task: 7-step pipeline
  1. File Received (record run, record step)
  2. Extract (unzip if `.zip`)
  3. Filter by Date (message window from settings, default 7 days)
  4. Call Gemini LLM (google-genai SDK; fail immediately on error)
  5. Parse LLM Response (Pydantic validation)
  6. Deduplicate & Save (UNIQUE constraint check; parse `resolved_date_earliest`)
  7. Notify (SMS + email; send even if 0 new events)
- SSE endpoint `/api/v1/processing-runs/{id}/sse` (sse-starlette)
- Pipeline progress page: 7 step indicators with live SSE updates (HTMX)
- `onboarding_first_upload_done` flag set on first upload

---

### Slice 5 — Events Dashboard
**Delivers:** Full events table with filters, sort, pagination, calendar/tasks links, and delete.

**Includes:**
- Dashboard page: table (type, description, resolved_date, raw_date_text, agreed_by chips, Calendar link, Tasks link, Delete)
- Filters: event type dropdown, date range pickers, free-text search (HTMX-driven)
- Default sort: newest `resolved_date_earliest` first; user-sortable by date
- Pagination: 50 per page
- Google Calendar URL builder (title + resolved_date_earliest + description with raw_date_text and agreed_by)
- Google Tasks URL builder (title + due date)
- Single event delete (with confirmation via DaisyUI modal)
- Getting Started checklist (3 steps, shown until all complete)

---

### Slice 6 — Processing History + Logs
**Delivers:** User can review all past runs, drill into step detail, search logs, and download them.

**Includes:**
- Processing history list page (run date, filename, status, event count)
- Run detail page (per-step status indicators + log lines)
- Log viewer: searchable (HTMX filter), structured display
- Download logs endpoint (JSON response)

---

### Slice 7 — Notifications (Email + SMS)
**Delivers:** Users receive branded email and SMS after processing runs (success and failure).

**Includes:**
- Resend integration (branded HTML email template: OrganizeMe header, event summary table, dashboard link)
- Twilio SMS integration (success: count + link; failure: details + link)
- Settings > Notifications tab: toggle SMS on/off, toggle email on/off
- `onboarding_notifications_done` flag set when user saves notification prefs

---

### Slice 8 — Dropbox + S3 Storage Providers
**Delivers:** Settings > Storage tab fully supports all three providers.

**Includes:**
- Dropbox `StorageProvider` implementation (OAuth 2.0 flow)
- S3 `StorageProvider` implementation (manual credentials: access key, secret, bucket, region)
- Settings > Storage tab updated: provider selector shows all three; form fields conditionally shown per provider (Alpine.js)

---

### Slice 9 — Automated File Watch (Cloud Scheduler)
**Delivers:** System automatically detects and processes new files from connected storage every 15 minutes.

**Includes:**
- `/internal/trigger-scan` endpoint (authenticated with a shared secret header)
- Celery scan task: for each user with active storage config, list new files and enqueue `FileProcessTask` per file
- GCP Cloud Scheduler job configuration (POST every 15 min)
- File lifecycle: move to `processed/` on success, `failed/` on failure

---

## Key Utilities to Build Once and Reuse

- **`app/services/storage/base.py`** — `StorageProvider` ABC
- **`app/services/llm/gemini.py`** — Gemini call wrapper (injectable fake in tests)
- **`app/services/notifications/email.py`** — Resend wrapper
- **`app/services/notifications/sms.py`** — Twilio wrapper
- **`app/core/security.py`** — encryption helpers for credential storage
- **`app/core/date_parser.py`** — `parse_earliest_date(resolved_date: str) -> date | None`
- **`app/core/calendar_url.py`** — Google Calendar + Tasks URL builders

---

## Testing Approach

- **Unit tests**: `date_parser`, `calendar_url`, duplicate detection logic, prompt reset
- **Pipeline integration tests**: Celery in `ALWAYS_EAGER` mode; stub Gemini (return `examples/example.lmmoutput.txt`); assert events appear in DB
- **Auth tests**: register, login, forgot-password flows via httpx TestClient
- **Storage provider tests**: inject `FakeStorageProvider` (implements ABC) — never hit live credentials
- **Notification tests**: stub Resend + Twilio at delivery boundary; assert payloads
- **End-to-end pipeline test** (one real Gemini call): upload `examples/example.whatsapp.txt`, run full pipeline, assert dashboard rows match `examples/example.lmmoutput.txt`
- **Browser tests (Playwright)**: a `e2e/` suite runs against the deployed QA Cloud Run instance (`e2e-qa` CI job, after `deploy-qa`) to validate each slice's overall UX delivery — e.g. Slice 1 covers landing page, register/login/logout, forgot/reset password, dark/light mode toggle persistence, profile edit, account deletion, and sidebar nav. Google OAuth is excluded (unreliable to drive headlessly against Google's real consent screen) and stays covered by backend tests. Later slices add their own Playwright specs to the same suite (e.g. storage config form conditional fields, notification toggles) rather than a separate one-off suite per slice.

---

## Reference Fixtures

- `examples/example.whatsapp.txt` — 630-line WhatsApp conversation (pipeline input)
- `examples/example.lmmoutput.txt` — 22 extracted events in JSON (expected output)

---

## Prerequisites Before Slice 1 Begins

- [ ] GCP project created, billing linked, required APIs enabled
- [ ] Artifact Registry repo + two Cloud Run services (QA + prod) provisioned
- [ ] GitHub Actions secrets configured: `GCP_SA_KEY`, `SUPABASE_QA_URL`, `SUPABASE_PROD_URL`, `UPSTASH_REDIS_URL`, `GEMINI_API_KEY`, `TWILIO_*`, `RESEND_API_KEY`
- [ ] Supabase: two projects (QA + prod), connection strings noted
- [ ] Upstash Redis: one database, connection URL noted
- [ ] Google OAuth app registered (for Drive + auth) — client ID + secret
- [ ] Resend account + domain verified
- [ ] Twilio trial account + phone number
- [ ] Gemini API key from Google AI Studio
