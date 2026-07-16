## Problem Statement

The left-hand sidebar in Organize Me's shared chrome renders every app's navigation items as one
flat, merged list (`packages/chrome/src/organizeme_chrome/templating.py`, `nav_items`). As more
apps are registered (currently `event-creator` and `organizeme`), it becomes harder to tell which
nav item belongs to which app, and there is no way to visually de-emphasize an app the user isn't
currently working in. A user who wants to focus on a single app (e.g. Event Creator) has no way to
hide the other apps' menu items and reduce visual clutter.

## Solution

Group the sidebar's nav items by the app that owns them, using the existing `APPS` registry
(`packages/chrome/src/organizeme_chrome/registry.py`) as the source of truth. Each app renders as
a named, collapsible group header with its own nav items nested underneath. Users can
independently expand or collapse any group; the choice is remembered per user across sessions.
Settings and Profile remain permanent, always-visible flat items at the bottom of the sidebar,
outside any app group, since they are account-level rather than app-scoped.

## User Stories

1. As an Organize Me user, I want each app's nav items grouped under that app's name, so that I can tell at a glance which menu items belong to which app.
2. As an Organize Me user, I want to collapse an app's group, so that I can hide menu items for apps I'm not currently using.
3. As an Organize Me user, I want to expand a collapsed app's group again, so that I can access its pages when I need them.
4. As an Organize Me user, I want to collapse and expand app groups independently of one another, so that I can have any combination of groups open or closed at once (not forced into an accordion).
5. As an Organize Me user, I want my collapsed/expanded choices remembered across sessions, so that I don't have to re-collapse the same apps every time I log in.
6. As a first-time Organize Me user, I want all app groups expanded by default, so that I can discover every app's pages without having to know to expand anything.
7. As an Organize Me user, I want Settings and Profile to always stay visible at the bottom of the sidebar, so that I can reach account-level pages regardless of which app groups are collapsed.
8. As an Organize Me user, I want clicking a group header to only toggle that group (not navigate anywhere), so that expanding/collapsing an app's menu is predictable and doesn't accidentally take me to a page.
9. As an Organize Me user, I want the toggle to feel instant, so that expanding/collapsing doesn't wait on a network round-trip.
10. As an Organize Me user, I want my collapse choice to be saved automatically in the background, so that I don't have to take a separate "save" action.
11. As an Organize Me user who navigates directly into a page inside a collapsed app group (e.g. via a bookmark or the browser back button), I want that group to show as expanded so I can see where I am and reach sibling pages, so that I'm never stranded looking at a page with no visible nav for it.
12. As an Organize Me user, I want navigating into a collapsed group to not overwrite my saved preference, so that the group collapses again the next time I navigate away, exactly as I left it.
13. As an Organize Me user relying on a screen reader or keyboard-only navigation, I want the group toggles to be operable via keyboard and to announce their expanded/collapsed state, so that I can use the sidebar without a mouse.
14. As an Organize Me user viewing an app with only one nav item, I want it to still render as a named, collapsible group like every other app, so that the sidebar's visual pattern stays consistent regardless of how many pages an app currently has.
15. As an Organize Me developer adding a new app to the `APPS` registry, I want its nav items to automatically render as a new collapsible group, so that I don't need extra chrome-package work per new app.
16. As an Organize Me user, I want app groups to appear in the same order the apps are registered in, so that the sidebar layout stays predictable and unsurprising.

## Implementation Decisions

- **Registry stays the source of truth.** `packages/chrome/src/organizeme_chrome/registry.py`'s
  `AppEntry`/`AppNavItem`/`APPS` list is unchanged in shape. No new fields are added to the
  registry for this feature.
- **Grouping happens at render time, not merge time.** Today `register_chrome()` in
  `packages/chrome/src/organizeme_chrome/templating.py` flattens every app's `nav` into one merged
  `nav_items` list (losing which app owns each item). This changes to expose a grouped structure —
  a per-app object carrying `service_name`, a display label, and its `nav` items — so the template
  can render one collapsible section per app in registry-definition order.
- **Settings/Profile stay carved out.** They remain the `organizeme` app's existing flat nav
  entries in the registry (`registry.py` lines ~106-109) but are rendered separately from the
  grouped-by-app sections, pinned at the bottom of the sidebar, never collapsible.
- **Persisted state shape.** A new column is added to `User`
  (`app/models/user.py`, alongside `dark_mode`): a JSON-typed mapping from app `service_name` to a
  collapsed boolean, e.g. `nav_collapsed_groups: Mapped[dict[str, bool]]` backed by a `JSON` column
  with `default=dict, server_default="{}"`. An app with no entry in the dict is treated as expanded
  (the default). This is a new pattern for this repo (no existing `Mapped[dict]`/JSON ORM column in
  `app/models`), added via an Alembic migration following this repo's `add_*` naming convention
  (`op.add_column('users', ..., schema='host')`, matching `User.__table_args__`).
- **API contract.** No new endpoint. The existing `PATCH /api/v1/users/me`
  (`app/api/v1/users.py`) and its `UserUpdate`/`UserRead` schemas (`app/schemas/user.py`) gain a
  new optional field, `nav_collapsed_groups: dict[str, bool] | None`, following the same
  partial-update (`exclude_unset=True`) semantics already used for `dark_mode`. Client sends the
  full updated dict (not a single key delta) on every toggle.
- **Client-side interaction.** Alpine.js drives instant, optimistic UI: clicking a group's toggle
  button immediately flips that group's `x-show`/`aria-expanded` state client-side, and fires a
  background call to `PATCH /api/v1/users/me` with the updated `nav_collapsed_groups` dict. No
  page reload, no blocking on the network response.
- **Initial render reflects server state.** On full page load, the server renders each group's
  initial expanded/collapsed HTML state directly from the current user's
  `nav_collapsed_groups`, so there's no flash of the wrong state before Alpine hydrates.
- **Current-page override.** If the page currently being rendered belongs to an app whose group is
  marked collapsed in `nav_collapsed_groups`, the server still renders that specific group as
  expanded for this page load only — it does not write back to `nav_collapsed_groups`. Every other
  group renders according to the stored preference as normal.
- **Group header markup.** Each group header is a semantic `<button>` (not a link or a `<div>`
  with a click handler) carrying `aria-expanded`, toggling visibility of its own `<ul>` of nav
  items. It performs no navigation. A chevron/caret icon rotates to reflect state, purely
  presentational (design details deferred to `/to-design`).
- **Single-item apps still group.** Every `AppEntry` renders its own named, collapsible group
  regardless of how many `AppNavItem`s it has — no special-casing for apps with only one nav item.
- **Group ordering.** Groups render in the same order as `list_apps()` / the `APPS` list — no
  alphabetical or user-customizable sort.
- **No accordion behavior.** Expanding one group never collapses another; each group's state is
  fully independent.
- **Out-of-scope UI controls excluded now**: no bulk "collapse all"/"expand all" control (see Out
  of Scope).

## Testing Decisions

- **Persistence (integration test)**: extend `tests/test_users.py`'s existing pattern
  (`test_patch_dark_mode_persists`, `test_patch_partial_update_leaves_other_fields_unchanged`,
  `test_patch_rejects_missing_cookie`) with equivalent cases for `nav_collapsed_groups`: patching
  it persists and round-trips via `GET`/`PATCH /api/v1/users/me`; patching one field doesn't
  disturb the other; auth is required. These are `httpx.AsyncClient`-driven integration tests
  against the real ASGI app with a rolled-back DB transaction per test
  (`tests/conftest.py`), same as existing `dark_mode` coverage. Only external behavior (request in,
  persisted/returned state out) is tested — no reaching into ORM internals.
- **Rendering (template test)**: following the pattern in `tests/test_profile_page.py`, add
  assertions that the rendered sidebar HTML (a) groups nav items under the correct app labels in
  registry order, (b) marks a group's container with the correct expanded/collapsed
  state/`aria-expanded` value based on the current user's `nav_collapsed_groups`, (c) always
  renders Settings/Profile outside any group, and (d) force-expands the current page's own group
  even when stored as collapsed, without mutating the stored preference. These test rendered
  output (HTML structure/attributes), not internal Python helper functions.
- **No new test infra needed.** No new fixtures, mocks, or test framework changes — reuses the
  existing `client`/`db_session` fixtures.

## Out of Scope

- Bulk "collapse all" / "expand all" control.
- User-customizable group ordering (drag-and-drop or otherwise) — registry order only.
- Accordion-style mutual exclusion between groups.
- Any change to which apps/pages exist, or to the `APPS` registry's schema/fields.
- Mobile/responsive drawer redesign beyond making the existing collapsible groups work within the
  current DaisyUI drawer — no new mobile-specific interaction pattern.
- localStorage or any client-only persistence mechanism — all state is server-persisted per user.
- Visual design specifics (icon choice, spacing, animation timing/easing) — deferred to
  `/to-design`.

## Further Notes

- This is the first `Mapped[dict]`/JSON-typed column in `app/models` for this repo; the Alembic
  migration and SQLAlchemy column definition should be reviewed carefully as a new pattern, even
  though the feature itself is otherwise low-risk and purely additive.
- `packages/chrome` is consumed by every hosted app (not just `organizeme`), so template and
  `templating.py` changes affect chrome rendering across all apps uniformly — there is only one
  shared sidebar implementation to change, not one per app.
