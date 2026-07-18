# Shared component primitives live in `packages/chrome`, not just design tokens

**Status:** Proposed
**Date:** 2026-07-18
**Feature:** [`design-refresh`](../features/design-refresh/TDD.md)

## Context

Dropping DaisyUI means every button, card, input, and badge across all pages needs a replacement
implementation. `packages/chrome` already ships shared Jinja macros for nav (`nav_link`) and the
Settings tab-bar (`chrome_tabs.html`) — precedent exists for shared UI living centrally — but the
current generic "centered card" wrapper (`card_page()`) lives locally in `organize-me`'s own
`app/templates/macros/ui.html`, not in chrome, even though it's a generic-enough shape that
`event-creator`/`doc-library` would plausibly want the same pattern.

The question this feature has to settle: do the new hand-rolled component primitives (button, card,
input, badge) live centrally in `packages/chrome` for every hosted app to share, or does only the
token system (colors/type/spacing) live centrally, with each app building/owning its own component
implementations on top of those tokens?

## Decision

Both tokens **and** a small set of genuinely cross-app primitive components live in
`packages/chrome`, as Jinja macros over the new Tailwind classes — mirroring how `nav_link` already
prevents markup drift between call sites. `event-creator`'s and `doc-library`'s eventual adoption of
this design system (separate, later features) extends these primitives rather than re-deriving
their own.

App-specific *compositions* — organize-me's specific login/register/profile page layouts, the
landing hero — stay local to `organize-me`, built by calling chrome's primitives, not duplicated
into chrome themselves.

New subpackage in chrome: `organizeme_chrome/design/` alongside the existing flat modules
(`registry.py`, `nav_groups.py`, etc.), with a matching `templates/components/` directory alongside
the existing `templates/macros/`.

## Alternatives considered

- **Tokens-only in `packages/chrome`; each app builds its own component implementations.**
  Rejected — this is exactly the mistake `card_page()` already represents (a generic-enough pattern
  built locally instead of centrally), and it directly contradicts the PRD's own user story that a
  developer extending `event-creator`/`doc-library` later wants component patterns reusable, not
  just the palette. Repeating it across three apps risks three implementations drifting apart on
  spacing, focus states, and accessibility details that should be identical everywhere.

## Consequences

- `event-creator`/`doc-library` inherit a real dependency-and-versioning surface for UI components
  (not just nav/tabs as today), via the existing pin-and-bump discipline — more upfront coupling
  than tokens-only, but consistent with the trade-off the platform already made for shared chrome.
- A single fix (e.g. a focus-ring contrast issue) is made once in `packages/chrome` and propagates to
  every consumer on their next pin bump, rather than needing three separate fixes.
- `card_page()` itself is expected to be retired/replaced by the new chrome-provided card primitive
  as part of this feature, closing the precedent gap this ADR identifies.
