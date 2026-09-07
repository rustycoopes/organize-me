# The filter disclosure is a CSS checkbox-`peer` toggle inside the HTMX fragment

**Status:** Proposed
**Date:** 2026-09-07
**Feature:** [`mobile-responsive-tables`](../features/mobile-responsive-tables/TDD.md)

## Context

Below the breakpoint, the Dashboard and Logs filter/sort bars should collapse behind a
"Filters (N)" toggle so the data is what fills the first screen.

The complication: the filter `<form>` lives **inside** the HTMX swap target
(`#dashboard-body` / `#logs-body`). That fragment is re-rendered on every filter `change`, sort
toggle, and pagination click — by design, because the form's hidden `sort` field must re-render
with it (`dashboard_body.html`'s "must swap together" comment is load-bearing). So any toggle
state held *inside* the fragment — Alpine `x-data`, a checkbox — is destroyed and recreated on
every interaction.

Worse: `dashboard_body.html` has
`hx-trigger="keyup changed delay:500ms from:input[type='text']"` on the search box. On mobile,
a user opening Filters, tapping Search, and typing would get the panel collapsed out from under
them mid-keystroke (and the soft keyboard dismissed) 500ms after they pause.

The PRD's "Alpine, consistent with the sidebar" premise is also slightly wrong: the sidebar
*drawer* is a hidden-checkbox `peer` + `peer-checked:` CSS toggle, not Alpine; only the nav-group
collapse is Alpine, and that lives on `#sidebar-nav`, outside every swap target.

## Decision

- **The toggle is a hidden `<input type="checkbox">` + `peer` / `peer-checked:` CSS**, inside the
  fragment, wrapping the filter form. Zero JS, matches the sidebar drawer pattern already in the
  codebase. Above the breakpoint the form is always shown and the toggle is `lg:hidden`.
- **State resets to collapsed on every swap.** Accepted for select / date / status filters — each
  is a single tap, and seeing the filtered result (with the panel closed again) is fine.
- **The search input is moved off the auto-`keyup` swap path below the breakpoint.** Its
  `hx-trigger` becomes `search, change` (fires on blur / enter / native clear) rather than
  `keyup changed delay:500ms`. This removes the "panel collapses while I'm typing in it" failure
  and the mid-type keyboard dismissal. Desktop keeps the debounced keyup behaviour (media-query
  or a small `hx-trigger` swap is an implementation detail for `/to-design`'s successor).
- **`active_filter_count` ("N") is computed server-side** and re-rendered with the fragment on
  every swap, so it is always current even though the open/closed state is not persisted. It is a
  new explicit context value per page — **not** derived from the existing `has_active_filters`,
  which on the Dashboard folds in `event_types` (true whenever the user has any events) and would
  show a phantom count on an unfiltered page.
  - Dashboard: `sum(1 for f in (type, date_from, date_to, q, show_reviewed) if f)` — excludes
    `event_types`.
  - Logs: `sum(1 for f in (run_status, date_from, date_to) if f)`.
  - `show_reviewed=true` counts (a user who set it expects it counted); whitespace-only `q`
    counts (matches existing `_dashboard_url` behaviour).

## Alternatives considered

- **Hoist the disclosure wrapper outside `#dashboard-body`** (into the page template). State
  survives swaps. Rejected: splits the disclosure across two templates, and the "(N)" badge on
  the button would then be outside the swap and go stale — needing `hx-swap-oob` to keep it
  updated, which is more moving parts than the reset-on-swap behaviour is worth.
- **Alpine `x-data` + `$persist` (localStorage).** Rejected: the `$persist` plugin is not loaded
  (pages load htmx only; chrome base loads Alpine core), and persisting a filter panel's
  open state across page loads is not clearly desirable anyway.
- **Keep the search box on `keyup` and just let the panel collapse.** Rejected: actively broken
  UX on the exact device class this feature targets.
- **One shared helper for `active_filter_count` across both pages.** Rejected: 5 candidate fields
  vs 3, in two modules with two separate URL-builder helpers already; a shared helper would take
  the field tuple as an argument — no real DRY win for two call sites.

## Consequences

- No JS, no new dependency, no Alpine-scope-nesting question with the events table's existing
  large `x-data` (which is a sibling, not a parent, of the form).
- The panel is collapsed after every filter interaction on mobile. For multi-filter workflows
  that is a few extra taps; judged acceptable versus the complexity of persisting state across
  HTMX swaps.
- The search box on mobile updates results on blur/enter instead of live-as-you-type. Minor
  behaviour change, arguably better on a phone.
- Two small `active_filter_count` expressions to keep in sync when a filter field is added to
  either page — cheap, and co-located with the existing filter parsing.
- If a second app later needs the same disclosure, promote it to a chrome macro then — **trigger:
  the second consumer.** Until then it lives in `event-creator`'s templates.
