# Slice 1 — Grouped, collapsible sidebar in organize-me (Host)

> Part of the `sidebar-nav-groups` feature. PRD: [`../PRD.md`](../PRD.md) · Technical design:
> [`../TDD.md`](../TDD.md)

**Delivers:** Organize Me users see the left-hand sidebar grouped by app, with each app's group
independently collapsible/expandable, remembered per user across sessions.

## What to build

Replace the sidebar's current flat, merged nav list with per-app collapsible groups, rendered from
the existing `APPS` registry. Each app renders as a named group with a toggle control; clicking it
instantly shows/hides that group's nav items client-side and persists the new state in the
background, with no page reload. A user's group states are stored server-side and reflected
correctly on the next full page load (no flash of the wrong state). Settings and Profile remain
permanent, always-visible flat items at the bottom of the sidebar, outside any group. If the page
currently being viewed belongs to a group the user has stored as collapsed, that group renders
expanded for this page load only, without overwriting the stored preference. New users (no stored
preference yet) see every group expanded by default. Every group is keyboard-operable and exposes
its expanded/collapsed state to assistive tech.

## Design notes

- Combine logic (registry + stored preference + current path → per-group render state) is a pure
  function added to `packages/chrome`, called per-request from organize-me's own route/template
  layer — see [TDD §1](../TDD.md#1-render-state-boundary) and
  [ADR: render boundary](../../adr/sidebar-nav-groups-render-boundary.md).
- Persistence: new `User.nav_collapsed_groups` JSON column (default `{}`), `PATCH /api/v1/users/me`
  extended with the same field, full-dict-replace-on-write semantics, explicit-null rejected — see
  [TDD §2-4](../TDD.md#2-persistence-shape).
- Group display labels are humanized from `service_name` inside `packages/chrome`, not a new
  registry field.
- This slice's `packages/chrome` changes must be tagged as a new git release once merged — Slice 2
  depends on that tag existing (see [ADR: cross-repo sync](../../adr/sidebar-nav-groups-cross-repo-sync.md)).

## Blocked by

None — can start immediately.

## Acceptance criteria

- [ ] Sidebar renders one named, collapsible group per registered app, in registry-definition
      order, even for apps with only one nav item.
- [ ] Settings and Profile always render flat, outside any group, regardless of any group's state.
- [ ] Clicking a group's toggle instantly shows/hides its nav items client-side, with no page
      reload and no navigation side-effect.
- [ ] Toggling a group persists the new state to the database in the background (verified via
      `PATCH /api/v1/users/me`), without blocking the UI toggle.
- [ ] A user with no stored preference sees all groups expanded on first load.
- [ ] Reloading the page reflects the previously toggled state correctly on first paint (no flash
      of the wrong state).
- [ ] Navigating directly into a page inside a group the user has stored as collapsed renders that
      group expanded for that page load, without changing the stored preference (verified by
      reloading a different page afterward and seeing the group collapsed again).
- [ ] Group toggle controls are real `<button>` elements with correct `aria-expanded`, operable via
      keyboard (Enter/Space).
- [ ] `PATCH /api/v1/users/me` rejects an explicit `null` for `nav_collapsed_groups` with a 422,
      matching `dark_mode`'s existing behavior.
- [ ] A second `PATCH` with a different `nav_collapsed_groups` dict fully replaces the stored value
      rather than merging with the previous one.

## Testing

- Unit tests for `build_nav_groups()` in `packages/chrome` as a pure function (plain dict/list
  input, no `Request`/DB fixtures) — see [TDD Testing Approach](../TDD.md#testing-approach).
- API integration tests in `tests/test_users.py`, extending the existing `dark_mode` coverage
  pattern (`test_patch_dark_mode_persists`,
  `test_patch_partial_update_leaves_other_fields_unchanged`,
  `test_patch_with_explicit_null_dark_mode_returns_422`) with equivalent `nav_collapsed_groups`
  cases plus the full-replace-not-merge case, using the existing `httpx.AsyncClient` +
  rolled-back-DB fixtures (`tests/conftest.py`).
- Template-rendering test (extending `tests/test_profile_page.py`'s pattern, or a new
  `tests/test_sidebar_nav_groups.py`) asserting grouped HTML structure, `aria-expanded` values, the
  current-page force-expand override, and Settings/Profile always rendering outside any group.

<!-- /to-implementation appends a "## Delivered" section here once this slice ships. -->

## Delivered (2026-07-16, issue #212, branch `feature/sidebar-nav-groups`)

Shipped as designed, with two corrections found during code review (not in the original design):

- The `tojson` Jinja filter's HTML-escape table (borrowed from Flask's `htmlsafe_json_dumps`
  convention) omitted `"`, which broke the double-quoted `x-data` HTML attribute it's embedded in
  on every render with a non-empty collapsed map. Fixed by escaping `"` too.
- The original design sent the *displayed* collapsed map (including the current-page force-open
  override) back in the toggle's PATCH body. That could silently persist a temporary force-open
  override for an untouched, unrelated group as its new "real" stored preference. Fixed by
  splitting displayed state (`nav_collapsed_json`) from the user's real stored preference
  (`nav_stored_collapsed_json`) in `app/core/nav.py`'s `sidebar_nav_context()` — the toggle now
  mutates and PATCHes only the latter.

`packages/chrome` was tagged three times during implementation (`chrome-v0.5.0` → `0.5.1` fixing
the two bugs above → `0.5.2` for code-quality cleanup: duplicated nav-link markup extracted into a
`nav_link` Jinja macro, `NavGroup` construction switched to keyword args, a lockfile re-lock, and a
comment documenting why `service_name` is safe to interpolate unescaped into Alpine JS string
literals). The Host's own `organizeme-chrome` pin ended on `chrome-v0.5.2`.

Everything in the original "What to build" and acceptance criteria shipped as specified — no scope
changes. `packages/chrome`'s own test suite (23 existing + 9 new `build_nav_groups`/`flat_nav_items`
tests) and `mypy --strict` on both `packages/chrome` and the Host `app/` were run and pass. The
DB-backed integration suite (`tests/test_users.py`, `tests/test_sidebar.py`) could not be run
locally (no DB credentials in the implementation sandbox) — verified via CI on the PR instead, per
explicit direction from the issue owner.
