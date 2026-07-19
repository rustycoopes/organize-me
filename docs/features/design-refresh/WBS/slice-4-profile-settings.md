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

- Slice 2 (issue [#223](https://github.com/rustycoopes/organize-me/issues/223)) — needs the
  card/input/button primitives and the restyled chrome shell. Can run in parallel with Slice 3
  (issue [#224](https://github.com/rustycoopes/organize-me/issues/224)) — different pages, no
  shared file conflicts.

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

## Delivered (2026-07-18, issue #225, branch `feature/design-refresh-slice-4-profile-settings`)

`app/templates/profile.html` and `app/templates/settings.html` rebuilt on the Slice 2 primitives
(`card_shell`, `alert`, `status_dot`, plus hand-rolled markup using the exposed
`FOCUS_RING`/`DENSITY_PADDING`/`BUTTON_VARIANT_CLASSES` globals for elements needing Alpine
bindings the shared macros' fixed parameter lists can't express — the same idiom Slice 3's
`login.html`/`register.html` already established). `macros/ui.html`'s `card_page()` macro is
deleted; no remaining callers.

Profile gained three distinct `card_shell` sections (Personal details / Appearance / Danger zone)
instead of one flat card, per PRD story 11. The dark-mode toggle now pairs a plain-Tailwind
checkbox with a `status_dot` reflecting Enabled/Disabled state, per PRD story 13's
not-color-only requirement. Fixed a real (pre-existing, unrelated-to-scope-until-now) dark-mode
bug along the way: `toggleDarkMode()` was still setting the pre-design-refresh
`document.documentElement.dataset.theme`, which does nothing under the Slice-1 `dark:`-class
strategy — it now toggles `classList` directly, matching `theme_attr()`'s server-rendered class.
The delete-account confirmation is now a native `<dialog>` styled with a `[&::backdrop]:` arbitrary
variant instead of DaisyUI's `.modal`.

Diverged from the plan in one place: mid-review, `code-review-master` caught that the confirmation
`<dialog>` had been placed as a sibling *after* the closing tag of the Alpine `x-data` root div
rather than nested inside it — Alpine directives don't resolve across that boundary, so
`x-ref="deleteModal"`, `$refs.deleteModal.close()`, and the confirm button's `deleteAccount()`
call would have silently failed. Fixed before merge (dialog moved back inside the `x-data` scope)
and reconfirmed via a template-render smoke test asserting the dialog is a structural descendant
of the root div, since the DB-backed pytest suite and the live-QA Playwright suite can't run in
this sandbox (no local Supabase/JWT secrets, per `docs/secrets-and-accounts.md`) — both run in CI
on push instead. Also fixed a test that asserted the literal substring `"toggle"` never appears in
the page, which would have failed on the correct, non-DaisyUI `toggleDarkMode()`/
`dark-mode-toggle` identifiers; narrowed to check for the DaisyUI `class="toggle` attribute value
instead.

`code-quality-guardian`'s one actionable finding (the three profile form inputs shared one
233-character class string copy-pasted verbatim) was applied — extracted to a single
`field_input_classes` Jinja variable. Its other finding — no `"danger"` entry exists in
`BUTTON_VARIANT_CLASSES`, so the destructive delete-confirmation button is styled identically to
an ordinary primary action beyond an added warning icon — was filed as
[#238](https://github.com/rustycoopes/organize-me/issues/238) (`modelsuggested`) rather than fixed
here, since it's a shared-component-library gap spanning beyond this slice's two pages.

`tests/test_card_macro.py`'s profile/settings section was rewritten (not fully retired — the auth-
page parametrized tests from Slice 3 remain in the same file). `e2e/tests/profile.spec.ts` and
`e2e/tests/account-deletion.spec.ts` selectors were updated for the removed DaisyUI classes
(`input.toggle` → `#dark-mode-toggle`, `dialog button.btn-error` → `#confirm-delete-account-button`).
