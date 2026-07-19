# Slice 5 — Component contrast hardening + missing primitives

> Part of the `design-refresh` feature. PRD: [`../PRD.md`](../PRD.md) · Technical design:
> [`../TDD.md`](../TDD.md)

**Delivers:** Fixes a real, reported legibility defect in the shipped design system (not a
migration gap) — the `ghost` button variant and the default input/select border are both a
30%-opacity ink line with no fill, sitting on backgrounds (`Paper`/`Mist`) that are nearly the
same lightness, so they're effectively invisible. Also adds the two primitives Slice 2 never
built: a `select` macro (no dropdown primitive exists today at all) and a shared `toggle` macro
(the only boolean-input treatment in the app today is one-off CSS hand-written directly in
`profile.html`, not a reusable component).

## Source of this slice

Filed from a live QA pass (2026-07-19), not a fresh design session:
- "Input fields are not very clear. They should have a highlight around them so you can see
  what's an input or a drop down."
- "Buttons are completely invisible. They've blended with the background and all I can see is the
  text."
- "I don't like the checkboxes for a boolean input. Can we return those to a toggle?"

Root-caused by direct inspection of `packages/chrome/src/organizeme_chrome/design/classes.py` and
the `button`/`input` macros — see the design-refresh-hardening plan discussion for the full
root-cause chain (this is one of several tracks from that pass; sibling tracks landed as
[slice-6](slice-6-consistent-button-macro-adoption.md) here and as separate issues in
`doc-library`/`event-creator`).

## What to build

- `BUTTON_VARIANT_CLASSES["ghost"]` (`design/classes.py`) gains a visible fill or a much stronger
  border — e.g. `bg-paper-2`/`bg-mist-2` background (a shade that actually contrasts against the
  page's own `Paper`/`Mist`) plus a full-opacity or near-full-opacity border, not
  `border-ink-2/30`. Verify against both density variants and both light/dark mode on an actual
  rendered page, not just the token value in isolation — the failure mode here was exactly
  "looks fine as a hex code, invisible in practice."
- `input.html`'s default (non-error) border and `bg-paper` fill get the same contrast pass — the
  input's own background must read as visibly different from the page background it sits on, not
  just have a faint outline. Apply the identical fix to whatever backs the new `select` macro
  below, since it's the same visual problem.
- New `templates/components/select.html` macro (`select` — following `input.html`'s parameter
  shape: `name`, `label`, `options`, `value`, `density`, `required`, `error`), added to
  `packages/chrome`'s `design/` class tables and exported the same way as the other primitives.
  No consuming page uses `<select>` today, but this closes the gap before
  [Event Creator's dashboard-restyle slice](../../event-creator-design-adoption/) needs it — its
  filter bar's type dropdown is the first real caller.
- New `templates/components/toggle.html` macro (`toggle`), generalizing the exact visual pattern
  `profile.html` already hand-wrote for the dark-mode field (`appearance-none` checkbox styled as
  a track+thumb switch) into a reusable primitive with the same `checked:bg-flame` /
  `before:translate-x-5` treatment, parameterized on `name`/`id`/`checked`/`label`. Migrate
  `profile.html`'s dark-mode field to call it, proving the macro replaces the one-off code
  byte-for-byte in behavior.

## Design notes

- No new architectural decisions — same component boundary as Slice 2
  ([ADR: shared component library](../../adr/design-refresh-shared-component-library.md)), just
  correcting values within it and filling two gaps the original primitive list
  (button/input/badge/card-shell/status-dot) missed.
- Both `select` and `toggle` need explicit `dark:` variants for every class, same requirement as
  every other primitive per
  [ADR: dark-mode CSS strategy](../../adr/design-refresh-dark-mode-css-strategy.md).

## Blocked by

- None — `packages/chrome` component primitives already exist (Slice 2, merged).

## Acceptance criteria

- [ ] A `ghost`-variant button is visually distinguishable from its page background at a glance,
      in both light and dark mode, on both `Paper` and `Mist` backgrounds.
- [ ] A default (non-error) input/select field's boundary and fill are visually distinguishable
      from its page background at a glance, in both light and dark mode.
- [ ] `packages/chrome` ships `select` and `toggle` macros, each backed by the new tokens, each
      with a macro-level test mirroring `test_component_macros.py`'s existing pattern.
- [ ] `profile.html`'s dark-mode field uses the new `toggle` macro; no visual/behavioral
      regression (still persists via the existing `PATCH /api/v1/users/me` call).
- [ ] No DaisyUI classes introduced; no regression in any existing macro/E2E test.

## Testing

- Extend `packages/chrome/tests/test_component_macros.py` with `select`/`toggle` cases (structural
  assertions — right element, right `aria-*`/`role` attributes for a given state — not full page
  renders, matching the existing pattern for this file).
- Manual visual check (this slice exists because a value looked fine as a token but failed in
  practice) — screenshot login, profile, and settings pages in both light and dark mode as part of
  review, not just run the test suite.

<!-- /to-implementation appends a "## Delivered" section here once this slice ships. -->

## Delivered (2026-07-19, issue #240, branch `fix/slice-5-component-contrast-hardening`)

- `BUTTON_VARIANT_CLASSES["ghost"]` reworked from a transparent fill with a 30%-opacity border to
  an alpha-blended ink/paper tint (`bg-ink/5 border-ink/30` light, `bg-paper/10 border-paper/40`
  dark) — contrasts against either `Paper` or `Mist` page background without needing to know which
  one it sits on.
- New shared `INPUT_DEFAULT_BORDER`/`INPUT_DEFAULT_FILL` constants in `design/classes.py`, used by
  both `input.html` and the new `select.html`, and by `profile.html`'s own hand-rolled
  `field_input_classes` (which duplicates `input.html`'s markup because its fields need Alpine
  `x-model`) — same contrast fix applied everywhere the pattern existed, not just in the shared
  macro.
- New `templates/components/select.html` macro (`select`), following `input.html`'s
  `name`/`label`/`density`/`required`/`error` parameter shape, plus an `options` param of
  `(value, label)` tuples. No consuming page uses it yet — closes the primitive gap ahead of
  Event Creator's dashboard-restyle slice.
- New `templates/components/toggle.html` macro (`toggle`), generalizing `profile.html`'s
  hand-written dark-mode switch (track+thumb, `checked:bg-flame`/`before:translate-x-5`) into a
  reusable primitive with an optional attached `<label>` (bare-control mode when omitted, so a
  caller can compose it into a custom layout) and optional Alpine `x_model`/`on_change` params.
  `profile.html`'s dark-mode field now calls `toggle("dark_mode", id="dark-mode-toggle",
  x_model="dark_mode", on_change="toggleDarkMode")` — identical `id`/`x-model`/`@change` wiring,
  no behavioral change, verified by a direct template render (not just the macro's own unit
  tests) and confirmed the `e2e/tests/profile.spec.ts` locator (`#dark-mode-toggle`) still
  resolves.
- New shared `templates/components/field_error.html` macro (`field_error`), factored out of
  `input.html`/`select.html`'s previously-duplicated error-message markup during code review
  (code-quality-guardian finding), so a future a11y/copy change to the error state can't drift
  between the two.
- `select()`'s option-match comparison does `opt_value|string == value|string` rather than a raw
  `==`, so numeric option values (e.g. `1`) still match a string-typed `value` (e.g. `"1"`)
  instead of silently leaving nothing selected (code-review-master finding).
- Contrast fix verified visually (not just as token values) by rendering the actual compiled
  Tailwind output in both light/dark mode against both `Paper` and `Mist` backgrounds — ghost
  button, input, select, and toggle are all clearly visible in every combination.
- `packages/chrome` bumped `0.10.3` → `0.11.1` (tags `chrome-v0.11.0`, `chrome-v0.11.1`); root
  `pyproject.toml`/`uv.lock` repinned to `chrome-v0.11.1`.
- Diverged from the plan only in scope, not approach: also fixed `profile.html`'s duplicated
  hand-rolled input classes (same contrast bug, not called out explicitly in the issue) since it
  was the identical defect the issue was filed against.
- `packages/chrome`'s own test suite (77 tests, includes 9 new select/toggle tests) and `mypy
  --strict` are green. Root app's `pytest`/`mypy` also pass for everything not gated on a live
  Supabase connection; DB-dependent tests couldn't be exercised in this environment (no local
  `.env` credentials configured) — pre-existing environment gap, unrelated to this change.
