# Model decisions

Decisions taken by the model during autonomous implementation runs, recorded for later review.

## 2026-07-04 — Issue selection for autonomous run (picked #54)

### Board Status still not directly readable — reconstructed again
Same constraint as the earlier #53 run: `gh` is absent and the agent proxy serves only a pinned set
of PR-review REST ops, blocking the Projects v2 GraphQL endpoint entirely. The board Status column
(`backlog / Todo / In Progress / Done`) can be neither **read** nor **written** programmatically
this session, so the `next-issue` helper (`todo_issues.py`) cannot run and later "move to In
Progress / Done" board mutations are impossible. Selection was reconstructed from labels + open
PR/branch signals; board-column transitions in this run are recorded via issue comments instead of
real board moves, and this limitation is noted on the issue.

### Pick: #54 (Slice 5.1 — Events dashboard table + calendar/tasks links + delete)
- Slice 4's last planned enhancement (#53) is now merged (PR #53/commit 6d1dff9), so Slice 5 is the
  earliest slice with actionable planned work. Its `enhancement` issues are #54, #55, #56.
- #54 is the unblocker: #55 and #56 are both "Blocked by #54"; #54's own blocker #52 is merged. It
  is the foundational, first-user-visible piece of the slice.
- No branch and no PR touches #54–#56 → not In Progress. The only open PR (#70) targets #43 →
  treated as owned/In Progress → skipped.
- Slice 1 (#29–#43) and the Slice 4 `intake`/`modelsuggested` items (#64, #65, #68) are deferred
  backlog (lowest tier), not competing Todo work — consistent with the earlier entry below.
- Autonomous run: no user available within the 60s window, so recording the choice here per the
  `next-issue` no-response rule.

## 2026-07-04 — Issue selection for autonomous run (picked #53)

### Board Status was not directly readable — reconstructed it
The OrganizeMe Projects v2 board Status field (`backlog / Todo / In Progress / Done`) could not be
read this session: `gh` is not installed and the agent proxy serves only a pinned set of PR-review
GraphQL operations (Projects v2 needs GraphQL, and there is no REST equivalent). The
`next-issue` helper (`todo_issues.py`) therefore could not run. Board state was instead
reconstructed from `docs/project-status.md`, merged PRs, open PRs, and existing branches.

### Pick: #53 (Slice 4.2 — Live SSE pipeline progress page)
- Slice 4 is the earliest slice with actionable planned work: its foundation #51 (PR #66) and #52
  (PR #69) are merged, and #53 — the next Slice 4 enhancement — is open, unblocked (blocker #52
  merged), with **no branch and no PR**, so it is not In Progress.
- #43 has an open PR (#70) → treated as In Progress / owned by another worker → skipped.
- Slice 1 issues #29–#42 are all `future-enhancement` — the deliberately-deferred backlog the
  project has advanced past; this decisions log already records that such items sit in the
  **backlog** column, not Todo, so they are not competing Todo work.
- Slice 5 (#54–#56) is a higher-numbered slice → loses to Slice 4's remaining #53.
- No user was available to confirm within the 60s window (autonomous run); recording the choice
  here per the `next-issue` no-response rule.

## 2026-07-04 — #53 Slice 4.2 live SSE pipeline progress page

### Branch — used the assigned run branch, not a `feature/…` branch
This autonomous run was assigned the branch `claude/admiring-carson-bzzfow` (and told never to push
elsewhere), so all work landed there rather than on a `feature/slice-4.2-…` branch as CLAUDE.md's
convention would otherwise suggest. The branch was reset from the latest `origin/main` and developed
in the primary checkout (already the isolated per-session container), so a second worktree was
unnecessary.

### Board status could not be moved to "In Progress"
The board's Status is a Projects v2 field, only mutable via GraphQL, which the session's egress
proxy blocks (only pinned PR-review GraphQL ops are served) — and `gh` isn't installed. So the issue
could not be programmatically moved to In Progress / Done. Recorded here; the PR closes #53 on merge,
and the final board move is noted as a manual follow-up in the issue comment.

### E2E Gemini fake wired into the factory (not just tests)
The Playwright acceptance test needs a *successful* run in CI, but `E2E_TEST_MODE` only faked the
storage provider, not Gemini — so `get_gemini_client` now returns a `FakeGeminiClient` under
`E2E_TEST_MODE`, seeded with a small **inline** canned payload rather than reading
`examples/example.lmmoutput.txt` (that fixture is excluded from the deployed image by
`.dockerignore`, so it can't be read at runtime on QA). The Upload page also treats `E2E_TEST_MODE`
as Drive-connected so its dropzone is enabled. This mirrors the resolved-decision comment ("the
Gemini step to the injected fake").

### SSE reads via per-statement fresh selects, no cross-poll transaction reset
`stream_run_progress` re-selects the step/run rows each poll using column selects (not ORM-identity
reads). Under Postgres READ COMMITTED each statement takes a fresh snapshot, so the in-process
pipeline's commits are visible poll-to-poll without ending the stream's read-only transaction —
important because the same session object is a rolled-back SAVEPOINT in tests (a `rollback()` between
polls would have discarded the seeded run).

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
