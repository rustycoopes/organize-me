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

## Delivered (2026-07-18, issue #222, branch `feature/design-refresh-slice-1`)

Shipped as planned. `packages/chrome` gained `tokens.css` (the Signal `@theme` palette + font
stack + `@custom-variant dark`) and self-hosted webfonts (Bricolage Grotesque 700, IBM Plex Sans
400, JetBrains Mono 400) as package data, a `paths.py` helper (`chrome_package_dir` and friends)
so consuming services never guess a site-packages path, and a shrunk `theme.py`
(`theme_attr(dark_mode) -> "dark" | ""`). `chrome_base.html` drops all three CDN tags and switches
`<html>` from `data-theme="..."` to `class="{{ theme_attr(dark_mode) }}"`. Released as
`chrome-v0.7.0` (the `chrome-v0.6.x` tags already on the remote belong to the separate, still
unmerged `registry-decoupling` branch — this slice's version bump deliberately skipped past them
to avoid a collision).

organize-me's `pyproject.toml` repins to `chrome-v0.7.0` and gained a `build` dependency group
(`pytailwindcss`). `scripts/build_css.py` generates a Tailwind v4 entry CSS (`@source` globs over
both organize-me's own templates and chrome's installed templates, `@import` of chrome's
`tokens.css`) and compiles `app/static/css/app.css`; `scripts/verify_css_build.py` is the shared
CI canary check (non-empty + `.bg-flame` class present) used by both `ci.yml` and `deploy.yml`.
The `Dockerfile` is now multi-stage — the builder stage installs the `build` group and runs the
compile step, the runtime stage only copies in the compiled `app.css` and the fonts, never the
Tailwind CLI binary or `pytailwindcss` itself. `landing.html` was restyled on the new tokens
(hero/features/CTA structure unchanged) and gained the chat-bubble-resolving-into-a-calendar-chip
signature moment as a static (non-animated) illustration.

Diverged from the plan in one respect: `docker build` itself could not be run in this environment
(no Docker/WSL available) — the pipeline was instead validated by building the actual
`organizeme-chrome@chrome-v0.7.0` wheel, installing it, and running the real Tailwind v4.3.3 CLI
binary directly against `scripts/build_css.py`'s generated entry file (producing a 24.5 KB
`app.css` containing the `.bg-flame` canary class and all three `@font-face` rules), plus rendering
every touched template directly via Jinja to catch errors independent of the (QA-only, no local
credentials) database-backed pytest suite. The actual `docker build` and full pytest suite run for
the first time in CI on this PR.

Two review agents (code-review-master, code-quality-guardian) ran against the full diff; their
findings were fixed inline before merge: a Playwright assertion that passed trivially
(`not.toHaveClass('dark')` doesn't reject an empty class), the CI canary check duplicated
verbatim between `ci.yml`/`deploy.yml` (now `scripts/verify_css_build.py`), the builder Docker
stage installing the unused `dev` dependency group, a stale Dockerfile comment, `--watch` dumping
a traceback on Ctrl+C, and `landing.html`'s dark-mode rendering relying on Jinja's implicit
`Undefined.__bool__()` fallthrough rather than an explicit default. One finding (`packages/chrome`
tests only run at tag-publish time, not on every PR — a pre-existing structural gap) was filed as
follow-up [issue #228](https://github.com/rustycoopes/organize-me/issues/228), `Intake` status,
same `design-refresh`/`slice-1` labels plus `modelsuggested`.
