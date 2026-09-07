# Slice 2 — Logs page adoption

> Part of the `mobile-responsive-tables` feature. PRD: [`../PRD.md`](../PRD.md) · Technical design:
> [`../TDD.md`](../TDD.md)

**Delivers:** On a phone, the Event Creator Logs page renders each processing run as a labelled
card with no horizontal scroll, and its filter/sort controls collapse behind a "Filters (N)"
toggle.

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

- **Slice 1** — needs `chrome-v0.20.0`, the `components.css` import, and the `playwright.config`
  mobile `describe` / `verify_css_build` assertion it introduces. Independent of Slice 1's
  Dashboard *template* work, but rebases on the shared config/pin changes.

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
