# OrganizeMe — Technical Approach

**Version:** 1.0  
**Date:** 2026-06-30  
**Status:** Draft — awaiting sign-off before implementation begins

---

## Recommended Stack (Headline)

| Layer | Choice |
|---|---|
| Backend | Python 3.12 + FastAPI |
| Validation / typing | Pydantic v2 + mypy strict |
| Frontend rendering | Jinja2 templates + HTMX + Tailwind CSS + Alpine.js |
| Database | PostgreSQL via Supabase (free hosted) |
| ORM / migrations | SQLAlchemy 2.0 async + Alembic |
| Background jobs | Celery + Upstash Redis |
| File-watch scheduler | GCP Cloud Scheduler → Cloud Run Job |
| Real-time pipeline UI | SSE via sse-starlette + HTMX SSE extension |
| Auth | FastAPI-Users (email/password + Google OAuth) |
| LLM | google-genai SDK (Gemini) |
| Storage SDKs | dropbox, google-api-python-client, boto3 |
| Email notifications | Resend (3 000 emails/month free) |
| SMS notifications | Twilio (~$0.008/message — paid) |
| Testing | pytest + httpx + pytest-asyncio + factory_boy |
| Containerisation | Docker + Docker Compose (dev) / Dockerfile (prod) |
| CI/CD | GitHub Actions |
| Deployment | GCP Cloud Run (app + workers) |
| Secrets | GCP Secret Manager |
| Container registry | GCP Artifact Registry |
| Logging | structlog → GCP Cloud Logging (automatic from Cloud Run) |

---

## Section-by-Section Evaluation

### 1. Backend Framework

**Choice: FastAPI**

| Option | TDD Story | Typing | Async | Verdict |
|---|---|---|---|---|
| **FastAPI** | httpx TestClient; test REST endpoints directly | Pydantic v2 enforced at runtime + mypy at build | Native asyncio | ✅ Best fit |
| Django + DRF | Django test client; fixtures | Partial via django-stubs | Bolted-on | ❌ Heavier; admin out of scope |
| Flask | Similar to FastAPI | Manual | Extension-based | ❌ Less ergonomic for async + typing |

FastAPI auto-generates OpenAPI docs that also serve as a live spec to test against.

---

### 2. Frontend Rendering

**Choice: Jinja2 + HTMX + Tailwind CSS + Alpine.js**

| Option | Logic location | Build pipeline | Real-time | Testability |
|---|---|---|---|---|
| **HTMX + Jinja2** | 100% backend | None | SSE (HTMX native) | Test HTML via httpx |
| React SPA | Shared / fragmented | npm + bundler | WebSockets or polling | Separate test suites |
| Next.js SSR | Shared | Complex | Streaming | Mixed concerns |

HTMX requests return HTML fragments; FastAPI returns Jinja2-rendered partials. All business
logic stays in Python and is tested via REST endpoints.

Alpine.js (~15 kB, no build step) handles micro-interactions: dark mode toggle, tab switching,
form conditionals. Tailwind CSS provides the Laravel-inspired aesthetic.

---

### 3. Database

**Choice: PostgreSQL via Supabase**

| Option | Monthly cost | Notes |
|---|---|---|
| **Supabase** | Free (500 MB) | Full PostgreSQL; wire-compatible with Cloud SQL if scale requires |
| Cloud SQL (GCP) | ~$7/month minimum | Tighter GCP integration; paid from day one |
| SQLite | Free | Not suitable for multi-instance Cloud Run |

SQLAlchemy 2.0 async ORM + Alembic migrations. Both run cross-platform (Windows dev / Linux
prod via Docker), so there is no dev/prod divergence risk.

---

### 4. Background Tasks & File Watching

The app has two async concerns:

- **Polling** — check Dropbox / Google Drive / S3 every N minutes for new files
- **Processing pipeline** — when a file is found, run the 7-step pipeline

**Architecture:**

```
Cloud Scheduler (every 5 min)
  → POST /internal/trigger-scan (Cloud Run)
    → Celery task: scan each user's storage, enqueue FileProcess tasks
      → Celery worker: 7-step pipeline → SSE updates → DB write → notify
```

| Option | Complexity | Free? | Reliability |
|---|---|---|---|
| **Celery + Upstash Redis** | Medium | Upstash free (10k cmds/day) | Production-grade ✅ |
| FastAPI BackgroundTasks + APScheduler | Low | Yes | Fails on multi-instance Cloud Run ❌ |
| Cloud Tasks (GCP) | Low | 1 M tasks/month free | Vendor lock-in; harder to test locally |
| ARQ (async job queue) | Low–medium | Yes (Redis needed) | Less ecosystem than Celery |

Celery workers run in `CELERY_TASK_ALWAYS_EAGER = True` mode in the test suite so tests
remain fast and deterministic.

---

### 5. Real-time Pipeline Progress

**Choice: Server-Sent Events (SSE)**

| Option | HTMX integration | Complexity | Notes |
|---|---|---|---|
| **SSE** | Native `hx-ext="sse"` | Low | One-way push; auto-reconnect ✅ |
| WebSockets | Possible with htmx-ws | Higher | Stateful connections; not needed here |
| Polling | Simple HTMX polling | Very low | Works but less elegant |

`sse-starlette` provides the FastAPI SSE endpoint. HTMX subscribes and swaps DOM elements
as each step completes. On reconnect, the client fetches current state from a REST endpoint
so no progress is lost.

---

### 6. Authentication

**Choice: FastAPI-Users**

Provides out of the box:
- Email + password with bcrypt hashing
- Google OAuth via `httpx-oauth`
- JWT tokens in HTTPOnly cookies (CSRF-safe)
- Password reset flow with email tokens
- Extensible user model for OrganizeMe-specific fields (phone number, preferences, onboarding state)

---

### 7. Notifications

**Email — Choice: Resend**

| Option | Free tier | Notes |
|---|---|---|
| **Resend** | 3 000 emails/month | Official Python SDK ✅ |
| SendGrid | 100 emails/day | More limited |
| AWS SES | Free only from inside AWS | Not applicable here |
| Gmail SMTP | Rate-capped | Not suitable for production |

**SMS — Choice: Twilio**  
⚠️ **PAID SERVICE** — ~$0.008/message (US numbers). No practical free-tier SMS provider exists
for production. Twilio offers ~$15 trial credit. For personal-scale usage the monthly cost will
be pennies, but it is not zero.

---

### 8. LLM Integration

**Choice: google-genai SDK (Gemini)**

- Gemini 2.0 Flash free tier: 15 RPM / 1 500 requests/day — sufficient for personal use
- Pipeline step "Call Gemini LLM" sends one structured-output request per file
  (`response_mime_type="application/json"`)
- The LLM call is isolated in a service class and stubbed in tests (returning the canonical
  `examples/example.lmmoutput.txt` fixture); one integration test calls the real API to
  validate the prompt

---

### 9. Storage Provider Integrations

| Provider | SDK | Auth model | Watch mechanism |
|---|---|---|---|
| Dropbox | `dropbox` | OAuth 2.0 | List folder API (polling) |
| Google Drive | `google-api-python-client` | OAuth 2.0 | Files.list API (polling) |
| AWS S3 | `boto3` | Access key + secret | ListObjectsV2 API (polling) |

A `StorageProvider` abstract base class (`list_new_files()`, `move_file()`, `download_file()`)
sits behind the polling logic. Each provider implements the interface; tests inject a fake.

---

### 10. Deployment Architecture

```
GitHub
  └─ GitHub Actions
       ├─ On PR: pytest + mypy → build → push image → deploy to Cloud Run (QA)
       └─ On merge to main: pytest + mypy → build → push image → deploy to Cloud Run (Prod)

GCP Project
  ├─ Cloud Run: organize-me-qa      (app + Celery worker)
  ├─ Cloud Run: organize-me-prod    (app + Celery worker)
  ├─ Cloud Scheduler                (triggers /internal/trigger-scan every 5 min)
  ├─ Artifact Registry              (Docker images)
  ├─ Secret Manager                 (DB URL, Gemini key, Twilio, Resend, etc.)
  └─ Cloud Logging                  (automatic from Cloud Run stdout/stderr)

External (free / near-free)
  ├─ Supabase            (PostgreSQL: organize-me-qa + organize-me-prod databases)
  └─ Upstash Redis       (Celery broker)
```

---

### 11. CI/CD Pipeline

Two GitHub Actions workflows:

**`ci.yml`** — runs on every PR:
1. `pytest` (Supabase QA DB URL injected as secret)
2. `mypy --strict`
3. Docker build + push to Artifact Registry
4. Deploy to Cloud Run (QA)

**`deploy.yml`** — runs on merge to `main`:
1. Same test suite
2. Deploy to Cloud Run (Prod)

All secrets (GCP service account, Supabase URLs, Gemini key, Twilio, Resend) are stored
as GitHub Actions secrets.

---

### 12. Logging & Observability

- **structlog** outputs structured JSON; Cloud Run picks it up automatically into Cloud Logging
- Every pipeline run creates a `ProcessingRun` DB record
- Each of the 7 steps writes a `ProcessingStep` row (status, log lines, timestamps)
- The in-app log viewer queries these rows; logs are downloadable as JSON from a REST endpoint
- GCP Cloud Logging provides searchable log storage and alerting at no extra cost at personal scale

---

## Cost Summary

| Service | Estimated monthly cost | Notes |
|---|---|---|
| GCP Cloud Run | **$0** | Scale-to-zero; free tier covers personal scale |
| GCP Cloud Scheduler | **$0** | 3 jobs/account always free |
| GCP Artifact Registry | **$0** | 0.5 GB free |
| GCP Secret Manager | **~$0.06** | Per secret per month |
| GCP Cloud Logging | **$0** | At personal scale |
| Supabase (PostgreSQL) | **$0** | 500 MB, unlimited API |
| Upstash Redis | **$0** | 10 000 commands/day free |
| Resend (email) | **$0** | 3 000 emails/month free |
| Gemini API | **$0** | Free tier (1 500 req/day) |
| **Twilio (SMS)** | **~$0–2/month** | ~$0.008/message; no free alternative |
| GitHub Actions | **$0** | 2 000 min/month (private repo) |
| **Total** | **< $2/month** | Driven almost entirely by SMS volume |

---

## Prerequisites Checklist

The following must be provisioned before development begins or CI/CD can run end-to-end.

### GitHub
- [ ] Repository created with branch protection on `main` (require PR + passing CI)
- [ ] GitHub Projects board created for issue tracking
- [ ] GitHub Actions secrets configured (added progressively as services are provisioned)

### GCP
- [ ] GCP project created (e.g. `organize-me`)
- [ ] Billing account linked (required even for free-tier resources)
- [ ] APIs enabled: Cloud Run, Cloud Scheduler, Artifact Registry, Secret Manager, Cloud Build, Cloud Logging
- [ ] Service account created for GitHub Actions with roles: `Artifact Registry Writer`, `Cloud Run Developer`, `Secret Manager Secret Accessor`
- [ ] Service account JSON key downloaded and stored as GitHub Actions secret `GCP_SA_KEY`
- [ ] Two Cloud Run services provisioned: `organize-me-qa`, `organize-me-prod`
- [ ] Cloud Scheduler job created (POST to `/internal/trigger-scan` every 5 minutes)
- [ ] Artifact Registry repository created (e.g. `organize-me`)

### Supabase
- [ ] Account created at supabase.com
- [ ] Two projects created: `organize-me-qa`, `organize-me-prod`
- [ ] Connection strings (PostgreSQL) noted for GitHub Actions secrets and local `.env`

### Upstash Redis
- [ ] Account created at upstash.com
- [ ] Redis database created; connection URL noted

### Gemini
- [ ] API key generated in Google AI Studio (aistudio.google.com)
- [ ] Confirm free tier quota (15 RPM / 1 500 req/day) is sufficient for expected volume

### Resend
- [ ] Account created at resend.com
- [ ] Domain verified for sending (or use sandbox for initial development)
- [ ] API key generated

### Twilio
- [ ] Account created at twilio.com (trial credit ~$15 available)
- [ ] Phone number purchased or trial number used
- [ ] Account SID + Auth Token noted

### Local development
- [ ] Python 3.12 installed
- [ ] Docker Desktop installed (for local Postgres + Redis via Docker Compose)
- [ ] `pyproject.toml` scaffold created (FastAPI, Pydantic, SQLAlchemy, Celery, etc.)
- [ ] `docker-compose.yml` with PostgreSQL + Redis services
- [ ] `.env.local` file created with all keys (confirmed in `.gitignore`)
- [ ] `mypy.ini` with `strict = true`
- [ ] `pytest.ini` / `pyproject.toml` test config pointing at test database

---

## Reference Fixtures

The following example files in `examples/` are canonical for testing and LLM prompt tuning:

- `examples/example.whatsapp.txt` — 630-line real WhatsApp conversation (input format)
- `examples/example.lmmoutput.txt` — 22 extracted events in JSON (expected pipeline output)

The end-to-end integration test uploads `example.whatsapp.txt`, runs the full pipeline with the
real Gemini API, and asserts that the resulting dashboard rows match `example.lmmoutput.txt`.
All other pipeline tests stub the Gemini call and return the example output directly.

---

## Key Implementation Notes

- **Dev/prod parity**: Docker Compose runs PostgreSQL + Redis locally, matching Cloud Run exactly. No SQLite shortcuts.
- **Strict typing throughout**: `mypy --strict` in CI; Pydantic v2 validates all API I/O and LLM responses at runtime.
- **Storage provider abstraction**: `StorageProvider` ABC with injectable fakes — storage tests never hit live credentials.
- **Celery eager mode in tests**: `CELERY_TASK_ALWAYS_EAGER = True` makes pipeline tasks run synchronously in the test process.
- **SSE reconnect safety**: If the browser disconnects mid-pipeline, it re-fetches step state from a REST endpoint on reconnect so no status is lost.
- **One Gemini prompt per user**: Stored in DB; editable via the Prompt page. No multi-prompt management.
- **Google Calendar / Tasks**: Pre-filled URL approach — no OAuth write access needed.
