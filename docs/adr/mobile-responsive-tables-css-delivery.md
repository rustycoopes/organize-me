# Shipped component CSS lives in a new `components.css`, imported unlayered

**Status:** Proposed
**Date:** 2026-09-07
**Feature:** [`mobile-responsive-tables`](../features/mobile-responsive-tables/TDD.md)

## Context

The responsive stacked-table pattern needs `td::before { content: attr(data-label) }` and a
table→card flip in a media query — CSS that cannot be expressed as Tailwind utilities, and that
must not be subject to the Tailwind v4 CLI class-scanning bug that already dropped chrome utility
classes from a consumer's build (`event-creator#46`). So it ships as raw CSS in the
`organizeme-chrome` package.

`organizeme_chrome/static/css/tokens.css` today contains only build *directives* Tailwind
consumes (`@theme`, `@custom-variant dark`) plus `@font-face`. Consumers `@import` it into their
own Tailwind v4 entry CSS *after* `@import "tailwindcss"` and run their own `pytailwindcss` build
(`design-refresh-per-service-tailwind-build`).

Two sub-decisions:
1. Does the pattern go in `tokens.css`, or a new file?
2. What cascade layer does it land in — and therefore, can Tailwind utilities on a cell override
   it?

## Decision

**A new `organizeme_chrome/static/css/components.css`**, resolved via a new
`organizeme_chrome.paths.chrome_components_css_path()` helper (sibling of the existing tokens
path helper). Each adopting consumer adds one `@import ".../components.css";` line to its Tailwind
entry CSS. The feature wires it into `event-creator` and the Host now; `doc-library` and
`ha-dashboard` add the import if/when they adopt.

`tokens.css` stays limited to `@theme` / `@font-face` / `@custom-variant` — design tokens, not
component styles.

**Imported unlayered** (a bare `@import` after `@import "tailwindcss"`, like `tokens.css`), so its
rules sit outside every `@layer` and therefore win against `@layer utilities` regardless of
specificity. This is deliberate: `.om-stacked-table` needs to reliably defeat the per-cell
utilities already on these tables (`truncate`, `max-w-xs`, `w-10` on `logs_grid.html`) when it
flips to card mode. The raw CSS explicitly resets those:
`.om-stacked-table td { display: block; max-width: none; white-space: normal; width: auto; }`
inside the media query.

**Contract**, documented in a docstring on the new `classes.py` constant (held to the same
standard as `TABLE_CLASSES` / `FOCUS_RING`) and in `packages/chrome/DESIGN.md`:
- the class goes on the `<table>` element itself (not a wrapper — `events_panel.html`'s wrapper
  div is load-bearing for Alpine);
- every `<td>` needs `data-label="…"` (empty string allowed for checkbox/actions columns —
  the `::before` is suppressed when `data-label` is empty);
- `<thead>` is retained and only visually hidden below the breakpoint, so the real th↔td
  association still reaches assistive tech — `data-label` is purely cosmetic;
- cells inside `.om-stacked-table` are **not** controllable with Tailwind utilities below the
  breakpoint (the unlayered reset wins).

## Alternatives considered

- **Add the rules to `tokens.css`.** Zero new wiring (consumers already import it). Rejected:
  this PRD ships *two* raw rules (the table pattern and the dialog-width fix), so it is setting
  the policy for all future shipped component CSS, not making a one-off exception. A second
  `@import` line, once per consumer, in a file each consumer already had to touch to adopt chrome
  at all, is a cheap price for keeping `tokens.css` to its one job. Decide the seam before it is
  eight rules deep.
- **A Jinja `responsive_table` macro emitting a real table above the breakpoint and a card list
  below.** Rejected: every table caller rewrites onto it, column content on these two tables is
  highly heterogeneous (checkboxes, initials-badge loops, toggles, link cells), and the existing
  `design-refresh-shared-component-library` ADR already explains why there is no `<table>` macro.
- **Import into `@layer components`** so utilities can override the pattern. Rejected: inverts the
  robustness — a stray `hidden` or `truncate` on a cell would silently break the card flip, and
  the whole point is that opting a table in *reliably* stacks it.

## Consequences

- `tokens.css` keeps a single, defensible purpose; future shipped component CSS has an obvious
  home and precedent.
- Adopters take one extra `@import` line and must re-run `pytailwindcss` after bumping the chrome
  pin (already true of any chrome bump per `design-refresh-per-service-tailwind-build`).
- A consumer that bumps the chrome pin but does **not** add the `@import` gets no change at all —
  the pattern simply isn't in their bundle. Genuinely additive.
- Because the import is unlayered, any consumer that later adds it inherits "these rules beat
  utilities" — fine for the namespaced `.om-stacked-table` selector, but the contract must say so
  because it is surprising.
- Per-cell mobile tweaks (e.g. wanting one column hidden in card view) are not possible with
  utilities — they would need a change to the shared CSS. Accepted; the card deliberately shows
  every field.
