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

- [x] Zero occurrences of `BUTTON_VARIANT_CLASSES[`/`DENSITY_PADDING[` (or equivalent hand-assembly
      of macro internals) in `app/templates/**` outside of pages that have a genuine, documented
      reason the macro can't yet express (none expected after this slice).
- [x] `login.html`, `register.html`, `profile.html` render identically (visually and behaviorally —
      submitting state, disabled state, spinner-swap text) to before the conversion.
- [x] No regression in `auth.spec.ts`, `profile.spec.ts`, or `account-deletion.spec.ts`.

## Testing

- Existing Playwright specs (`auth.spec.ts`, `profile.spec.ts`, `account-deletion.spec.ts`) stay
  the functional regression backstop — expected to pass unmodified, since behavior isn't changing.
- Extend `packages/chrome/tests/test_component_macros.py` for the macro's new
  `x_bind_disabled`/`x_bind_class`/`attrs` parameters.

<!-- /to-implementation appends a "## Delivered" section here once this slice ships. -->

## Delivered (2026-07-19, issue #241, branch `feature/slice-6-button-input-macro-adoption`)

- `packages/chrome/src/organizeme_chrome/templates/components/button.html` (`button` macro)
  extended with: `x_bind_disabled` (Alpine `:disabled`), `x_bind_class` (Alpine `:class`, now
  auto-derived from `x_bind_disabled` as `{ 'opacity-50 cursor-not-allowed': <expr> }` unless a
  caller sets it explicitly — removes four copy-pasted occurrences of that literal string across
  the converted templates), `attrs` (free-form escape hatch for one-off attributes like `@click`),
  `class_` (extra classes), and `{% call %}`-block support so rich content (icons, multiple
  `x-show` spans for spinner-swap text) no longer requires a plain-string `label`. A new `"danger"`
  variant was added to `BUTTON_VARIANT_CLASSES` (`design/classes.py`) for the outline-red
  "Delete account" trigger button, which didn't fit any existing variant.
- `input.html` (`input` macro) gained the same `attrs` escape hatch (for `profile.html`'s
  `x-model` bindings) and a `class_` param, added for parity with `button`/`alert`'s existing
  convention even though no current caller needs it yet.
- `login.html`'s submit button and Google sign-in link, `register.html`'s submit button and
  Google sign-in link, and `profile.html`'s save/delete-trigger/cancel/confirm-delete buttons and
  name/email/phone inputs all now call the shared macros. `profile.html`'s local
  `field_input_classes` Jinja variable was removed.
- Full audit (`grep -rn "BUTTON_VARIANT_CLASSES\[" app/templates`, same for `DENSITY_PADDING['`)
  confirms these three files were the only hand-rolled call sites in the Host — nothing else
  needed conversion.
- **Diverged from the plan / caught in review**: the initial pass rendered `attrs`, `x_bind_disabled`,
  and `x_bind_class` without `| safe`. Under the chrome test harness's plain `Environment()` (no
  autoescape) this looked correct, but the Host's real environment
  (`app/core/templating.py`'s `Jinja2Templates` → `select_autoescape()`) HTML-entity-escapes
  unmarked interpolations — which would have silently broken `profile.html`'s `x-model` bindings
  and all of its `@click` handlers in production despite every macro test passing. Caught by
  code-review-master's review pass (independently verified by rendering through the real
  `select_autoescape()` path before fixing), not by the test suite itself — the chrome test
  harness's `_env()` now uses `autoescape=True` to match production and prevent a repeat.
  All of these params are developer-authored template literals, never user input, so `| safe` is
  the correct fix rather than a workaround.
- `packages/chrome` bumped `0.11.1` → `0.12.1` (tags `chrome-v0.12.0`, `chrome-v0.12.1` — the
  latter is the autoescape fix); root `pyproject.toml`/`uv.lock` repinned to `chrome-v0.12.1`.
- `packages/chrome`'s own suite (86 tests, includes 13 new/extended macro tests) and `mypy --strict`
  are green. All three converted templates were rendered directly (bypassing the DB-dependent app
  test fixtures, which need Supabase QA credentials not available in this environment — same
  pre-existing gap noted in slice-5's delivery) through the real `select_autoescape()` path to
  confirm ids, `x-model` wiring, `@click` handlers, and Alpine `:class`/`:disabled` bindings all
  survive unbroken. Root app's DB-dependent `pytest` suite (`test_auth.py`, `test_profile_page.py`,
  etc.) could not be exercised locally for the same reason; CI runs them against the real QA
  Supabase instance.

