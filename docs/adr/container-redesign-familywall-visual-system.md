# Primary brand color and danger color are split into separate tokens

**Status:** Accepted
**Date:** 2026-07-24
**Feature:** N/A — visual redesign via the `impeccable` design skill; see `DESIGN.md`

## Context

The prior "Signal" design system used `flame` (a red-orange) as both the primary brand/CTA color
*and* the sole danger color — one token serving two conflicting semantic roles. That was a
reasonable choice at the time (fewer tokens, one accent to reason about), but it means every
primary call-to-action (register, save, submit) rendered in the same color as every destructive
action (delete account, delete event).

This redesign anchors OrganizeMe's visual language on FamilyWall (a family-organization app the
user selected from a five-site competitor scan), whose brand color is a friendly blue. Adopting a
blue primary makes the primary/danger conflation impossible to preserve silently — a decision had
to be made explicitly.

## Decision

Split the dual-role token into two single-role tokens:

- `cobalt` (blue) becomes the **brand primary** — primary buttons, links, active nav/tab state,
  the focus ring, and "info" status. It was previously the secondary/info-only color.
- `flame` (red, recolored slightly warmer) becomes **danger-only** — destructive buttons, error
  alerts, form validation errors, and "danger" status. It no longer appears on any non-destructive
  primary action.
- A new `amber` token is introduced as the secondary accent (secondary buttons, secondary badges,
  warm highlight moments), replacing `cobalt`'s old role as the "second" brand color now that
  `cobalt` is primary.

## Alternatives considered

- **Keep `flame` as primary, recolor it away from red.** Rejected — a primary-brand token that
  also drives every danger surface (`danger`/`danger-solid` button variants, error alerts, input
  error borders) must stay legibly "alarming" red; recoloring it toward blue/warm would have
  broken every destructive-action affordance in the product to chase the FamilyWall reference,
  which is exactly backwards.
- **Introduce a brand-new token pair and leave `flame`/`cobalt` as unused legacy names.** Rejected
  — `flame` and `cobalt` are deeply embedded (component macros, `classes.py`'s documented dark-mode
  contrast fixes, existing tests); renaming the tokens themselves would touch every call site for
  no semantic gain over reassigning their *roles* and recoloring their hex values in place.

## Consequences

- Every component that read `flame` as an implicit "primary-or-danger" signal (toggle's `checked`
  state, active nav/tab state, the settings-tab loading spinner) needed an explicit review — each
  was in fact using it for a non-danger "primary/active" meaning and is corrected to `cobalt` as
  part of this change, not left silently wrong.
- Tests in `packages/chrome/tests/test_component_macros.py` that asserted the old
  `bg-flame`-as-primary/`bg-cobalt`-as-secondary mapping are updated to assert the new mapping —
  an intentional, reviewed test change, not drift.
- Hosted apps (Event Creator, Doc Library, HA Dashboard) that call these same shared components
  inherit the corrected semantics automatically once each repo bumps its `organizeme-chrome` pin;
  no cross-repo migration is required beyond that pin bump.
