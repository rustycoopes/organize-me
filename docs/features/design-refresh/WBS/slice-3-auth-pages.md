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

- [ ] All four auth pages render with zero DaisyUI classes and zero references to `card_page()`.
- [ ] Existing auth functionality (register, login, forgot/reset password flows) is unchanged —
      this is a presentation-only change.
- [ ] Validation errors are visually distinct (color/icon/placement), not just present in the DOM.
- [ ] Keyboard focus is visible on every interactive element (input, button, link).

## Testing

- Rewrite `tests/test_card_macro.py`'s auth-page assertions (`"card-body"`, `"card-title"`,
  `"max-w-sm"`) to match the new component output. Keep the structural intent — the title still
  renders as an `<h1>`, the auth-page width variant still applies — since that's the actual
  regression value, not the specific class strings.
- Existing E2E specs (`auth.spec.ts`, `reset-password.spec.ts`) stay the functional regression
  backstop — expected to pass unmodified since behavior isn't changing.

<!-- /to-implementation appends a "## Delivered" section here once this slice ships. -->
