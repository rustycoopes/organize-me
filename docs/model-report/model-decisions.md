# Model decisions

Decisions taken by the model during autonomous implementation runs, recorded for later review.

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
