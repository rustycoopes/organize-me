# Slice 2 — Logs page adoption

> Part of the `mobile-responsive-tables` feature. PRD: [`../PRD.md`](../PRD.md) · Technical design:
> [`../TDD.md`](../TDD.md)

**Delivers:** On a phone, the Event Creator Logs page renders each processing run as a labelled
card with no horizontal scroll, and its filter/sort controls collapse behind a "Filters (N)"
toggle.

> Published as [`rustycoopes/event-creator#50`](https://github.com/rustycoopes/event-creator/issues/50).

## What to build

All in `event-creator` — the `.om-stacked-table` pattern and the chrome pin are already in place
from Slice 1.

- `app/templates/partials/logs_grid.html` — `.om-stacked-table` on `<table id="logs-grid">`;
  `data-label` on every `<td>` (`Date`, `Filename`, `Status`, `Events`, `Details`). Keep the
  whole-row `role="link"` / `onclick` navigation (a card-sized tap target is fine); confirm the
  inner date `<a>` still `stopPropagation`s so it doesn't double-navigate. The `truncate` /
  `max-w-xs` on the Details cell is overridden by the card-mode reset — full text on mobile, as
  intended.
- `app/templates/partials/logs_body.html` — wrap the filter `<form>` in the same checkbox-`peer`
  disclosure as the Dashboard: `Filters ({{ active_filter_count }})` label-button below `lg`,
  form `hidden`/`peer-checked:block` below `lg` and `lg:block` above.
- `app/pages/logs.py` — add `active_filter_count = sum(1 for f in (run_status, parsed_date_from,
  parsed_date_to) if f)` to the template context.

## Design notes

- Same three ADRs as Slice 1: CSS delivery, breakpoint, filter disclosure. The Logs filter bar
  has no free-text search input, so the `hx-trigger` change from Slice 1 doesn't apply here.
- Logs' `has_active_filters` (`logs.py`) is already a faithful filter predicate (no `event_types`
  term) — but still add the explicit `active_filter_count` for the button rather than reusing a
  bool.

## Blocked by

- [`rustycoopes/event-creator#49`](https://github.com/rustycoopes/event-creator/issues/49)
  (Slice 1b) — needs the `chrome-v0.20.0` pin bump, the `components.css` import, and the
  `playwright.config` mobile `describe` / `verify_css_build` assertion it introduces. Independent
  of Slice 1b's Dashboard *template* work, but rebases on the shared config/pin changes.

## Acceptance criteria

- [ ] Below 1024px the Logs runs table renders as cards — each field labelled, no horizontal
      document scroll; the `Details` text is fully shown, not truncated.
- [ ] At/above 1024px the runs table renders exactly as before.
- [ ] Tapping a run's card still navigates to that run's detail page; the inner date link does
      not double-navigate.
- [ ] Below 1024px the filter/sort form is hidden until "Filters" is tapped; the button shows the
      correct active count.
- [ ] Before/after screenshots of the Logs page at ~375px attached to this slice.

## Testing

- **event-creator — `tests/test_logs_page.py`**: `assert "om-stacked-table" in response.text`;
  `assert 'data-label="Filename"' in response.text`; `assert "Filters (1)" in response.text` for
  a filtered request vs the unfiltered case. String-contains style.
- **event-creator — `e2e/tests/logs.spec.ts`**: a `test.describe` with
  `test.use({ viewport: { width: 375, height: 812 } })` — no horizontal overflow, a `data-label`
  value visible, filter form hidden until toggled, "Filters (N)" count, row-card navigation.
  Reuses the mobile-viewport pattern Slice 1 adds.
- **Screenshot audit**: event-creator run locally at ~375px, before/after Logs.

<!-- /to-implementation appends a "## Delivered" section here once this slice ships. -->

## Delivered (2026-09-10, issue [`event-creator#50`](https://github.com/rustycoopes/event-creator/issues/50), branch `feature/mobile-responsive-tables-logs`)

The Event Creator Logs page adopts the `.om-stacked-table` pattern + the mobile filter/sort
disclosure. All in the `event-creator` repo (PR
[`#55`](https://github.com/rustycoopes/event-creator/pull/55)). The `chrome-v0.20.1` pin,
`components.css` import and `verify_css_build` canary were already in place from Slice 1b (#49),
so this slice is templates + one context value + tests.

**Shipped:**

- `app/templates/partials/logs_grid.html` — `om-stacked-table` on `<table id="logs-grid">`;
  `data-label` on all five `<td>`s (`Date`, `Filename`, `Status`, `Events`, `Details`). The
  whole-row `role="link"` / `onclick` navigation and the inner date `<a>`'s
  `onclick="event.stopPropagation()"` are unchanged; the `Details` cell keeps `max-w-xs truncate`
  (reset by the card layout below `lg`, so mobile shows the full text).
- `app/templates/partials/logs_body.html` — filter `<form>` wrapped in the same checkbox-`peer`
  disclosure as the Dashboard: `Filters ({{ active_filter_count }})` label shown only below `lg`,
  form `hidden peer-checked:flex lg:flex`, checkbox `sr-only lg:hidden` (keyboard-operable on
  mobile, out of the tab order at `lg`+). Logs has no free-text search, so the form keeps its
  plain `hx-trigger="change"`.
- `app/pages/logs.py` — `active_filter_count = sum(1 for f in (run_status, parsed_date_from,
  parsed_date_to) if f)` added to the template context; `has_active_filters` is now just
  `active_filter_count > 0` (same tuple, no `event_types`-style term).
- Tests: `tests/test_logs_page.py` — 3 string-contains tests (`om-stacked-table` + `data-label`s;
  `Filters (0)` vs `Filters (1)`; the mobile sort `<select>`s present + current sort round-trips).
  `e2e/tests/logs.spec.ts` — a `test.describe` with `test.use({ viewport: { width: 375, height:
  812 } })`: card layout active, `data-label` `::before` visible, no horizontal document scroll,
  filter form collapsed until "Filters" is tapped (and until Space on the focused toggle), sort
  control reachable + re-sorts, `Filters (N)` count re-renders on swap, row-card navigation.

**Diverged from the plan:**

- **Added a mobile sort control** (code-review finding, below) — the plan only wrapped the filter
  `<form>`, but Logs' sort UI lives entirely in the grid's `<thead>` column links, which
  `.om-stacked-table` visually hides below `lg`. `logs_body.html` now carries `sort_by`/`sort_dir`
  `<select>`s in an `lg:hidden` wrapper — the mobile sort UI, and (still `display:none`-serialized
  at `lg`+) the sort carrier for filter changes that the removed hidden inputs used to be.
- **Dropped the QA pipeline** (rode along on this PR, user-approved) — CI's Supabase QA project
  was torn down mid-implementation (`alembic upgrade head` failing with `(ENOTFOUND) tenant/user
  … not found`). `event-creator`'s `ci.yml` now mirrors `organize-me`'s 2026-09-08
  `refactor: drop QA environment from the pipeline`: the `deploy-qa` / `e2e-boundary-qa` /
  `e2e-qa` jobs are gone, and the `test` job points `DATABASE_URL` at Supabase **prod** (exactly
  as `deploy.yml`'s own `test` job already does on every merge; test writes roll back in a
  SAVEPOINT). Ephemeral Postgres isn't viable — `event-creator`'s only migration is a no-op
  baseline that adopts `organize-me`-created tables. The Playwright `e2e/` suite (this slice's
  and Slice 1b's mobile `describe`s included) is now **local-only**; the CI gate is the
  `test_logs_page.py` markup assertions.
- **Screenshot audit:** not captured — same machine limitation Slice 1b hit (the MCP-driven
  Chrome window won't resize below the desktop viewport — `window.innerWidth` stays at 1440 — and
  there's no local Postgres to run the app against). Deployed-prod DOM was checked instead:
  `#logs-grid` carries `om-stacked-table` and the `Filters (0)` disclosure label renders. The
  375px behaviour is otherwise asserted by the CI page tests and the local-only Playwright
  `describe`. Before/after screenshots to be attached here by hand.

**Code review** (`/code-review`, high) — one finding fixed in this branch:

- Below `lg`, `.om-stacked-table` visually hides the grid's `<thead>`, so the column-header sort
  links (Logs' only sort UI, unlike the Dashboard's single in-form toggle) became unreachable on
  mobile — a regression against the slice's "filter/**sort** controls collapse behind a toggle"
  deliverable. Fixed by adding `sort_by`/`sort_dir` `<select>`s to the filter form (see the
  divergence above). Two lower-severity notes (the `has_active_filters` duplication; the
  date-range panel-collapse) were also addressed / already tracked — see below.

**Follow-up filed:** none new. The date-range panel-collapse note is the same behaviour already
tracked as [`event-creator#53`](https://github.com/rustycoopes/event-creator/issues/53)
(`modelsuggested`, filed by Slice 1b) — it applies identically to the Logs disclosure.
