# Slice 3 — Doc link CRUD (list view only)

> Part of the `doc-library` feature. PRD: [`../PRD.md`](../PRD.md) · Technical design:
> [`../TDD.md`](../TDD.md)

**Delivers:** A logged-in user can add, view, edit, and delete their own document links — each
with a title, URL, and freeform category — and see them grouped by category, alphabetically
ordered, on `/doc-library`. This is the feature's core value, fully usable end to end (list view
only; tile view arrives in Slice 4).

## What to build

- `doc_links` table migration in the `doc_library` schema: `id` (UUID PK), `user_id` (UUID, FK
  `host.users.id`, `ON DELETE CASCADE`), `title`, `url`, `category` (all `text`, not null),
  `created_at`.
- A single query function (e.g. `app/models/doc_link.py`'s `list_grouped_by_category(db,
  user_id)`) that fetches a user's links ordered `category, title` and groups them in Python — no
  dedicated service layer, per
  [ADR: no dedicated service layer](../../../adr/doc-library-service-layer.md).
- Pydantic schemas: `DocLinkCreate`, `DocLinkUpdate` (partial, no field is ever nulled),
  `DocLinkResponse` — URL validated as `http`/`https` with a non-empty host; title/category
  required and trimmed non-empty.
- Pure JSON API (`/api/v1/doc-links`): `GET` (list), `POST` (create, 201), `PATCH /{id}` (edit,
  200), `DELETE /{id}` (204). Every operation scopes to `Depends(current_user_id)`; an id that
  isn't the requester's own returns 404, never 403.
- HTML fragment routes (`/doc-library/fragments/links`, HTMX-driven, per
  [ADR: HTMX fragments over a JSON-driven frontend](../../../adr/doc-library-htmx-rendering.md)):
  create/edit/delete each return the re-rendered grouped-list partial. Same underlying query/CRUD
  functions as the JSON API — thin route-handler duplication only.
- `/doc-library` page now renders real content: grouped-by-category list of the user's links (or
  the existing empty state if they have none), with inline add/edit/delete controls wired to the
  fragment routes.

## Design notes

Implements the TDD's Schema, API surface, Pydantic schemas, and Layering design decisions in full
for `doc_links` (the `user_preferences`/view-toggle half is Slice 4). See the TDD's Component/Data
Flow diagram for the create-link request sequence.

## Blocked by

- Slice 2 (needs the authenticated `/doc-library` page and JWT-trust seam already working)

## Acceptance criteria

- [ ] A user can add a link (title, URL, category) and see it appear on `/doc-library`, grouped
      under its category.
- [ ] Categories and links within a category render alphabetically, with no manual ordering
      control.
- [ ] A user can edit a link's title/URL/category and see the change reflected immediately.
- [ ] A user can delete a link and it disappears immediately.
- [ ] Submitting an empty title, empty category, or a non-`http(s)` URL is rejected with a clear
      error, both client-side and server-side.
- [ ] A user cannot view, edit, or delete another user's links — attempting to (e.g. guessing an
      id) returns 404.
- [ ] Unauthenticated requests to any `/api/v1/doc-links*` or fragment route return 401.
- [ ] No cap on the number of links a user can add.
- [ ] Deleting the owning Host user cascades and removes their `doc_links` rows (cross-schema `ON
      DELETE CASCADE`).

## Testing

HTTP-level (`httpx.AsyncClient` + real async test Postgres session), mirroring `event-creator`'s
`tests/test_events_api.py`:

- `tests/test_doc_links_api.py` — 401 unauthenticated; ownership scoping (404 on another user's or
  a nonexistent id, never 403); create/update validation (malformed URL, empty title/category);
  delete removes the row.
- `tests/test_doc_links_fragments.py` — HTMX partial routes return the expected re-rendered
  fragment HTML for create/edit/delete.
- `tests/test_doc_library_page.py` (extended from Slice 2) — grouped/ordered rendering with real
  data, empty state still renders correctly with zero links.
- `tests/test_doc_link_model.py` — DB-level `ON DELETE CASCADE` test against `host.users`,
  matching the R10 pattern (`event-creator`'s `test_event_model.py`).

<!-- /to-implementation appends a "## Delivered" section here once this slice ships. -->
