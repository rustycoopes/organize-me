# Slice 2 — Shared component primitives and chrome shell restyle

> Part of the `design-refresh` feature. PRD: [`../PRD.md`](../PRD.md) · Technical design:
> [`../TDD.md`](../TDD.md)

**Delivers:** A small set of reusable design-system components (button, card, input, badge) shared
via `packages/chrome`, and every authenticated page's sidebar/header/Settings tab-bar restyled on
the new visual system — the shell every other page in this feature (and, later, `event-creator`/
`doc-library`) builds on.

## What to build

Add a new `organizeme_chrome/design/` subpackage and matching `templates/components/` directory to
`packages/chrome`, holding Jinja macros for the primitives every hosted app needs: button, input,
badge, card shell, status-dot — following the same pattern that already prevents markup drift for
`nav_link` (chrome's existing nav macro). Implement the marketing-vs-product density split as one
component set with a variant, not two divergent sets, per the TDD.

Restyle `chrome_authenticated_base.html`, `macros/chrome_nav.html`, and `macros/chrome_tabs.html`
in place: swap DaisyUI's `drawer`/`menu`/`btn`/`navbar`/`tabs` classes for the new component
classes. The DOM structure, element IDs, and the `sidebar-nav-groups` Alpine.js wiring (`x-data`,
toggle logic, `aria-expanded` state) stay exactly as they are — this is a class-substitution pass,
not a structural rewrite.

## Design notes

- Component boundary (why primitives live in chrome, not organize-me) and the density-variant
  approach: [TDD §3](../TDD.md#3-shared-component-boundary) and
  [ADR: shared component library](../../adr/design-refresh-shared-component-library.md).
- Sidebar restyle-in-place reasoning, including the explicit rebase/diff check against
  `registry-decoupling` (confirmed via cross-reference to carry no markup conflict — see
  TDD's Open Questions) and against `sidebar-nav-groups`' already-landed tests:
  [TDD §4](../TDD.md#4-sidebar--chrome-restyling) and
  [ADR: sidebar restyle in place](../../adr/design-refresh-sidebar-restyle-in-place.md).
- `packages/chrome/pyproject.toml` will already carry `registry-decoupling`'s runtime deps
  (`httpx`, `google-auth`) by the time this slice starts — this slice's own edits (wheel
  package-data config for the new component templates) land in unrelated sections; verify current
  file content rather than assuming the pre-registry-decoupling shape.

## Blocked by

- Slice 1 (issue [#222](https://github.com/rustycoopes/organize-me/issues/222)) — needs the
  compiled build pipeline and token system to exist before any component can be styled against it.

## Acceptance criteria

- [ ] `packages/chrome` ships button, input, badge, card-shell, and status-dot macros, each backed
      by the new tokens (no DaisyUI classes).
- [ ] `chrome_authenticated_base.html`/`chrome_nav.html`/`chrome_tabs.html` contain zero DaisyUI
      classes; visual appearance is the new system.
- [ ] Every existing `sidebar-nav-groups` behavior still works unchanged: group
      expand/collapse, per-user persistence, current-page force-open override, keyboard operability,
      `aria-expanded` announcement.
- [ ] Settings tab-bar switching (`settings_tab_bar` macro) still works via Alpine, restyled.
- [ ] No regression in any existing sidebar/tab-bar test.

## Testing

- `sidebar-nav-groups`' existing test suite (unit + E2E) passes unmodified — the regression
  backstop proving the class swap didn't touch behavior.
- New macro-level tests for the button/card/input/badge primitives in `packages/chrome/tests/`,
  mirroring `test_card_macro.py`'s existing pattern (pin structural output — e.g. the right element,
  the right `aria-*` attributes for a given variant — not full page renders).
- Extend `e2e/tests/sidebar.spec.ts` (existing) with a visual-smoke assertion that no DaisyUI class
  remains in the rendered sidebar markup.

<!-- /to-implementation appends a "## Delivered" section here once this slice ships. -->

## Delivered (2026-07-18, issue #223, branch `feature/design-refresh-slice-2-component-primitives`)

Shipped as planned. `packages/chrome` gained `organizeme_chrome/design/` (`classes.py` — Tailwind
class-name tables for density/variant, keyed off `tokens.css`'s palette) and
`templates/components/` (`button`, `input`, `badge`, `card_shell`, `status_dot` Jinja macros),
following the same doc-comment/markup-drift-prevention pattern as the existing `nav_link` macro.
The marketing-vs-product density split is one component set with an explicit `density` parameter
per macro call (not two divergent sets), per the ADR and the user's own choice when asked to
clarify the WBS's "one component set with a variant" instruction.

`chrome_authenticated_base.html`, `macros/chrome_nav.html`, and `macros/chrome_tabs.html` were
restyled in place: every DaisyUI class (`drawer`/`drawer-toggle`/`drawer-content`/`drawer-side`/
`drawer-overlay`/`menu`/`btn`/`navbar`/`tabs`/`tab`) is gone, replaced by tokens.css-based Tailwind
classes. The mobile drawer's open/close mechanism — previously provided by DaisyUI's `.drawer` CSS
component — was reimplemented from scratch with a plain `peer`/`peer-checked:` pattern (a hidden
checkbox input plus later-sibling `<label>`s/`<aside>`). DOM structure, element IDs
(`sidebar-drawer-toggle`, `sidebar-nav`, `nav-group-{service_name}`, `sidebar-logout-button`), and
`sidebar-nav-groups`' existing Alpine.js wiring (`x-data`, `x-show`, `:aria-expanded`,
collapsed/stored-collapsed state) are all unchanged.

Released as `chrome-v0.10.1` (superseding an initial `chrome-v0.10.0` tag revised after review, see
below); organize-me's own `pyproject.toml`/`uv.lock` are repinned to that tag.

Two review agents (code-review-master, code-quality-guardian) ran against the full diff before
merge. The most significant finding — the restyle introduced zero `dark:` classes anywhere,
which would have silently broken dark mode for every existing user the moment this merged, per
`docs/adr/design-refresh-dark-mode-css-strategy.md`'s explicit warning — was fixed inline, with new
regression tests (`packages/chrome/tests/test_dark_mode_coverage.py`) pinning `dark:` coverage
across every new/restyled template and class table. The review's other highest-value gap — no
functional test for the reimplemented drawer mechanism — was also addressed with a new
mobile-viewport e2e test that opens/closes the drawer via the hamburger and overlay. Minor
cleanups from review: badge's density text-size now sources from `design/classes.py`
(`DENSITY_BADGE_TEXT`) like every other axis instead of being computed ad hoc, and a comment ties
the `lg:pl-64`/`w-64` width pairing together so a future edit to one doesn't silently break the
other. A lower-priority finding (the `input` macro will need error-state and checkbox support
before Slice 3/4 need them) was filed as [issue #233](https://github.com/rustycoopes/organize-me/issues/233),
`Intake`, same `design-refresh`/`slice-2` labels plus `modelsuggested`.

Diverged from the plan in one respect: the e2e "no leftover DaisyUI classes" check initially
scanned the entire rendered page rather than just the chrome shell, and failed in CI against real
QA data because `/profile`'s still-DaisyUI `card_page()` content (out of this slice's scope,
per the TDD) matched `.btn`/`.tab`. Fixed by scoping the check to the sidebar/header/tab-bar
elements this slice actually restyled.
