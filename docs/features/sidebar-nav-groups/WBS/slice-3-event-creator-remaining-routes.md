# Slice 3 — event-creator sync, remaining routes

> Part of the `sidebar-nav-groups` feature. PRD: [`../PRD.md`](../PRD.md) · Technical design:
> [`../TDD.md`](../TDD.md)

**Delivers:** Every remaining event-creator page (Logs, Processing, Prompt, Upload) renders its
sidebar groups using the current user's real, Host-stored `nav_collapsed_groups` preference,
matching Dashboard's behavior from Slice 2.

**Repo:** `event-creator` (separate from `organize-me`).

## What to build

Apply the pattern Slice 2 proved on the Dashboard route to the four remaining event-creator page
routes that render chrome: Logs, Processing, Prompt, and Upload. Each route stops hardcoding a
default nav-group state and instead fetches the current user's real `nav_collapsed_groups` via
`get_host_user()`, passing it through `build_nav_groups()` exactly as Dashboard does.

## Design notes

- Purely mechanical repetition of Slice 2's pattern across four more routes — no new design
  decisions. See [Slice 2](slice-2-event-creator-sync-pattern.md) for the pattern being applied.
- As with Slice 2, this does not touch `dark_mode`'s existing hardcoded-default gap in these same
  routes — explicitly out of scope, per [TDD Open Questions](../TDD.md#open-questions).

## Blocked by

- [Slice 2](slice-2-event-creator-sync-pattern.md) — the pattern must be proven on one route first.

## Acceptance criteria

- [ ] Logs, Processing, Prompt, and Upload routes each read real `nav_collapsed_groups` via
      `get_host_user()` instead of a hardcoded default.
- [ ] A user's group collapse state is consistent across all event-creator pages and organize-me
      pages alike.
- [ ] The current-page force-expand rule works correctly on each of these four routes (each route's
      own app group renders expanded when viewing that route, regardless of stored state).

## Testing

- Route-level tests for each of the four routes, mirroring the test added in Slice 2 for Dashboard.
- Manual verification: toggle a group in organize-me, confirm correct rendering across all four
  remaining event-creator pages.

<!-- /to-implementation appends a "## Delivered" section here once this slice ships. -->
