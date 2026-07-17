# HTMX fragments over a JSON-driven frontend for Doc Library

**Status:** Proposed
**Date:** 2026-07-17
**Feature:** [`doc-library`](../features/doc-library/TDD.md)

## Context

Doc Library needs add/edit/delete for `doc_links` and a view-mode (list/tiles) toggle, all without
a full-page reload feeling clunky for what's meant to be a quick, lightweight page. `event-creator`
already established a precedent for exactly this shape of interaction — its Settings tabs
(`app/pages/settings_fragments.py`) fetch and swap HTML fragments via HTMX (`hx-get`,
`hx-trigger="load"`) rather than shipping a JSON API consumed by hand-written client JavaScript.
The alternative — a pure JSON API plus a client-side JS layer (vanilla fetch/render, or a small
framework) — is also viable and is what a from-scratch app with no sibling precedent might default
to.

## Decision

Doc Library renders mutations via HTMX partial swaps against dedicated fragment routes
(`app/pages/doc_links_fragments.py`, e.g. `POST /doc-library/fragments/links`), matching
`event-creator`'s existing Settings-fragment pattern. A separate, pure-JSON `/api/v1/doc-links`
surface exists alongside it for test/API consumers, but the page itself never talks to that JSON
API directly — no hand-written client JS, no SPA-style JSON-driven rendering.

## Alternatives considered

- **Pure JSON API + hand-written client JS.** Rejected as the default: it would introduce a third
  rendering style into the platform (server-rendered pages, HTMX fragments, and now JSON+JS) for
  no functional gain — Doc Library's interactions (add/edit/delete a row, toggle a boolean) are
  exactly the shape HTMX already handles well elsewhere in this platform. Client JS also means a
  build step or at least hand-maintained fetch/DOM-update code with no existing pattern to lean
  on.
- **Plain server-rendered forms + full-page redirects, no partial updates at all.** Rejected:
  cheapest to build, but every add/edit/delete would reload the whole page including the shared
  chrome/sidebar, which reads as sluggish for a "quick reference" page whose entire value
  proposition is being fast to check and update.
- **One combined content-negotiated endpoint** (same route returns JSON or HTML fragment based on
  `Accept`/`HX-Request` headers) instead of two separate route sets. Rejected: keeps the JSON
  contract simple and testable without conditional response-shape logic, at the cost of two thin
  route handlers per operation instead of one — an acceptable, small duplication.

## Consequences

- Consistent with the one existing precedent in the platform; a contributor who's worked on
  `event-creator`'s Settings tabs already knows the pattern.
- No client-side JS bundle/build step to introduce or maintain for this app.
- Two route surfaces (JSON + fragment) per mutation means slightly more route-handler code than a
  single JSON API would need, in exchange for not coupling the JSON contract to HTML rendering
  concerns.
- If Doc Library (or a future hosted app) later needs richer client-side interactivity than HTMX
  swaps comfortably support, that's a deliberate future decision with its own ADR — this decision
  doesn't block it, since the JSON API already exists as a foundation.
