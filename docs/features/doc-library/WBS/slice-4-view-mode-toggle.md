# Slice 4 — List/tiles view toggle, persisted

> Part of the `doc-library` feature. PRD: [`../PRD.md`](../PRD.md) · Technical design:
> [`../TDD.md`](../TDD.md)

**Delivers:** A user can switch `/doc-library` between list and tile layouts with an in-page
toggle, and their choice is remembered the next time they visit — from any device, since it's
stored server-side.

## What to build

- `user_preferences` table migration in the `doc_library` schema: `user_id` (UUID PK, FK
  `host.users.id`, `ON DELETE CASCADE`), `view_mode` (text/enum, `list` | `tiles`). No row exists
  until a user's first write (get-or-create), not created eagerly at registration.
- `ViewModePreference` schema and `PUT /api/v1/doc-links/preferences` JSON endpoint (full
  replace).
- `PUT /doc-library/fragments/view-mode` HTMX fragment route: toggles and persists `view_mode`,
  returns the grouped grid re-rendered in the new mode.
- Tile-view rendering for the grouped links (same grouping/ordering as list view — category then
  title — just a different layout per category group).
- `/doc-library` page reads the user's current `view_mode` (defaulting to `list` when no
  preference row exists yet) to decide initial rendering, with a toggle control wired to the
  fragment route above.

## Design notes

Implements the TDD's `user_preferences` schema and view-mode API/fragment design decisions. Get-
or-create logic mirrors `event_creator.user_settings`'s lazy-creation pattern (created on first
write, not at registration) referenced in the TDD and `host-integration-guide.md`'s Slice R2
interface contract.

## Blocked by

- Slice 3 (needs real `doc_links` data to render in both view modes — toggling an empty list isn't
  a meaningful test of the layout)

## Acceptance criteria

- [ ] A first-time visitor (no preference row yet) sees list view by default.
- [ ] Clicking the toggle switches the visible layout between list and tiles without a full page
      reload.
- [ ] The chosen view mode persists across a full logout/login cycle and across a fresh browser
      session (server-side, not localStorage/cookie-only).
- [ ] Tile view groups by category the same way list view does — same alphabetical ordering rules.
- [ ] Unauthenticated requests to the view-mode endpoints return 401.
- [ ] A user's view-mode preference is never visible to or settable by another user.

## Testing

HTTP-level, mirroring `event-creator`'s Settings-fragment tests
(`tests/test_settings_fragments.py`):

- `tests/test_preferences_api.py` — get-or-create path (no row yet → `list` default returned);
  persists and correctly reads back a changed value; 401 unauthenticated.
- `tests/test_doc_links_fragments.py` (extended from Slice 3) — view-mode toggle fragment route
  returns the correctly re-rendered partial for both modes.
- `tests/test_doc_library_page.py` (extended) — page reflects the persisted `view_mode` on load,
  including the never-set-yet default case.

<!-- /to-implementation appends a "## Delivered" section here once this slice ships. -->
