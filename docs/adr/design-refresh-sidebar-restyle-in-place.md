# Restyle the sidebar's existing DOM structure in place, don't restructure it

**Status:** Proposed
**Date:** 2026-07-18
**Feature:** [`design-refresh`](../features/design-refresh/TDD.md)

## Context

`chrome_authenticated_base.html` and `macros/chrome_nav.html` currently use DaisyUI's
`drawer`/`drawer-toggle`/`drawer-content`/`drawer-side`/`menu`/`btn`/`navbar` classes throughout for
the sidebar/header layout. This same markup was very recently extended by the `sidebar-nav-groups`
feature (collapsible per-app nav groups), which is already partially implemented: its Alpine.js
`x-data`/toggle logic and its own test suite are keyed to specific structural details in this exact
markup (`aria-expanded` state, specific element IDs like `sidebar-nav`, `nav-group-{service_name}`,
`sidebar-drawer-toggle`, `sidebar-logout-button`, and the displayed-vs-stored collapsed-state split
that feature's changelog records as having already needed a real bug fix once).

A second in-flight feature, `registry-decoupling`, also touches `packages/chrome`, though its scope
is registry *data* fetching/caching, not template markup.

This design-refresh feature has to restyle this same sidebar to the new visual system. The open
question is whether that's purely a class swap on the existing DOM, or whether the redesign should
also restructure the markup itself while already in this file.

## Decision

Restyle in place: swap DaisyUI classes for the new component classes, keep the existing DOM
structure, element IDs, and Alpine.js wiring exactly as `sidebar-nav-groups` left them. Before
merging this feature's sidebar work, verify (via a rebase/diff check, not a design change) that
`registry-decoupling` hasn't landed conflicting markup changes to the same files in parallel — its
PRD scope suggests it's data-only, but branch timing could still collide on the same files.

## Alternatives considered

- **Restructure the sidebar DOM while restyling it**, on the theory that a from-scratch visual
  system might want a cleaner structure than what DaisyUI's component classes encouraged. Rejected:
  there's no visual requirement in the PRD that actually needs a structural change — the new look is
  achievable via classes alone — and restructuring risks re-breaking the exact bug class
  `sidebar-nav-groups` already found and fixed once (the collapsed-state display-vs-stored split,
  the `tojson`-escaping issue), since that feature's tests are asserting against today's specific
  structure. The cost (real regression risk on a feature that just landed) clearly outweighs the
  benefit (marginally cleaner markup with no user-visible difference).

## Consequences

- Sidebar restyling for this feature is lower-risk and faster than a structural rewrite would be —
  it's a class-substitution pass validated against `sidebar-nav-groups`' existing test suite, not a
  new structural implementation.
- The sidebar's underlying markup carries forward whatever DaisyUI-era structural choices
  `sidebar-nav-groups` built on, even though the visual system around it is now bespoke. A future
  feature is free to revisit the DOM structure on its own, once not competing with two other
  concurrently in-flight features touching the same file.
