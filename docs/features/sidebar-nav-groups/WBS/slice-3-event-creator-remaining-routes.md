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

## Delivered (2026-07-16, event-creator#19, branch `feature/sidebar-nav-groups-slice2`, PR event-creator#20)

Folded into [Slice 2](slice-2-event-creator-sync-pattern.md)'s delivery rather than shipped as a
separate change: wiring Logs, Processing (both the progress and run-detail pages), Prompt, and
Upload turned out to be a **safety requirement** of Slice 2's own pin bump, not a follow-on — see
Slice 2's Delivered note for the full explanation (a missing nav context on any page extending the
shared sidebar template crashes it). All acceptance criteria below were met as part of that same
PR:

- All four routes (plus the Processing run-detail page, which this slice's original scope didn't
  explicitly enumerate but which extends the same template) read real `nav_collapsed_groups` via
  `get_host_user()` — no hardcoded default remains anywhere in the service.
- Group collapse state is consistent across every event-creator page and organize-me alike,
  manually verified live on QA.
- The current-page force-expand rule was verified working via the shared, already-tested
  `build_nav_groups()` pure function — no per-route logic to re-verify.

No new route-level tests were written per-route beyond one regression test per page (mirroring
Dashboard's), asserting the rendered `storedCollapsed` JSON reflects the real Host-stored value —
sufficient to catch the exact crash this expansion was fixing, without re-testing
`build_nav_groups()`'s own logic (already covered in `packages/chrome`).
