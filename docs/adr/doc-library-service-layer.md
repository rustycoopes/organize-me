# No dedicated service layer for Doc Library

**Status:** Proposed
**Date:** 2026-07-17
**Feature:** [`doc-library`](../features/doc-library/TDD.md)

## Context

`event-creator`, the platform's one existing hosted app, structures its code as
`pages/api/models/schemas/services` — five layers, with `app/services/` hosting real cross-cutting
logic (pipeline orchestration, multi-provider storage, LLM calls) shared across multiple routers.
Doc Library is a much smaller app: one entity (`doc_links`), one lazily-created preferences row,
five endpoints, no background processing, no third-party integration. The question is whether to
copy the five-layer structure wholesale for consistency with the sibling app, or size the
structure to what this app actually needs.

## Decision

Doc Library omits `app/services/` as a distinct package. Route handlers in `app/pages/` and
`app/api/v1/` call query/CRUD functions defined directly in `app/models/doc_link.py` (or a single
`app/crud.py`-style module), not an intermediate service layer. Grouping-by-category and
alphabetical ordering are implemented as one query function (`ORDER BY category, title` plus a
Python `itertools.groupby`), not a service abstraction.

## Alternatives considered

- **Copy `event-creator`'s five-layer structure unchanged**, for consistency across hosted apps
  and to make future contributors' mental model transferable. Rejected: with no real
  cross-cutting logic to house, a services layer here would be pure pass-through (`service.
  create_link()` calling `db.add()` and returning) — indirection with no payoff. Consistency
  for its own sake isn't worth adding a layer that does nothing.
- **Fold everything into route handlers directly** (no separate query/CRUD module at all).
  Rejected: even a tiny app benefits from separating "how do I fetch/group doc_links" from "how do
  I turn that into an HTTP response," since both the JSON API and the HTML fragment routes need
  the same query logic — a shared query function avoids duplicating the `ORDER BY`/grouping logic
  in two route handlers.

## Consequences

- Fewer files, less indirection to trace through for a change that touches one entity.
- If Doc Library later grows a second entity, a cross-app reuse need, or genuine cross-cutting
  logic (the same trigger that justified `event-creator`'s `services/`), introducing
  `app/services/` at that point is a small, well-motivated refactor — not a large one, since the
  query functions it would wrap already exist as isolated units.
- A contributor moving from `event-creator` to `doc-library` will notice the missing layer; this
  ADR is the pointer to why, so it doesn't read as an oversight.
