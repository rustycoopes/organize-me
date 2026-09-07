# Slice 1 — Stacked-table pattern + Dashboard adoption

> Part of the `mobile-responsive-tables` feature. PRD: [`../PRD.md`](../PRD.md) · Technical design:
> [`../TDD.md`](../TDD.md)

**Delivers:** On a phone, the Event Creator Dashboard renders each event as a labelled card with
no horizontal scroll, and the filter/sort controls collapse behind a "Filters (N)" toggle.

## What to build

Spans two repos. The chrome change must be released before Event Creator can adopt it.

### organize-me (`packages/chrome`)

- `organizeme_chrome/static/css/components.css` (new) — the `.om-stacked-table` pattern: below
  `max-width: 1023.98px`, `thead` becomes sr-only (kept for a11y), each `tr` a bordered card,
  each `td` a block with its `data-label` shown via `::before`, and a reset of `display` /
  `max-width` / `width` / `white-space` so per-cell utilities (`truncate`, `max-w-xs`, `w-10`)
  don't fight the card layout. Empty `data-label` suppresses the `::before`.
- `organizeme_chrome.paths.chrome_components_css_path()` (new, sibling of the tokens helper).
- `organizeme_chrome/design/classes.py` — `STACKED_TABLE_CLASS = "om-stacked-table"` with a
  docstring stating the full contract (class on `<table>`; every `<td>` needs `data-label`;
  `<thead>` retained; cells not utility-controllable below `lg`; requires the `components.css`
  import).
- `packages/chrome/DESIGN.md` — a "Responsive tables" section with the contract + the
  `1023.98px == lg` breakpoint note.
- `pyproject.toml` → `0.20.0`; tag `chrome-v0.20.0` on that commit.

### event-creator

- Bump the `organizeme-chrome` pin to `chrome-v0.20.0`; add `@import ".../components.css";` to the
  Tailwind entry CSS; extend `scripts/verify_css_build.py` to assert `.om-stacked-table` is
  present in the compiled `app/static/css/app.css`.
- `app/templates/partials/events_panel.html` — `.om-stacked-table` on `<table id="events-table">`;
  `data-label` on every `<td>` (`""`, `Type`, `Description`, `Resolved date`, `Raw date text`,
  `Agreed by`, `Calendar`, `Tasks`, `Reviewed`, `""`); `max-w-[calc(100vw-2rem)]` on the two
  `<dialog>` confirm modals (local, not chrome).
- `app/templates/partials/dashboard_body.html` — wrap the filter `<form>` in a checkbox-`peer`
  disclosure: a `Filters ({{ active_filter_count }})` label-button shown only below `lg`, form
  `hidden`/`peer-checked:block` below `lg` and `lg:block` above. Change the search input's
  `hx-trigger` from `keyup changed delay:500ms` to `search, change` so it doesn't swap the
  fragment (collapsing the panel) mid-type.
- `app/pages/dashboard.py` — add `active_filter_count = sum(1 for f in (type, parsed_date_from,
  parsed_date_to, q, show_reviewed) if f)` to the template context (do **not** reuse
  `has_active_filters` — it folds in `event_types`).

### organize-me (Host)

- Add the inert `@import ".../components.css";` to the Host's Tailwind entry CSS (confirmed in
  design — keeps the four consumers from diverging). Host has no tables using the pattern; this
  is wiring only.

### Verification (no deploy)

Rebuild `doc-library` / `ha-dashboard` / Host `app.css` against the candidate `tokens.css` +
`components.css` and diff — expected delta is only the added `@media` block for services that add
the import, zero for those that don't.

## Design notes

- CSS home + unlayered import + contract:
  [`../../../adr/mobile-responsive-tables-css-delivery.md`](../../../adr/mobile-responsive-tables-css-delivery.md).
- `lg` breakpoint aligned with the sidebar drawer:
  [`../../../adr/mobile-responsive-tables-breakpoint.md`](../../../adr/mobile-responsive-tables-breakpoint.md).
- Checkbox-`peer` disclosure inside the fragment, search-trigger change, `active_filter_count`
  source: [`../../../adr/mobile-responsive-tables-filter-disclosure.md`](../../../adr/mobile-responsive-tables-filter-disclosure.md).
- This is a deliberate part-horizontal slice — the chrome release changes no rendered output on
  its own; value lands with the Event Creator adoption in the same slice. TDD "WBS shape".
- `publish-chrome.yml` runs the chrome package's tests only on **tag push**, not the PR.
- e2e runs against deployed QA only — the mobile checks are a post-deploy regression guard; the
  pre-merge visual gate is the screenshot audit.

## Blocked by

None — can start immediately. (Internal ordering: chrome PR + tag + green `publish-chrome` before
the event-creator pin bump resolves.)

## Acceptance criteria

- [ ] `chrome-v0.20.0` tag pushed; `publish-chrome` green; `pyproject.toml` version == tag.
- [ ] chrome package test asserts `components.css` ships with `.om-stacked-table`,
      `content: attr(data-label)`, and `1023.98px`, and that `STACKED_TABLE_CLASS` is importable.
- [ ] `event-creator`'s `verify_css_build.py` fails the build if `.om-stacked-table` is absent
      from compiled `app.css`.
- [ ] Below 1024px the Dashboard events table renders as cards — each field labelled, no
      horizontal document scroll; the `Details`-style long text is fully shown, not truncated.
- [ ] At/above 1024px the events table renders exactly as before.
- [ ] Below 1024px the filter/sort form is hidden until "Filters" is tapped; the button shows the
      correct active count; typing in Search does not collapse the panel.
- [ ] The delete-confirm dialogs fit within a 375px viewport.
- [ ] `doc-library` / `ha-dashboard` `app.css` rebuild shows zero delta from the new chrome
      version (import not added); Host shows only the added `@media` block.
- [ ] Before/after screenshots of the Dashboard at ~375px attached to this slice.

## Testing

- **chrome — `packages/chrome/tests/`** (new test, mirroring `test_dark_mode_coverage.py`):
  `chrome_components_css_path()` resolves; file text contains the three stable tokens above;
  `STACKED_TABLE_CLASS` importable from `organizeme_chrome.design` and its value in the CSS.
- **event-creator — `tests/test_dashboard_page.py`**: `assert "om-stacked-table" in response.text`;
  `assert 'data-label="Description"' in response.text`; `assert "Filters (2)" in response.text`
  for a 2-filter request vs the unfiltered case. String-contains, matching the file's existing
  `"Page 1 of 2"` style.
- **event-creator — `scripts/verify_css_build.py`**: the new canary assertion.
- **event-creator — `e2e/tests/dashboard.spec.ts`**: a `test.describe` with
  `test.use({ viewport: { width: 375, height: 812 } })` — no horizontal overflow, a `data-label`
  value visible, filter form hidden until toggled, "Filters (N)" count. Runs against deployed QA.
- **Screenshot audit**: event-creator run locally at ~375px, before/after Dashboard.

<!-- /to-implementation appends a "## Delivered" section here once this slice ships. -->
