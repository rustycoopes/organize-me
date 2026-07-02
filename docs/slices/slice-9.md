# Slice 9 — Automated File Watch (Cloud Scheduler)

> Part of the OrganizeMe build plan. Shared context in
> [`../implementation-plan.md`](../implementation-plan.md).

**Delivers:** System automatically detects and processes new files from connected storage
every 15 minutes.

## Includes
- `/internal/trigger-scan` endpoint (authenticated with a shared secret header)
- Celery scan task: for each user with active storage config, list new files and enqueue
  `FileProcessTask` per file
- GCP Cloud Scheduler job configuration (POST every 15 min)
- File lifecycle: move to `processed/` on success, `failed/` on failure

## Relevant endpoints (under `/api/v1/`)
| Method | Path | Purpose |
|---|---|---|
| POST | /internal/trigger-scan | Cloud Scheduler webhook (internal, shared-secret header) |

## Depends on
- Slice 2/8 `StorageProvider.list_new_files()` / `move_file()`.
- Slice 4's `FileProcessTask` pipeline (reused per detected file).

## Design notes
- Cloud Scheduler fires every 15 minutes (not 5).

## Testing
- Assert the scan task enqueues one pipeline task per new file across users with active configs,
  using `FakeStorageProvider`.
