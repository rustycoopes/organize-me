# Mobile-Responsive Tables — Technical Design

**Feature:** [`PRD.md`](PRD.md)
**Date:** 2026-09-07
**Status:** Draft

## Architecture at a Glance

- A `.om-stacked-table` pattern (~20 lines of raw CSS) ships in a **new**
  `organizeme_chrome/static/css/components.css`, resolved by a new
  `chrome_components_css_path()` helper, imported **unlayered** by consumers so it reliably beats
  per-cell Tailwind utilities. `tokens.css` stays tokens-only.
  ([ADR: css-delivery](../../adr/mobile-responsive-tables-css-delivery.md))
- The pattern flips tables to labelled cards at **`max-width: 1023.98px`** — the same width where
  the shared sidebar becomes a hamburger drawer, so there is no frame-mobile / table-desktop
  in-between state. ([ADR: breakpoint](../../adr/mobile-responsive-tables-breakpoint.md))
- Event Creator adopts: `.om-stacked-table` + `data-label` on the `events_panel.html` and
  `logs_grid.html` tables, plus a **CSS checkbox-`peer` filter disclosure** inside each page's
  HTMX fragment with a server-computed `active_filter_count`.
  ([ADR: filter-disclosure](../../adr/mobile-responsive-tables-filter-disclosure.md))
- Released as chrome **`v0.20.0`** (tag == `pyproject.toml` version). Only `event-creator` (and
  the Host, for the `components.css` import wiring) adopt; `doc-library` / `ha-dashboard` are
  untouched and unaffected.

## Design Decisions

### 1. `components.css` — the shipped pattern

See [ADR: css-delivery](../../adr/mobile-responsive-tables-css-delivery.md). Sketch:

```css
/* organizeme_chrome/static/css/components.css */
@media (max-width: 1023.98px) {           /* == Tailwind lg (64rem); see DESIGN.md */
  .om-stacked-table thead {
    position: absolute; width: 1px; height: 1px;
    overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap;   /* sr-only, thead kept for a11y */
  }
  .om-stacked-table tr {
    display: block;
    border: 1px solid var(--color-ink-2, #454b56);
    border-radius: 0.5rem;
    padding: 0.5rem 0.75rem;
    margin-bottom: 0.5rem;
  }
  .om-stacked-table td {
    display: block;
    max-width: none; width: auto;         /* defeat max-w-xs / w-10 utilities */
    white-space: normal;                   /* defeat truncate */
    padding: 0.25rem 0;
    text-align: left;
  }
  .om-stacked-table td[data-label]:not([data-label=""])::before {
    content: attr(data-label) ": ";
    font-weight: 600;
    color: var(--color-ink-2, #454b56);
  }
}
```

- Dark mode: the borders/labels use design-token CSS variables, so light and dark both work with
  no extra block.
- `<thead>` is hidden with an sr-only clip, not `display:none`, so screen readers still get the
  th↔td association; `data-label` is cosmetic only.
- Empty `data-label` suppresses the `::before` (checkbox / actions columns).
- The `td` reset is what makes the unlayered import matter — see the ADR.

New Python: `organizeme_chrome.paths.chrome_components_css_path()` (sibling of the tokens helper)
and a constant in `organizeme_chrome/design/classes.py`:

```python
# organizeme_chrome/design/classes.py
STACKED_TABLE_CLASS = "om-stacked-table"
"""Responsive stacked-card table. Put this on the <table> element. Every <td> needs
data-label="<column name>" (empty string for checkbox/actions columns). Keep <thead> — it is
visually hidden below lg but retained for assistive tech. Cells cannot be controlled with
Tailwind utilities below lg (the shipped rule is unlayered and wins). Requires the consumer's
Tailwind entry CSS to @import organizeme_chrome/static/css/components.css."""
```

`packages/chrome/DESIGN.md` gets a short "Responsive tables" section with the same contract and
the breakpoint note.

### 2. Consumer wiring

Each adopting service adds one line to its Tailwind entry CSS (`event-creator` and the Host in
this feature):

```css
@import "tailwindcss";
@import "…/organizeme_chrome/static/css/tokens.css";
@import "…/organizeme_chrome/static/css/components.css";   /* new */
```

and must re-run `pytailwindcss` after bumping the chrome pin (already required for any chrome
bump). `event-creator`'s `scripts/verify_css_build.py` (the `#46` canary-class check) gains an
assertion that `.om-stacked-table` is present in the compiled `app/static/css/app.css` — so a
Tailwind-scanning regression that drops it fails the build loudly, pre-deploy.

### 3. Event Creator table adoption

**`app/templates/partials/events_panel.html`** — `.om-stacked-table` on `<table id="events-table">`
(not the `x-data` wrapper div). `data-label` on every `<td>`:
`""` (select checkbox), `Type`, `Description`, `Resolved date`, `Raw date text`, `Agreed by`,
`Calendar`, `Tasks`, `Reviewed`, `""` (actions). Per-row controls are unchanged — they flow into
the card. The two `<dialog>` confirm modals get `max-w-[calc(100vw-2rem)]` (local, not chrome —
only the Dashboard has them).

**`app/templates/partials/logs_grid.html`** — `.om-stacked-table` on `<table id="logs-grid">`.
`data-label`: `Date`, `Filename`, `Status`, `Events`, `Details`. The whole-row
`role="link"` / `onclick` navigation is kept (a card-sized tap target is fine); confirm the inner
date `<a>` still `stopPropagation`s so it doesn't double-navigate. The `truncate` / `max-w-xs` on
the Details cell is overridden by the `.om-stacked-table td` reset in card mode (full text, no
clip) — the desired mobile behaviour.

### 4. Filter disclosure

See [ADR: filter-disclosure](../../adr/mobile-responsive-tables-filter-disclosure.md).

- `dashboard_body.html` / `logs_body.html`: wrap the filter `<form>` in a checkbox-`peer`
  disclosure. `<label for>` button reads `Filters ({{ active_filter_count }})`, shown only
  below `lg` (`lg:hidden`); the form is `hidden`/`peer-checked:block` below `lg` and always shown
  `lg:block` above.
- Search input `hx-trigger` changes from `keyup changed delay:500ms` to `search, change` (fires
  on blur / enter / native clear) so it never swaps the fragment — and collapses the panel —
  while being typed into. (If desktop should keep live-search, gate the two triggers by a media
  query or ship both and accept the mobile one firing on blur too; implementer's call.)
- `active_filter_count` — new explicit context int in `app/pages/dashboard.py` and
  `app/pages/logs.py`, next to the existing `has_active_filters` (which is **not** reused — it
  folds in `event_types`):
  - Dashboard: `sum(1 for f in (type, parsed_date_from, parsed_date_to, q, show_reviewed) if f)`
  - Logs: `sum(1 for f in (run_status, parsed_date_from, parsed_date_to) if f)`

No change to filter/sort/pagination behaviour, HTMX swap targets, or any API.

### 5. Chrome release

- Bump `packages/chrome/pyproject.toml` to `0.20.0`; tag `chrome-v0.20.0` on that commit
  (the established convention — tag always matches version). Additive minor.
- `publish-chrome.yml` runs the package's `pytest` + `mypy` **only on tag push**, not on the PR.
  So the chrome slice's Definition of Done includes: tag pushed, `publish-chrome` green, re-tag
  `0.20.1` if red. Landing the PR on `organize-me` main changes no rendered output anywhere (even
  the Host builds from its own pinned tag).
- `event-creator` bumps `organizeme-chrome @ git+…@chrome-v0.20.0` and adds the `components.css`
  import + template changes in its own repo, against the published tag.

### 6. Zero-blast-radius verification (not a deploy)

Before claiming "additive, no-op for non-adopters": in `/to-implementation` for the chrome slice,
rebuild `doc-library` / `ha-dashboard` / Host `app.css` against the candidate `tokens.css` +
`components.css` and diff. Expected delta: only the added `@media` block for services that add
the import; **zero** delta for services that don't. Demonstrated, not asserted. Deploys nothing.

## Component / Data Flow

```
organizeme-chrome  ──(tag chrome-v0.20.0)──►  components.css + STACKED_TABLE_CLASS
        │                                        chrome_components_css_path()
        ▼
event-creator pyproject pin bump ──► Docker build ──► pytailwindcss:
   entry.css  @import tailwindcss
              @import tokens.css
              @import components.css   ─────────────►  app/static/css/app.css  (contains .om-stacked-table)
                                                        verify_css_build.py asserts it present
        ▼
GET /dashboard  ──► dashboard.py builds context incl. active_filter_count
                    dashboard.html → dashboard_body.html (disclosure + form)
                                   → events_panel.html  <table class="om-stacked-table">
                                                         <td data-label="Description">…

viewport < 1024px  ──►  components.css @media: thead sr-only, tr→card, td→block + ::before label
viewport ≥ 1024px  ──►  @media inert; table renders exactly as today
```

## Testing Approach

Assert on rendered markup and on behaviour at a viewport — never on CSS rule bodies.

| Seam | File | Cases |
|---|---|---|
| chrome package ships the pattern | **`packages/chrome/tests/`** (new test, mirroring `test_dark_mode_coverage.py`) | `chrome_components_css_path()` resolves; file text contains `.om-stacked-table`, `content: attr(data-label)`, `1023.98px`; `STACKED_TABLE_CLASS` importable from `organizeme_chrome.design` and its value appears in the CSS. Assert the *stable core* only, not full rule bodies. |
| EC template emits the contract | `event-creator/tests/test_dashboard_page.py`, `test_logs_page.py` | `assert "om-stacked-table" in response.text`; `assert 'data-label="Description"' in response.text` (one representative cell); `assert "Filters (2)" in response.text` for a 2-filter request vs the unfiltered case. String-contains, matching the files' existing `"Page 1 of 2"` style — no BeautifulSoup. |
| EC build actually ships the CSS | `event-creator/scripts/verify_css_build.py` | extend the `#46` canary check: `.om-stacked-table` present in compiled `app.css` → fail build if absent. Pre-deploy. |
| End-to-end at mobile width | `event-creator/e2e/tests/dashboard.spec.ts`, `logs.spec.ts` | a `test.describe` block with `test.use({ viewport: { width: 375, height: 812 } })` (not a new Playwright project — that re-runs all 8 specs remotely; not `devices['Pixel 5']` — that flips `isMobile`/`hasTouch` too). Assert: no horizontal document overflow; a known `data-label` value visible next to its value; filter form hidden until the "Filters" label is clicked; "Filters (N)" shows N when a filter is applied. Runs against **deployed QA only** — regression guard, not a merge gate. |
| Visual sign-off | design-time, not CI | run event-creator locally at ~375px, before/after screenshots of Dashboard + Logs attached to this TDD / the WBS slice. This is the pre-merge visual gate. |

Out of scope for automated coverage: computed styles / actual card rendering in a unit test; the
chrome↔consumer integration (rule shipped in package vs rule in served bundle) is only fully
proven post-deploy on QA — accepted, with the `verify_css_build.py` assertion as the pre-deploy
proxy.

## Open Questions

1. **Desktop live-search** — keep `keyup` debounced search above `lg` (two triggers gated by
   media query) or accept `search, change` everywhere? Leaning "accept everywhere" (simpler,
   blur-to-search is fine on desktop too) but flag for the implementer.
2. **`components.css` import into the Host** — the Host doesn't have these tables, but wiring the
   import now keeps the four consumers from diverging further. Confirm the Host maintainer is OK
   adding an inert `@import` in the same slice, or defer it.
3. **`data-label` for `Agreed by` / `Calendar` / `Tasks`** — the card label for a column of
   initials-badges or an "Add" link. `"Agreed by"`, `"Calendar"`, `"Tasks"` read fine; confirm
   during the screenshot audit.
4. **Logs row-as-card navigation** — whole card is a click target with a nested date link.
   Confirm intentional; adjust if double-navigation shows up in the e2e.

## WBS shape (for `/to-wbs`)

Three slices. Slice 1 is a deliberate **horizontal enabling slice** (releasing the pattern
changes no rendered output on its own — acknowledge this in the granularity quiz):

- **Slice 1 — chrome pattern + release.** `components.css`, `chrome_components_css_path()`,
  `STACKED_TABLE_CLASS` + docstring, `DESIGN.md` section, package test, `pyproject.toml` 0.20.0.
  *Blocked by:* nothing. *Acceptance:* `chrome-v0.20.0` tag pushed, `publish-chrome` green,
  package test asserts the rule ships, zero-blast-radius diff done.
- **Slice 2 — Dashboard adoption.** EC pin bump + `components.css` import +
  `verify_css_build.py` assertion + `events_panel.html` class/`data-label` + dialog width +
  Dashboard filter disclosure + `active_filter_count` in `dashboard.py` + `playwright.config`
  mobile `describe` + `test_dashboard_page` assertions + screenshots.
  *Blocked by:* Slice 1 (`chrome-v0.20.0` exists).
- **Slice 3 — Logs adoption.** `logs_grid.html` class/`data-label` + Logs filter disclosure +
  `active_filter_count` in `logs.py` + `logs.mobile` e2e + `test_logs_page` assertions +
  screenshots. *Blocked by:* Slice 1. Independent of Slice 2, **except** both touch
  `playwright.config.ts` and the EC pin/import — Slice 2 adds those; Slice 3 rebases on them (or
  swap the order).
