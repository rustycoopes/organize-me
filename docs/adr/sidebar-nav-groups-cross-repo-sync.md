# Ship nav-group sync to event-creator in this pass, via a bumped chrome tag

**Status:** Proposed
**Date:** 2026-07-16
**Feature:** [`sidebar-nav-groups`](../features/sidebar-nav-groups/TDD.md)

## Context

`packages/chrome` (this repo) is consumed by `event-creator`, a separately deployed service, via a
git-ref-pinned dependency in its `pyproject.toml`
(`organizeme-chrome @ git+...@chrome-v0.4.0#subdirectory=packages/chrome`) — not a live/local path
dependency. Changes to `packages/chrome`'s templates or rendering logic do not reach event-creator
until that pin is bumped to a newer tag and reinstalled.

Separately, `User.nav_collapsed_groups` (this feature's new per-user preference) lives in the
Host's database. event-creator reads other Host-owned per-user fields today via a read-only
cross-schema `HostUser` SQLAlchemy mapping (`event-creator/app/models/host_user.py`) — but
investigation during design found this pattern is *not* actually wired end-to-end for its existing
`dark_mode` field: `HostUser` maps the column, but every event-creator page route that renders
chrome hardcodes `dark_mode: False` in template context instead of reading it, per an explicit
code comment deferring that sync as out of scope for an earlier slice. There is no proven,
working, per-route preference-sync pattern to simply "reuse" for this feature.

This left three options for how to handle event-creator for this feature.

## Decision

Do the full cross-repo wiring in this same implementation pass:

1. Add `nav_collapsed_groups` to event-creator's `HostUser` mapping (read-only, mirroring how
   `dark_mode` is already mapped there).
2. Wire every event-creator page route that currently renders chrome to actually read
   `nav_collapsed_groups` from `get_host_user()` and pass it through `build_nav_groups()` (see
   [`sidebar-nav-groups-render-boundary`](sidebar-nav-groups-render-boundary.md)) — not hardcode a
   default.
3. Cut a new `packages/chrome` git tag (next after `chrome-v0.4.0`) once the grouping changes land
   in this repo, and bump event-creator's `pyproject.toml` pin to it, in the same slice as steps 1
   and 2 — not left pointing at the old tag.

## Alternatives considered

- **Defer event-creator entirely; ship Host-only for v1**, leaving event-creator's sidebar groups
  always-expanded and unpersisted until a follow-up feature. This was the default/lower-effort
  path and was explicitly offered to the user as an option. Rejected in favor of doing it now: it
  would recreate the exact same class of silent gap that `dark_mode` already has in event-creator
  (a Host preference that's mapped but never actually read), and the user chose to close that gap
  immediately rather than defer it a second time.
- **Switch event-creator's `organizeme-chrome` dependency from a pinned tag to a floating branch
  ref** (e.g. tracking `main`), so future `packages/chrome` changes reach it automatically.
  Rejected: this trades away deployment reproducibility (event-creator's build would no longer be
  pinned to a known-good chrome version) for convenience on this one feature; the tag-pin
  mechanism is an existing, deliberate convention this feature should follow, not undermine.
- **Vendor/copy the relevant template and rendering logic directly into event-creator**, avoiding
  the shared-package version-bump step altogether. Rejected: duplicates code the shared-package
  pattern exists specifically to avoid duplicating, and would immediately desync from any future
  `packages/chrome` change.

## Consequences

- This feature's implementation work spans two repos and must be sequenced: the
  `packages/chrome` change and its new tag must exist before event-creator's dependency bump can
  target it.
- Fixes, as a side effect, the "gap-vs-`dark_mode`" pattern for this one field, but does **not**
  retroactively fix `dark_mode`'s own hardcoded-default gap in event-creator — that stays out of
  scope per the PRD, to avoid scope creep into unrelated existing behavior.
- Establishes a real, working, per-route Host-preference-sync pattern in event-creator for the
  first time — future per-user preferences added to the Host can follow this same wiring instead
  of each starting from scratch.
