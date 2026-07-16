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
