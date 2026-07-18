# Slice 1 — Build pipeline, design tokens, and landing page

> Part of the `design-refresh` feature. PRD: [`../PRD.md`](../PRD.md) · Technical design:
> [`../TDD.md`](../TDD.md)

**Delivers:** A working, compiled custom Tailwind build with OrganizeMe's own design tokens,
serving a fully restyled landing page — proving the whole pipeline end-to-end before anything else
in the feature builds on top of it.

## What to build

Replace the current Tailwind CDN "Play" script + DaisyUI setup with a real compiled build. Add a
build-only dependency group to organize-me's `pyproject.toml` (`pytailwindcss`), convert the
Dockerfile to a multi-stage build (a build stage compiles the CSS, the runtime stage copies only
the compiled artifact — the Tailwind CLI binary and build-only packages never ship in the deployed
image), and document the local-dev watch command.

Add the design-tokens CSS file (Tailwind v4 `@theme` block: the "Signal" palette — Ink, Paper,
Flame, Cobalt, Mist, Sage — plus the display/body/mono font stack) as `packages/chrome` package
data, along with the self-hosted webfont files served from organize-me's `/static` mount.
`chrome_base.html` loses all three CDN tags, gains a `<link>` to the compiled stylesheet, and the
dark-mode mechanism switches from DaisyUI's `data-theme` attribute to an explicit `.dark` class
driven by a `@custom-variant`, so `User.dark_mode` keeps working exactly as it does today. `theme.py`
shrinks to just the dark/light class selector.

Restyle `app/templates/landing.html` on the new tokens — keep its existing hero/features/CTA
section structure (the PRD calls this sound, not broken), but express it through the new visual
system rather than DaisyUI defaults. Add the signature landing-hero moment: a chat message visually
resolving into a calendar/event chip, literalizing what the product does.

## Design notes

- Build/distribution approach, Docker layering, and the reasoning against precompiling in
  `packages/chrome`: [TDD §1](../TDD.md#1-build-pipeline--css-distribution) and
  [ADR: per-service Tailwind build](../../adr/design-refresh-per-service-tailwind-build.md).
- Tailwind v4 `@theme` token shape and the `theme.py` shrink:
  [TDD §2](../TDD.md#2-tailwind-version--token-ownership).
- Dark-mode class mechanism — this is the easiest detail in the whole feature to silently lose;
  see [ADR: dark-mode CSS strategy](../../adr/design-refresh-dark-mode-css-strategy.md) for exactly
  why the v4 default (OS-preference-driven) would regress existing behavior.
- No component primitives yet (that's Slice 2) — the landing page can be restyled directly with
  Tailwind utilities against the new tokens; it doesn't need the shared button/card/input macros to
  prove the pipeline works.

## Blocked by

None — can start immediately.

## Acceptance criteria

- [ ] `docker build` produces an image with no Tailwind CLI binary or build-only Python packages
      present in the final layer, but a compiled, non-empty stylesheet served from `/static`.
- [ ] `chrome_base.html` no longer references the Tailwind CDN script, the DaisyUI stylesheet, or
      any DaisyUI class.
- [ ] Visiting `/login`, `/register`, or any other still-unstyled page does not error — the new
      stylesheet coexists with not-yet-restyled DaisyUI markup elsewhere in the app during this
      slice (DaisyUI's own CDN is gone, so any DaisyUI class on an unmigrated page will render
      unstyled — expected and acceptable until Slices 2-4 land; not a regression to fix here).
- [ ] The landing page renders the new visual system: new typography, new color tokens, and the
      chat-bubble-to-calendar-chip signature moment.
- [ ] A user with `dark_mode=true` sees `class="dark"` on `<html>`; a user with `dark_mode=false`
      (or an anonymous visitor) does not.
- [ ] CI fails loudly (not silently) if the Tailwind build produces empty/near-empty output or a
      known canary utility class is missing from the compiled CSS.

## Testing

- New CI step: run the Tailwind compile, assert the output file is non-empty above a size
  threshold, and assert a canary class known to be used by the new tokens/landing markup appears in
  the compiled output.
- New test asserting `class="dark"` presence/absence on `<html>` tracks `User.dark_mode`
  correctly (first instance of this test — profile/settings pages in Slice 4 reuse the pattern).
- Extend `e2e/tests/landing.spec.ts` (existing) with a smoke assertion that the Tailwind CDN script
  and DaisyUI stylesheet are no longer referenced, and the compiled stylesheet returns 200.
- No visual regression/screenshot tooling (per PRD, out of scope).

<!-- /to-implementation appends a "## Delivered" section here once this slice ships. -->
