# Dark mode stays DB-driven via an explicit `.dark` class, not Tailwind v4's default OS-preference variant

**Status:** Proposed
**Date:** 2026-07-18
**Feature:** [`design-refresh`](../features/design-refresh/TDD.md)

## Context

Dark mode is an existing, shipped product capability: `User.dark_mode` is a persisted preference,
set explicitly by the user in Profile, and `theme_attr(dark_mode)` today selects between DaisyUI's
`corporate`/`dark` theme presets via an HTML `data-theme` attribute DaisyUI itself interprets.

Dropping DaisyUI removes that mechanism entirely — plain Tailwind v4 has no `data-theme` concept.
Tailwind v4's own default dark-mode variant (`dark:*` utilities) is driven by the browser's
`prefers-color-scheme` media query, not by any HTML attribute or class, unless explicitly
reconfigured. Left at the default, the redesign would silently regress dark mode from "the user's
explicit, persisted choice" to "whatever the OS reports" — a real behavior change, easy to miss
since both look like "dark mode working" in casual testing on a dark-OS machine.

## Decision

Reconfigure Tailwind v4's dark variant to be class-based instead of media-query-based, via
`@custom-variant dark (&:where(.dark, .dark *));` in the tokens CSS entry file. The server renders
`class="dark"` (or omits it) on `<html>` based on `theme_attr(dark_mode)`, which shrinks to:

```python
def theme_attr(dark_mode: bool) -> Literal["dark", ""]:
    return "dark" if dark_mode else ""
```

Python (`User.dark_mode`, read at request time) stays the single source of truth for *which* mode is
active, exactly as today; CSS stays the source of truth for *what each mode looks like*. This
preserves the existing DB-driven, explicit-toggle behavior exactly — only the mechanism connecting
the two changes.

## Alternatives considered

- **Accept Tailwind v4's default OS-preference-driven dark mode, drop the explicit toggle.**
  Rejected outright — this is a real product regression (removes user control, contradicts the
  PRD's own requirement that dark mode "must be preserved and carry the same design intent," not
  reworked), not a neutral implementation simplification.
- **Keep a `data-theme` attribute (rather than a `.dark` class) and write custom CSS selectors
  keyed off `[data-theme="dark"]` instead of adopting Tailwind's own `dark:` variant convention.**
  Rejected — this would work, but throws away Tailwind v4's built-in dark-variant utilities
  (`dark:bg-...`, etc.) for no benefit, forcing every component to hand-write theme-conditional CSS
  instead of using the utility classes the rest of the system relies on. The `@custom-variant`
  reconfiguration gets both a class-based (not media-query) trigger *and* keeps `dark:` utilities
  working normally.

## Consequences

- Every component's dark-mode styling is expressed with ordinary `dark:` utility classes, same
  authoring pattern as light-mode styling — no parallel theme-conditional CSS system to maintain.
- This is an easy detail to lose track of during implementation (it's a one-line config change with
  an easy-to-miss silent failure mode: forgetting it doesn't break the build, it just makes dark
  mode stop respecting the user's actual preference). Flagged explicitly here and in `TDD.md`'s
  Testing Approach so a test asserts the class-based behavior, not just that *some* dark styling
  exists.
