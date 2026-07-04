# Model decisions

Decisions taken by the model during autonomous implementation runs, recorded for later review.

## 2026-07-04 — #54 Slice 5.1 events dashboard

### No official Google Tasks "quick add" URL scheme
Google Calendar has a long-standing, widely used `render?action=TEMPLATE` convention for
pre-filling a new event via a plain link. Google has **never published an equivalent for Tasks** -
there is no documented way to pre-fill a task's title/due-date via URL. `build_google_tasks_url`
(`app/core/calendar_url.py`) implements a best-effort `title`/`due` query string; whether Google's
frontend actually honours it is unverified and needs a manual check against a real account (the
same class of caveat as #52's Google Drive multipart-upload verification). Even if Google ignores
the params, the link still opens Google Tasks - it just won't be pre-filled. Flagged in the PR
rather than filed as a separate `modelsuggested` issue, since it's inherent third-party-behaviour
uncertainty (nothing in the codebase to "fix") rather than a code improvement.

### Improvement pass
Compared against issue #54 + `docs/slices/slice-5.md`. All 3 slots used on implemented fixes (no
deferred issue needed this round):

1. **New migration `f6a7b8c9d0e1`** - added `ix_events_user_id_resolved_date_earliest_created_at`
   on `events(user_id, resolved_date_earliest, created_at)`. The dashboard's every-page-load query
   filters by `user_id` and sorts by `resolved_date_earliest DESC NULLS LAST, created_at DESC`; the
   existing `uq_events_user_description_resolved_date` unique index starts with `user_id` but is
   otherwise keyed on text columns unrelated to this sort, so it can't serve the query. Up/down/up
   round-trip verified against QA (sole active branch at the time - merged promptly per the
   shared-QA migration convention).
2. **Redirect an out-of-range dashboard `page`** to the last valid page (e.g. a stale bookmark, or
   deleting the only event on the last page) instead of showing a misleading "No events yet" -
   the JSON API still returns an honest empty list for the same out-of-range `page` rather than
   redirecting a request a client didn't ask to be redirected from.
3. **Show the total event count** near the dashboard heading (`"N events total"`) - cheap, and
   gives the pagination controls useful context.

## 2026-07-03 — #52 Slice 4.1 upload page + 7-step pipeline

### Execution model — followed the resolved in-process decision over the stale spec wording
`docs/slices/slice-4.md` and the issue body still say "Celery task / `ALWAYS_EAGER`", but #52's
resolved-decision comment (2026-07-03) is explicit: run the pipeline as an **in-process asyncio
background task, no Celery/Redis**, state in Postgres, the background task opens its own DB session.
Built it that way; left the dormant `app/worker.py` Celery stub unused. Recorded here because the
two docs visibly disagree with what was built.

### Date-window vs. the real-Gemini golden file
The "Filter by Date (default 7-day window)" step and the AC "assert dashboard rows match
`example.lmmoutput.txt`" are contradictory as written: the example conversation spans ~30 days and
the golden output has events across that whole span, so a real 7-day filter would drop most of them.
Resolved by making `window_days` a **parameter (default 7)**: the 7-day behaviour is unit-tested on
a synthetic conversation (`test_message_filter.py`), and the real-Gemini e2e test passes a wide
window so it can reproduce the full golden output. The stubbed integration test is unaffected (the
fake Gemini returns the golden payload regardless of the filtered input).

### Google Drive provider — real code, but live behaviour is manual-QA only
Built the concrete `GoogleDriveStorageProvider` (Drive REST v3 via httpx) per the resolved decision,
with unit tests driven through `httpx.MockTransport` covering request-building + token refresh. Its
**live** behaviour (real Drive folders + OAuth) can't be exercised in CI and wasn't by me — flagged
for manual QA in the PR. Every automated AC is met via the `FakeStorageProvider` seam
(`E2E_TEST_MODE`) and DB assertions.

### Improvement pass
Compared against issue #52 + the slice spec. Outcome:

- **Implemented now (2):**
  - Bounded the upload read to `MAX_UPLOAD_BYTES + 1` so an oversized file is rejected without
    reading the whole thing into memory first (OOM/DoS safety).
  - Added `StorageProvider.aclose()` (no-op default; `GoogleDriveStorageProvider` closes its httpx
    client) and call it in the background scheduler's `finally`, so each upload doesn't leak a
    connection pool.
- **Deferred → GitHub issue** (labels `slice4` + `modelsuggested` + `intake`, backlog column):
  - #68 — persist the refreshed Drive access token back to `storage_configs` (currently in-memory
    per run). Efficiency only; not required for correctness.

### "intake" status substitution
Same as #51: no `intake` status option exists on the board, so #68 got an **`intake` label** in the
**backlog** column rather than risk rewriting the single-select option set.

## 2026-07-03 — #51 Slice 4.0 pipeline foundation

### Improvement pass
Compared the work against issue #51 + `docs/slices/slice-4.md`. Outcome:

- **Implemented now:** a fixture-driven `date_parser` test that runs `parse_earliest_date` over
  every `resolved_date` in `examples/example.lmmoutput.txt` (all 22 real values), asserting each
  resolves and the three multi-date values return their earliest date. Cheap, high-value coverage
  against real data.
- **Deferred → GitHub issues** (labels `slice4` + `modelsuggested` + `intake`):
  - #64 — request structured JSON output from Gemini (`response_mime_type` + `response_schema`).
    Belongs with the parse step + live-key check in #52.
  - #65 — make the Gemini model name settings-configurable rather than hardcoded. Low priority.

### "intake" status substitution
`/to-implementation` asks deferred-improvement issues to be filed "with the status of intake".
The OrganizeMe board's Status field has only `backlog / Todo / In Progress / Done` — no `intake`
option. Adding a single-select option via the API requires rewriting the whole option set and can
unset every issue's status if done wrong, so it was judged too risky to do autonomously. Instead
the two issues were given an **`intake` label** and placed in the **`backlog`** column (the closest
existing not-yet-scheduled state). If a real `intake` status column is wanted, add it to the board
manually and re-file these.
