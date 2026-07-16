# Slice 6 — Processing History + Logs

> Part of the OrganizeMe build plan. Shared context in
> [`../implementation-plan.md`](../implementation-plan.md).

**Delivers:** User can review all past runs, drill into step detail, search logs, and download them.

## Includes
- Processing history list page (run date, filename, status, event count)
- Run detail page (per-step status indicators + log lines)
- Log viewer: searchable (HTMX filter), structured display
- Download logs endpoint (JSON response)

## Relevant schema (read-only; created in Slice 4)
- `processing_runs` — id, user_id, filename, status, events_extracted_count,
  started_at, completed_at, created_at
- `processing_steps` — id, run_id, step_number, step_name, status, log_lines (JSONB),
  started_at, completed_at

## Relevant endpoints (under `/api/v1/`)
| Method | Path | Purpose |
|---|---|---|
| GET | /processing-runs | List processing history |
| GET | /processing-runs/{id} | Run detail (steps + status) |
| GET | /processing-runs/{id}/logs | Structured log lines |
| GET | /processing-runs/{id}/logs/download | Download logs as JSON |

## Design notes
- Processing history is kept forever — no auto-deletion.

## Testing
- Assert log lines render and the download endpoint returns valid JSON.
