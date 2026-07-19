# Slice 3 — Auth pages restyle

> Part of the `design-refresh` feature. PRD: [`../PRD.md`](../PRD.md) · Technical design:
> [`../TDD.md`](../TDD.md)

**Delivers:** Login, registration, forgot-password, and reset-password all rebuilt on the new
design system — a visitor's first real interaction with the product now carries the same
considered identity as the landing page.

## What to build

Rebuild `app/templates/auth/{login,register,forgot_password,reset_password}.html` on the new card,
input, and button primitives from Slice 2, replacing every `card_page()` call site in this set.
Form validation errors get clear visual treatment (not just present-but-unstyled text) per PRD story
10. These are unauthenticated pages — no sidebar/chrome involvement, just `chrome_base.html` +
the new components.

## Design notes

- Uses the marketing/first-impression density variant (per TDD §3's split), not the denser
  product-page variant — these are first-impression pages per the PRD's page-type split, alongside
  landing.
- No new architectural decisions — this slice is component application, not design.

## Blocked by

- Slice 2 (issue [#223](https://github.com/rustycoopes/organize-me/issues/223)) — needs the
  card/input/button primitives to exist.

## Acceptance criteria

- [x] All four auth pages render with zero DaisyUI classes and zero references to `card_page()`.
- [x] Existing auth functionality (register, login, forgot/reset password flows) is unchanged —
      this is a presentation-only change.
- [x] Validation errors are visually distinct (color/icon/placement), not just present in the DOM.
- [x] Keyboard focus is visible on every interactive element (input, button, link).

## Testing

- Rewrite `tests/test_card_macro.py`'s auth-page assertions (`"card-body"`, `"card-title"`,
  `"max-w-sm"`) to match the new component output. Keep the structural intent — the title still
  renders as an `<h1>`, the auth-page width variant still applies — since that's the actual
  regression value, not the specific class strings.
- Existing E2E specs (`auth.spec.ts`, `reset-password.spec.ts`) stay the functional regression
  backstop — expected to pass unmodified since behavior isn't changing.

<!-- /to-implementation appends a "## Delivered" section here once this slice ships. -->

## Delivered (2026-07-18, issue #224, branch `feature/design-refresh-slice-3`)

Shipped as planned. `app/templates/auth/{login,register,forgot_password,reset_password}.html` are
rebuilt on the Slice 2 `card_shell`/`input`/`button` primitives at the marketing density variant;
every `card_page()` call site and DaisyUI class is gone (`tests/test_card_macro.py`'s
`test_auth_pages_have_no_daisyui_classes` pins this). Login/register keep their existing
Alpine.js fetch-based submission logic verbatim — only surrounding markup/classes changed;
forgot-password/reset-password remain plain form POSTs, unchanged from before. Form `action`/
`method`, field `id`s (`#email`/`#password`/`#confirm_password`/`#token`), `autocomplete`, and
`minlength="8"` are all preserved so the existing `auth.spec.ts`/`reset-password.spec.ts` e2e
specs keep working unmodified.

Picked up the error-state half of [issue #233](https://github.com/rustycoopes/organize-me/issues/233)
(filed against Slice 2): the shared `input` macro (`packages/chrome`) gained `error` (flame border,
`aria-invalid`, `aria-describedby`-linked message with icon), plus `minlength`/`autocomplete`
passthrough needed to preserve existing field behavior. Checkbox support (#233's other half) is
still open for whichever of Slice 4 reaches it first.

Two review agents (code-review-master, code-quality-guardian) ran against the diff before merge.
No security/correctness/accessibility regressions found. code-quality-guardian flagged two real
gaps against the WBS's own "rebuild on card/input/button primitives" scope, both fixed inline:

- `forgot_password.html`/`reset_password.html`'s static submit buttons now use the shared
  `button()` macro instead of hand-typing its class string (login/register's submit buttons stay
  hand-rolled since they need `x-show` loading-state slots `button()` can't express).
- The same warning-icon SVG + banner markup had been freshly authored three times in one diff
  (login's error banner, login's info banner, register's error banner). Extracted a new
  `components/alert.html` macro (`danger`/`info` variants, `ALERT_VARIANT_CLASSES` in
  `design/classes.py` following the existing `STATUS_VARIANT_CLASSES` pattern) instead.

A lower-priority finding (the Google sign-in button's SVG icon is still duplicated between
`login.html` and `register.html`) was filed as
[issue #236](https://github.com/rustycoopes/organize-me/issues/236), `Intake`, same
`design-refresh`/`slice-3` labels plus `modelsuggested`.

Diverged from the plan in one respect: since `organizeme-chrome` is consumed via a pinned
git-tag dependency (not a local path — see Slice 2's own Delivered note), this slice's
`input`-macro extension required two chrome releases to reach organize-me itself:
`chrome-v0.10.2` (initial error-state/minlength/autocomplete work), then `chrome-v0.10.3` after
the code-review fixes above. `pyproject.toml`/`uv.lock` are repinned to `chrome-v0.10.3`.
