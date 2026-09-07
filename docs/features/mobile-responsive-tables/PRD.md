## Problem Statement

Event Creator's Dashboard and Logs pages are unusable on a phone. The Dashboard's events table has
**ten columns** (select, Type, Description, Resolved date, Raw date text, Agreed by, Calendar,
Tasks, Reviewed, actions); the Logs page's runs table has five. Both are wrapped only in
`overflow-x-auto`, so on a narrow screen the user gets a desktop-width table they have to scrape
sideways through — columns off-screen, no way to see a row's full data at once. The filter/sort
bars above each table use `flex-wrap`, so with a few filters set they stack into a tall block that
pushes the actual data below the fold.

The shared chrome (`organizeme-chrome` package) already handles the *frame* well on mobile — the
sidebar collapses to a hamburger drawer, the viewport meta tag is set. The gap is entirely in
dense in-page content. The user wants to keep the product on the web for now (no native app) but
needs these screens to render legibly on a mobile browser: menus and layouts compressing to fit,
not just scrolling.

## Solution

Add a **stacked-card responsive table pattern** to the shared chrome package: below a set
breakpoint, a table opted into the pattern renders each row as a self-contained card — field
label above value, one field per line, no horizontal scroll. The pattern is ~15 lines of plain
CSS shipped in chrome's `tokens.css` (not Tailwind utilities — `td::before { content: attr(...) }`
and the table→card flip can't be expressed as utilities, and raw CSS in `tokens.css` sidesteps
the known Tailwind-v4 CLI class-scanning bug). A wrapper class plus `data-label` attributes on
each cell are all a template needs.

Apply the pattern to Event Creator's two table-heavy pages, and collapse each page's filter/sort
bar into a "Filters" disclosure below the breakpoint so the data is what's on screen first. Cut a
new `organizeme-chrome` release; Event Creator bumps its pin to adopt. The change is purely
additive — other chrome consumers (`doc-library`, `ha-dashboard`, the Host) are unaffected and
adopt on their own schedule.

## User Stories

1. As a user on my phone, I want to open the Dashboard and see my events without scrolling
   sideways, so that I can actually read them.
2. As a user on my phone, I want each event shown as a card with labelled fields, so that I can
   see everything about one event at once.
3. As a user on my phone, I want the Logs page's processing runs shown the same card way, so that
   I can check what's been processed from my phone.
4. As a user on my phone, I want the per-event actions (Calendar link, Tasks link, Reviewed
   toggle, Delete, select checkbox) to still be reachable inside each card, so that I don't lose
   any functionality by being on mobile.
5. As a user on my phone, I want the filter and sort controls tucked behind a "Filters" button,
   so that the first thing I see is my data, not a wall of form fields.
6. As a user on my phone, I want the "Filters" button to show how many filters are currently
   active, so that I know the list is filtered even when the controls are hidden.
7. As a user on a tablet or desktop, I want the tables to look and behave exactly as they do
   today, so that this change costs me nothing on a big screen.
8. As a user on my phone, I want the delete-confirmation dialogs to fit the screen, so that I can
   read them and reach the buttons.
9. As a user rotating my phone to landscape or using a small tablet, I want the layout to switch
   cleanly between card and table form at a predictable width, so that there's no broken
   in-between state.
10. As a user relying on a screen reader, I want the card layout to still expose each value with
    its field name, so that the mobile view is as understandable as the table.
11. As a developer on any OrganizeMe app, I want a documented `.om-stacked-table` class I can add
    to a table to get responsive card behaviour, so that I don't reinvent it per app.
12. As a developer, I want the chrome change to be additive and versioned, so that apps that
    don't adopt the new release keep working unchanged.
13. As a developer, I want a mobile-viewport end-to-end check on the Dashboard and Logs pages, so
    that a future change that breaks the card layout is caught.
14. As a developer, I want to see before/after screenshots of the two pages at phone width during
    design, so that there's a visual record the feature did what it set out to do.

## Implementation Decisions

**Repo:** `organize-me` — the pattern lives in the shared `packages/chrome` package. Event
Creator's template + e2e changes are made in the `event-creator` repo against the new chrome
release, tracked as slices of this feature.

**The responsive-table pattern (`packages/chrome`):**
- New CSS added to `src/organizeme_chrome/static/css/tokens.css` (shipped as package data, not
  compiled — consistent with `docs/adr/design-refresh-per-service-tailwind-build.md`). Keyed to a
  `.om-stacked-table` class on the table (or a wrapper). Below the breakpoint: `thead` visually
  hidden (kept for screen readers), each `tr` becomes a bordered, padded card with vertical
  spacing between cards, each `td` becomes a block showing its `data-label` value (via
  `::before { content: attr(data-label) }`) above the cell content. Above the breakpoint: no
  effect — the table renders exactly as now.
- Breakpoint: `768px` (`md`). Tables stack on phones and portrait tablets; the ten-column events
  table needs the room. Chosen to sit in the same family as the existing `lg:` sidebar
  breakpoint rather than introduce a third value.
- `src/organizeme_chrome/design/classes.py` gains a constant for the wrapper class name so
  templates reference it the same way they reference `TABLE_CLASSES` etc.
- Dark mode: the card borders/background use existing design tokens, so light/dark both work with
  no extra rules.
- Dialog width: the hand-rolled `<dialog>` confirm pattern (used on the Dashboard) gets a
  mobile-friendly max-width / margin treatment. Whether this ships as a shared class in chrome or
  a local tweak in `events_panel.html` is a `/to-design` call — it's a small change either way.

**Chrome release & rollout:**
- Cut a new `chrome-vX.Y.0` tag after the pattern lands. Event Creator bumps its
  `organizeme-chrome @ git+...@chrome-vX.Y.0` pin.
- No other consumer is touched. `doc-library`, `ha-dashboard`, and the Host stay on their current
  pins; the new CSS only activates for tables that opt in with the class, so adopting the release
  later is a no-op until they choose to use it.

**Event Creator template changes (`event-creator` repo):**
- `app/templates/partials/events_panel.html`: add `.om-stacked-table` to the events table, add
  `data-label` to every `<td>` (and the header cells keep their text for the desktop view).
  Per-row controls stay where they are — they just flow into the card below the breakpoint.
- `app/templates/partials/logs_grid.html`: same treatment on the runs table. The existing
  whole-row click-through to the run detail is preserved.
- `app/templates/partials/dashboard_body.html` and `logs_body.html`: wrap the filter/sort form in
  a disclosure that, below the breakpoint, collapses to a "Filters (N)" toggle button; above the
  breakpoint the form is always shown and the toggle is hidden. Alpine drives the toggle
  (consistent with the sidebar's Alpine collapse pattern); the active-filter count is computed
  server-side from the same filter view-model that already renders the fields.
- No change to filter/sort/pagination behaviour, HTMX swap targets, or the events/runs APIs.

**What stays out of the chrome package:** the filter-disclosure markup is Event-Creator-specific
(its filter fields, its view-model) and lives in Event Creator's templates, not chrome. Only the
table-card CSS + class constant are shared.

## Testing Decisions

A good test here asserts on what renders and how it behaves at a given viewport — not on CSS rule
text or Alpine internals.

**Seam 1 — `packages/chrome/tests/` (pytest, existing):** a unit test that the new wrapper-class
constant is exported from `organizeme_chrome.design.classes` and that `tokens.css` (resolved via
the package's static path helper) contains the `.om-stacked-table` rule — a cheap guard that the
pattern actually ships in the built package, mirroring however the existing design-token/class
constants are asserted.

**Seam 2 — `event-creator` `e2e/tests/dashboard.spec.ts` and `logs.spec.ts` (Playwright,
existing):** these already drive the deployed QA app with canned events via `E2E_TEST_MODE`. Add a
mobile-viewport project (`devices['Pixel 5']` or an explicit narrow viewport) to
`playwright.config.ts`, and per-page specs that at phone width assert: the table has no horizontal
overflow (card layout is active), a known field's `data-label` is visible next to its value, the
filter form is hidden until the "Filters" toggle is pressed, and the toggle shows the active
count when a filter is applied. Note: the e2e suite runs against deployed QA, so this validates
post-deploy — the pre-merge visual check is the screenshot audit below.

**Seam 3 — `event-creator` `tests/test_dashboard_page.py` / `tests/test_logs_page.py` (pytest,
existing):** assert the server-rendered markup includes the `.om-stacked-table` class on the
table and `data-label` on the cells, and that the filter disclosure wrapper + active-count render
with the expected value for a filtered vs unfiltered request. These are fast and run pre-deploy.

**Screenshot audit (design-time, not a CI test):** during `/to-design`, run Event Creator locally
at ~375px width and capture before/after of the Dashboard and Logs pages, attached to the TDD as
the visual record.

## Out of Scope

- Any screen other than the Dashboard and Logs — Processing, Run detail, Prompt, Upload, Settings,
  and Login are single-column / `max-w-*`-constrained already and render acceptably on mobile.
  Revisit if a specific one turns out broken.
- A native mobile app, PWA install, or offline support.
- Rolling `doc-library`, `ha-dashboard`, or the Host forward to the new chrome release, or
  applying the pattern to their tables.
- Redesigning the sidebar/nav drawer — it already works on mobile.
- A general responsive-layout audit of the chrome frame (headers, spacing, typography scale)
  beyond what the two target pages and their dialogs need.
- Changing which columns/fields are shown — the card shows every field the table shows.
- Touch-specific interactions (swipe actions, long-press menus).

## Further Notes

- This is a sibling to `sidebar-nav-groups` and `design-refresh` as a chrome-package feature:
  same pattern of "land it in `packages/chrome`, cut a tag, consumer bumps its pin", and the same
  Python-only / shipped-CSS constraints (`docs/adr/design-refresh-per-service-tailwind-build.md`,
  `docs/adr/design-refresh-shared-component-library.md`).
- The Tailwind-v4 CLI class-scanning bug (`event-creator#46`) is the direct reason the pattern is
  raw CSS in `tokens.css` rather than utility classes in a template — utilities only referenced
  from chrome's shipped templates have been dropped from consumers' builds before.
- `/to-design` should decide: the exact breakpoint mechanism (media query in `tokens.css` vs a
  container query), whether the dialog-width fix is shared or local, and the precise
  active-filter-count source. An ADR is warranted for "shipped CSS pattern vs Jinja dual-markup
  macro" if the trade-off feels live during design.
- WBS is likely: (1) chrome pattern + release, (2) Event Creator Dashboard adoption, (3) Event
  Creator Logs adoption + filter disclosure. Slices 2 and 3 depend on 1; 2 and 3 are independent
  of each other.
