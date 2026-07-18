# Slice 4 — Profile and Settings shell restyle

> Part of the `design-refresh` feature. PRD: [`../PRD.md`](../PRD.md) · Technical design:
> [`../TDD.md`](../TDD.md)

**Delivers:** Profile and the Settings shell rebuilt on the new design system with real visual
hierarchy — the last two pages carrying old DaisyUI styling, closing out the feature's scope of
"every existing organize-me page."

## What to build

Rebuild `app/templates/profile.html` and `app/templates/settings.html` on the new component
primitives from Slice 2, replacing their `card_page()` usage — the last remaining call sites,
retiring the macro entirely. Profile gains real visual hierarchy (not one undifferentiated card)
per PRD story 11. These are authenticated pages, rendered inside the Slice-2-restyled chrome shell,
using the denser product-page density variant per the PRD's page-type split.

Confirm dark-mode correctness end-to-end on real data-bearing authenticated pages (Slice 1 proved
the mechanism on the landing page; this slice is the first place a logged-in user with
`dark_mode=true` actually sees it applied to real account data).

## Design notes

- Uses the denser/product density variant (per TDD §3), not the marketing variant Slices 1 and 3
  use — status/state (e.g. a saved-change confirmation, a connected/disconnected indicator) should
  be visually encoded via the badge/status-dot primitives, not text alone, per PRD story 13.
- `app/templates/macros/ui.html`'s `card_page()` macro is deleted entirely once this slice lands —
  it has no remaining callers after this.

## Blocked by

- Slice 2 (needs the card/input/button primitives and the restyled chrome shell). Can run in
  parallel with Slice 3 — different pages, no shared file conflicts.

## Acceptance criteria

- [ ] Profile and Settings render with zero DaisyUI classes and zero references to `card_page()`.
- [ ] `app/templates/macros/ui.html`'s `card_page()` macro is deleted (confirmed no remaining
      callers anywhere in the codebase).
- [ ] Profile page shows real visual hierarchy — fields are grouped/distinguished, not one flat
      card of inputs.
- [ ] Settings shell (tab bar + content area) matches the new visual system, tab switching still
      works.
- [ ] A logged-in user with `dark_mode=true` sees correct dark-mode styling on Profile and Settings,
      including on status/badge elements.

## Testing

- Rewrite `tests/test_card_macro.py`'s profile/settings assertions (`"max-w-lg"`, the remaining
  `card-body`/`card-title` checks) to match the new component output, then delete the test file's
  now-obsolete DaisyUI-specific parametrization once nothing references the old classes — or retire
  the file entirely if its full remaining scope is superseded by the new component-macro tests
  added in Slice 2.
- New dark-mode assertion on Profile/Settings, extending the pattern introduced in Slice 1.
- Existing E2E specs (`profile.spec.ts`, `account-deletion.spec.ts`, `sidebar.spec.ts`) stay the
  functional regression backstop.

<!-- /to-implementation appends a "## Delivered" section here once this slice ships. -->
