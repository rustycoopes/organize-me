# Slice 4 — Manual Upload + Processing Pipeline + SSE Progress

> Part of the OrganizeMe build plan. Shared context in
> [`../implementation-plan.md`](../implementation-plan.md).

**Delivers:** User uploads a file, sees live pipeline progress, and extracted events appear
in the dashboard.

## Includes
- Upload page (drag-and-drop + file picker, `.txt`/`.zip`/`.csv`)
- `processing_runs` + `processing_steps` + `events` table migrations
- Celery task: 7-step pipeline (below)
- SSE endpoint `/api/v1/processing-runs/{id}/sse` (sse-starlette)
- Pipeline progress page: 7 step indicators with live SSE updates (HTMX)
- `onboarding_first_upload_done` flag set on first upload

## The 7 pipeline steps
1. **File Received** — record run, record step
2. **Extract** — unzip if `.zip`
3. **Filter by Date** — message window from settings, default 7 days
4. **Call Gemini LLM** — google-genai SDK; fail immediately on error
5. **Parse LLM Response** — Pydantic validation
6. **Deduplicate & Save** — UNIQUE constraint check; parse `resolved_date_earliest`
7. **Notify** — SMS + email; send even if 0 new events

**Failure handling:** fail the run immediately at the Gemini step. Move file to `failed/`.
Record error in ProcessingStep logs. Notify user by SMS + email with link to logs.
**Zero-event run** (all duplicates): treated as success, file → `processed/`, "0 new events" notice.

## Relevant schema
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

## Relevant endpoints (under `/api/v1/`)
| Method | Path | Purpose |
|---|---|---|
| POST | /upload | Upload file for immediate processing |
| GET | /processing-runs/{id}/sse | SSE stream for live step updates |

## Key utilities introduced (build once, reused later)
- `app/services/llm/gemini.py` — Gemini call wrapper (injectable fake in tests)
- `app/core/date_parser.py` — `parse_earliest_date(resolved_date: str) -> date | None`

## Multi-date `resolved_date` handling
For values like "Sunday 28 June, Monday 29 June": parse and store `resolved_date_earliest`
(date column) alongside the raw string — used for sorting and the calendar URL. Full raw text
goes into the calendar description field.

## Testing
- Pipeline integration test: Celery `ALWAYS_EAGER`; stub Gemini (return
  `examples/example.lmmoutput.txt`); assert events appear in DB.
- One end-to-end test with a real Gemini call: upload `examples/example.whatsapp.txt`,
  run full pipeline, assert dashboard rows match `examples/example.lmmoutput.txt`.
- Unit test `date_parser` and duplicate-detection logic.

## Reference fixtures
- `examples/example.whatsapp.txt` — 630-line WhatsApp conversation (pipeline input)
- `examples/example.lmmoutput.txt` — 22 extracted events in JSON (expected output)
