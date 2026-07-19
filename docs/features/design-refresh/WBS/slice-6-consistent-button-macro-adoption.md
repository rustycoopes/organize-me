# Slice 6 — Consistent button/input macro adoption

> Part of the `design-refresh` feature. PRD: [`../PRD.md`](../PRD.md) · Technical design:
> [`../TDD.md`](../TDD.md)

**Delivers:** Removes the hand-copied button/input markup left over from Slices 3–4 so every
button and text input in `organize-me` is rendered by the shared macro, not a local copy of its
class string — closing a silent-drift risk the contrast fix in
[slice-5](slice-5-component-contrast-hardening.md) would otherwise reopen the next time these
classes change.

## Source of this slice

Found during the same QA-driven investigation as slice-5: `app/templates/auth/login.html`,
`app/templates/auth/register.html`, and `app/templates/profile.html` all contain raw `<button>`
elements whose `class="..."` string is hand-assembled from the same Jinja globals the `button`
macro already composes internally (`FOCUS_RING`, `DENSITY_PADDING[...]`,
`BUTTON_VARIANT_CLASSES[...]`) — e.g. `login.html`'s submit button and Google sign-in link,
`profile.html`'s save/delete/cancel/confirm-delete buttons. `profile.html`'s three plain `<input>`
fields (name/email/phone) do the same thing with a locally-defined `field_input_classes` variable
instead of calling the `input` macro. This isn't cosmetic — slice-5's contrast fix only reaches
call sites that use the macro; every hand-rolled copy has to be independently remembered and
re-edited, which is exactly how the two literal DaisyUI class buttons in the original build were
missed for so long elsewhere in this codebase.

## What to build

- Extend the `button` macro (`templates/components/button.html`) to accept the handful of
  attributes these call sites actually need that it doesn't support today: an `x_bind_disabled`
  passthrough (Alpine `:disabled`), an `x_bind_class` passthrough (Alpine `:class` for the
  submitting/saving spinner-swap pattern), and an `attrs` free-form string escape hatch for
  one-off cases (`@click`, `id` on an `<a>`, etc.) rather than each page reinventing the class
  string because the macro couldn't flex to its need.
- Convert `login.html`'s submit button, `register.html`'s submit button, and `profile.html`'s
  save/cancel/delete/confirm-delete buttons to call the (now-extended) macro.
- Convert `profile.html`'s name/email/phone `<input>` fields to call the `input` macro,
  removing the local `field_input_classes` Jinja variable.
- Audit the rest of `organize-me`'s templates for any other hand-rolled button/input markup this
  pass missed (`grep -rn "BUTTON_VARIANT_CLASSES\[" app/templates`,
  `grep -rn "DENSITY_PADDING\['" app/templates` after this slice should return nothing outside
  `packages/chrome`'s own macros).

## Design notes

- No new architectural decisions — this is consolidation onto Slice 2's existing component
  boundary, driven by what real call sites needed and didn't have, not a redesign.

## Blocked by

- [slice-5](slice-5-component-contrast-hardening.md) — do this after the contrast fix lands so the
  macro's default output is already correct when these pages start calling it, rather than
  converting twice.

## Acceptance criteria

- [ ] Zero occurrences of `BUTTON_VARIANT_CLASSES[`/`DENSITY_PADDING[` (or equivalent hand-assembly
      of macro internals) in `app/templates/**` outside of pages that have a genuine, documented
      reason the macro can't yet express (none expected after this slice).
- [ ] `login.html`, `register.html`, `profile.html` render identically (visually and behaviorally —
      submitting state, disabled state, spinner-swap text) to before the conversion.
- [ ] No regression in `auth.spec.ts`, `profile.spec.ts`, or `account-deletion.spec.ts`.

## Testing

- Existing Playwright specs (`auth.spec.ts`, `profile.spec.ts`, `account-deletion.spec.ts`) stay
  the functional regression backstop — expected to pass unmodified, since behavior isn't changing.
- Extend `packages/chrome/tests/test_component_macros.py` for the macro's new
  `x_bind_disabled`/`x_bind_class`/`attrs` parameters.

<!-- /to-implementation appends a "## Delivered" section here once this slice ships. -->
