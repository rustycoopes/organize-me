# Each service compiles its own Tailwind CSS at Docker build time

**Status:** Proposed
**Date:** 2026-07-18
**Feature:** [`design-refresh`](../features/design-refresh/TDD.md)

## Context

`packages/chrome` ships shared templates/tokens to three independently-deployed services
(`organize-me`, `event-creator`, `doc-library`) via a versioned git-tag pin. Moving to a real
compiled Tailwind build means a compiled `.css` asset now has to exist and be served by each
service — previously there was no binary asset in this package at all, only Python + Jinja text.

Tailwind's JIT compiler works by scanning template files for the utility classes actually used, and
only emitting CSS for those classes. That scanning has to happen against **every** template that
might use a class — both `packages/chrome`'s own shared templates and each consuming service's own
page-specific templates.

## Decision

Each consuming service compiles its **own** CSS, at its **own** Docker build time, by running
`pytailwindcss` against a content glob covering both its own templates and the installed
`organizeme_chrome` package's templates on disk. `packages/chrome` ships only the raw inputs — the
`@theme` token CSS entry file and component template sources, as chrome package data in its wheel
— never a precompiled bundle, and never runs a build itself. `pytailwindcss` is a dependency of the
consuming service's own `pyproject.toml` (a dedicated build-only dependency group), not of
`packages/chrome`'s.

`packages/chrome` exposes a small helper (returning its own installed template directory path) so
consuming services don't have to hardcode a guessed `site-packages` path into their own Tailwind
content-glob config.

## Alternatives considered

- **Chrome pre-compiles a single canonical CSS bundle at its own release time, ships the compiled
  CSS as package data, consuming services serve it as-is with zero Tailwind tooling of their own.**
  Rejected — not actually viable as a complete solution: at chrome's release time, it has no
  visibility into any consuming service's own page-specific templates, so any utility class a
  service's own pages use that chrome's templates don't would be silently missing from the served
  stylesheet. This isn't a partial trade-off, it's a correctness gap.
- **A hybrid — chrome pre-compiles its own shared-component CSS, each service compiles only its own
  page-specific additions, both loaded together.** Rejected for this feature: adds a second
  stylesheet, a merge-order concern, and real complexity for a problem the simpler per-service full
  build already solves cleanly. Revisit only if per-service build time becomes a real bottleneck
  (unlikely — Tailwind compiles in seconds).
- **A shared, reusable build pipeline (e.g. a GitHub Actions reusable workflow, a CLI wrapper in
  `organizeme_chrome` abstracting the `pytailwindcss` invocation) built now, so `event-creator`/
  `doc-library` can adopt it with zero rework later.** Rejected as premature — this PRD only needs
  to ship `organize-me` correctly; the plain "install chrome, point Tailwind's content globs at your
  own templates + chrome's installed template dir" pattern is already generic enough to copy when
  the second real consumer exists. Building an abstraction against one real and one imagined
  consumer risks needing rework once `event-creator`'s actual layout is known.

## Consequences

- Each service repeats the full Tailwind compile step (full rebuild per service, not incremental
  across services) — accepted cost, since builds are fast and this is the only correct option.
- The Tailwind content-glob path into `.venv`/`site-packages` is somewhat fragile (depends on uv's
  venv layout staying stable) — mitigated by the chrome-side helper function rather than a hardcoded
  path in each consumer.
- Staleness risk shifts from "unbumped chrome pin" (an existing, already-understood risk) to a new
  failure mode: if the Tailwind compile step is cached independently of the chrome-install step in a
  service's own Docker build, the compiled CSS can silently drift out of sync with the templates
  actually being rendered — visually broken (missing utility classes), not an error. Mitigated by
  running the compile step in the same Docker layer/step immediately after `uv sync` installs the
  project, and a CI "canary class" check (see `TDD.md`'s Testing Approach) that fails loudly on
  drift instead of shipping silently wrong.
- `event-creator`/`doc-library` adopt the identical pattern later without needing any change to how
  `packages/chrome` ships its assets.
