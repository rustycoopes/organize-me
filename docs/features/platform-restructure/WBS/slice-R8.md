# Slice R8 — Parity 2: Upload + Pipeline + Processing + Logs

> Part of the OrganizeMe Platform Restructure. Structural PRD:
> [`../platform-restructure-prd.md`](../platform-restructure-prd.md) ·
> Technical design: [`../platform-restructure-design.md`](../platform-restructure-design.md)

**Delivers:** Manual upload, the 7-step processing pipeline with live SSE progress, processing
history, and searchable/downloadable logs rebuilt in Event Creator — including standing up the
Celery worker it now owns.

## What to build

Migrate the heaviest feature area — file intake and the extraction pipeline — into Event Creator
with full parity. A user uploads a file, watches the 7 steps progress live, and can review the
history and logs of every run. The Celery worker (dormant in the monolith) becomes an Event
Creator concern with `REDIS_URL` wired.

## Includes
- Upload + pipeline driver (`app/api/v1/upload.py`, `app/services/pipeline/{runner,progress}.py`,
  `app/api/v1/import_pending_files.py`).
- 7-step pipeline: File Received → Extract/unzip → Filter by Date → Call Gemini → Parse → Dedup &
  Save → Notify (`app/services/llm/gemini.py`, `app/core/message_filter.py`, `date_parser.py`).
- Live progress via SSE (`app/api/v1/processing_runs.py` SSE stream, `app/pages/processing.py`,
  HTMX SSE).
- Processing history + logs (`app/pages/logs.py`, `app/services/processing_logs.py`, log list +
  download).
- **Celery worker owned by Event Creator:** enable `[program:worker]` (currently
  `autostart=false`), wire `REDIS_URL` (Upstash) into the Event Creator Cloud Run service.
- Notification dispatch on run completion (email/SMS) via the R7 settings — success/failure/zero-event.

## Relevant schema — `event_creator`
- `processing_runs`, `processing_steps`, `events` (write path).

## Relevant endpoints (moved into Event Creator)
| Method | Path | Purpose |
|---|---|---|
| POST | /api/v1/upload | Upload file for immediate processing |
| GET | /api/v1/processing-runs/{id}/sse | SSE stream of live step updates |
| GET | /api/v1/processing-runs | List processing history |
| GET | /api/v1/processing-runs/{id} | Run detail (steps + status) |
| GET | /api/v1/processing-runs/{id}/logs[/download] | Structured logs / JSON download |

## Design notes
- **LLM failure = fail the run immediately** at the Gemini step (no retry); move file to
  `failed/`, record error in `ProcessingStep` logs, notify by SMS + email with a link to logs.
- **Zero-event run** (all duplicates) is a success: file → `processed/`, "0 new events" notification.
- SSE needs the long Cloud Run request timeout (Event Creator service configured like the Host's
  `--timeout=3600`).
- Worker runs in the same container as the Event Creator web process via supervisord, as the
  monolith intended.

## Blocked by
- R6 (Event Creator scaffold + SSO trust).

## Acceptance criteria
- [ ] Upload → 7-step pipeline runs to completion in Event Creator with live SSE progress at parity.
- [ ] Processing history and searchable/downloadable logs work at parity.
- [ ] The Celery worker runs in the Event Creator service (`REDIS_URL` wired) and processes runs.
- [ ] LLM-failure and zero-event paths behave exactly as today (file moves + notifications).
- [ ] PRD stories covering upload/pipeline/processing/logs pass via the new structure.

## Testing
- Pipeline integration test: Celery `ALWAYS_EAGER`, stub Gemini with
  `examples/example.lmmoutput.txt`; assert events saved.
- Failure-path + zero-event-path tests (file move + notification payloads stubbed).
- One real end-to-end Gemini run on `examples/example.whatsapp.txt` (as today).
- E2E: upload → live SSE progress → history/logs render.
