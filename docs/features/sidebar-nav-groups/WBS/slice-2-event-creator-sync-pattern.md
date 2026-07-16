# Slice 2 — event-creator sync, proof of pattern (one route)

> Part of the `sidebar-nav-groups` feature. PRD: [`../PRD.md`](../PRD.md) · Technical design:
> [`../TDD.md`](../TDD.md)

**Delivers:** One event-creator page (Dashboard) renders its sidebar groups using the current
user's real, Host-stored `nav_collapsed_groups` preference, instead of a default — proving the
cross-repo sync pattern end-to-end before it's repeated across the rest of event-creator's pages.

**Repo:** `event-creator` (separate from `organize-me`).

## What to build

Extend event-creator's read-only `HostUser` mapping to include `nav_collapsed_groups`, mirroring
how `dark_mode` is already mapped there. Bump event-creator's `packages/chrome` dependency pin to
the tag released in Slice 1. Wire the Dashboard page route to fetch the current user's real
`nav_collapsed_groups` via the existing `get_host_user()` helper and pass it through the same
`build_nav_groups()` function Slice 1 introduced, so Dashboard's sidebar reflects true per-user
group state — collapsed groups stay collapsed, the current page's own group force-expands, exactly
as it behaves in organize-me.

## Design notes

- No new cross-service HTTP call: this reads the same shared Postgres instance event-creator
  already reads `dark_mode` from — see
  [ADR: cross-repo sync](../../adr/sidebar-nav-groups-cross-repo-sync.md).
- Investigation during design found `dark_mode` itself is mapped on `HostUser` but never actually
  read by any event-creator route (hardcoded `dark_mode: False` instead, per an existing code
  comment deferring that sync). This slice does **not** fix that — it only wires
  `nav_collapsed_groups`, establishing the pattern fresh rather than retrofitting `dark_mode`.
- Uses the same `build_nav_groups()` pure function from `packages/chrome` that Slice 1 added — no
  new grouping logic, just a new caller.

## Blocked by

- [Slice 1](slice-1-host-sidebar-groups.md) — needs the `packages/chrome` tag it releases, and the
  `nav_collapsed_groups` column/endpoint to exist on the Host.

## Acceptance criteria

- [ ] `HostUser` maps `nav_collapsed_groups` (read-only) from `host.users`.
- [ ] event-creator's `pyproject.toml` pin for `organizeme-chrome` is bumped to the new tag from
      Slice 1.
- [ ] The Dashboard route no longer hardcodes a default for nav group state; it reads the real
      value via `get_host_user()`.
- [ ] A user who has collapsed the Event Creator group in organize-me sees it collapsed on the
      Dashboard page too (except where the current-page force-expand rule applies).
- [ ] Toggling a group from within event-creator's Dashboard page is out of scope for this slice —
      only correct *rendering* of the Host-stored state is required here (event-creator has no
      write path to `PATCH /api/v1/users/me`; toggling still happens from organize-me pages).

## Testing

- Route-level test confirming the Dashboard route reads `nav_collapsed_groups` from
  `HostUser`/`get_host_user()` and passes it through correctly — not hardcoded — establishing the
  pattern to replicate in Slice 3.
- Manual verification: toggle a group in organize-me, confirm it renders correctly on the
  event-creator Dashboard page without a page-specific override.

<!-- /to-implementation appends a "## Delivered" section here once this slice ships. -->

## Delivered (2026-07-16, event-creator#18, branch `feature/sidebar-nav-groups-slice2`, PR event-creator#20)

Shipped as designed, with a scope expansion discovered during code review: bumping
event-creator's `organizeme-chrome` pin to `chrome-v0.5.4` changed the shared
`chrome_authenticated_base.html` template to require `nav_groups`/`flat_nav_items`/
`nav_collapsed_json`/`nav_stored_collapsed_json` in context on **every** page extending it — not
just Dashboard. Every page route in event-creator extends that template (Dashboard, Logs,
Processing, Processing run detail, Prompt, Upload), so a missing key crashes the `tojson` filter
(`TypeError: Object of type Undefined is not JSON serializable`, confirmed empirically). Shipping
the pin bump safely required wiring all of them in this same change, which incidentally completed
[Slice 3](slice-3-event-creator-remaining-routes.md) (event-creator#19) as the same delivery — see
that slice's own Delivered note.

Also found and fixed during review: two pre-existing `test_settings_fragments.py` assertions
expected raw, unescaped quotes in rendered JSON — the pin bump's `tojson` filter now HTML-entity-
escapes quotes universally (the fix from [Slice 1](slice-1-host-sidebar-groups.md)'s `x-data`
bug applies to every `| tojson` use in the shared package, not just the sidebar). Updated to
expect the escaped form, verified empirically against the actual filter rather than by inspection.

`get_dark_mode()` (in `app/services/host_user.py`) became dead code once every route was
refactored to a single `get_host_user()` fetch (covering both `dark_mode` and
`nav_collapsed_groups`) — removed it and its dedicated tests rather than leaving it unused.

CI: one round of failures (2 pre-existing test assertions broken by the escaping change, caught
by CI rather than locally — no DB credentials in the implementation sandbox), fixed and re-pushed
to fully green (unit tests, `deploy-qa`, `e2e-boundary-qa`, `e2e-qa` all passed). Manually verified
live on QA via browser automation: registered an account, collapsed the Event Creator group from
organize-me's own Settings page, confirmed the Host-stored preference round-tripped correctly to
event-creator's `/dashboard` (`storedCollapsed: {"event-creator": true}` while displayed expanded
due to the current-page force-open rule), confirmed toggling the group *from* event-creator's own
page correctly PATCHed back to the Host (no write-side wiring needed — the shared Load Balancer
routes `/api/v1/users/me` to the Host regardless of which service rendered the page), and
confirmed `/logs` — one of the routes that would have 500'd without the scope expansion — renders
correctly.

Merged to `main`, deployed to prod, `test` + `deploy-prod` jobs both green.
