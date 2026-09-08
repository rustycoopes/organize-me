# Tables flip to cards at the `lg` breakpoint, aligned with the sidebar drawer

**Status:** Proposed
**Date:** 2026-09-07
**Feature:** [`mobile-responsive-tables`](../features/mobile-responsive-tables/TDD.md)

## Context

The shared chrome frame collapses its sidebar to a hamburger drawer below Tailwind's `lg`
(1024px) — `chrome_authenticated_base.html` uses `lg:pl-64` / `lg:translate-x-0` / `lg:hidden`
throughout. The PRD proposed flipping the data tables to card layout below `md` (768px) "to avoid
introducing a third breakpoint value".

That leaves a dead zone: **768–1024px** (portrait-ish tablets, split-screen windows) renders the
hamburger drawer *and* the full desktop table — the 10-column events table in ~800px is exactly
the cramped, sideways-scrolling state PRD user story 9 ("switch cleanly … no broken in-between")
is trying to eliminate.

## Decision

The stacked-card media query in `components.css` uses **`max-width: 1023.98px`** — i.e. the pattern
is active on the same widths where the sidebar is a drawer, and inactive on the same widths where
the sidebar is pinned. One conceptual breakpoint ("compact vs full layout"), applied consistently
to frame and content.

The value is written once, in `components.css`. It is a literal `1023.98px` with a comment tying
it to Tailwind's default `lg` (`64rem`); if chrome ever redefines `--breakpoint-lg`, this needs a
matching edit (noted in `DESIGN.md`).

## Alternatives considered

- **`md` (768px), per the PRD.** Rejected: creates the 768–1024px hamburger-plus-wide-table dead
  zone. "Avoiding a third breakpoint" is a non-reason — `md` would *be* the third value; `lg` is
  already in use by the frame.
- **`md` for Logs (5 columns, survives ~800px) and `lg` for the Dashboard (10 columns).** Two
  breakpoints, more to reason about, and the Logs table at 800px is still a poor experience even
  if not broken. Rejected for consistency.
- **A container query keyed to the main content area.** Rejected in
  [css-delivery ADR](mobile-responsive-tables-css-delivery.md) — needs `container-type` on a
  chrome-owned ancestor, touching every consumer, for no benefit here (these tables are never
  rendered in a narrow panel at a wide viewport).

## Consequences

- No layout state where the frame is "mobile" and the table is "desktop".
- A browser window between 768 and 1024px wide (uncommon on laptops — 13" screens are 1280+;
  mainly iPad landscape at exactly 1024, which stays in table mode, and split-screen) gets card
  layout. Acceptable: cards are legible at any width, just visually roomy on the high end.
- iPad **landscape** (1024) → table; iPad **portrait** (768) → cards. Clean, predictable.
- The card/table flip and the sidebar drawer flip are the same breakpoint, so QA and the
  screenshot audit only have one width boundary to check.
