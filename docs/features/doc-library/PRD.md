# Doc Library — PRD

## Problem Statement

Everyone has a small handful of documents they need to find fast — an insurance policy, a will, a
mortgage document, a warranty — but those links end up scattered across bookmarks, emails, and
sticky notes with no single place to look. What's needed isn't a full document-management system;
it's a tiny, personal, always-in-the-same-place list of "the important stuff," organized just
enough to scan quickly.

## Solution

A new hosted app, **Doc Library**, added to the OrganizeMe platform following the standard
hosted-app pattern (own repo, own Cloud Run service, own DB schema, trusts the Host's JWT — see
[`how-to-add-a-hosted-app.md`](../../how-to-add-a-hosted-app.md)). Each logged-in user maintains
their own private list of document links — title, URL, and a freeform category — grouped by
category on the page, viewable as either a list or a tile grid. Full CRUD (add, edit, delete).
Small by design: no item cap, no sharing between users, no document storage/upload — it only holds
links to documents that live elsewhere.

## User Stories

1. As a user, I want to add a link with a title, URL, and category, so that I can save a document
   I need to find again later.
2. As a user, I want to see my links grouped by category, so that related documents are easy to
   scan together.
3. As a user, I want categories to be freeform text I type myself, so that I don't have to pick
   from a rigid predefined list that doesn't match how I think about my documents.
4. As a user, I want to switch between a list view and a tile view, so that I can choose whichever
   layout is easier for me to scan.
5. As a user, I want my chosen view (list or tiles) to be remembered the next time I visit, so
   that I don't have to re-select it every session.
6. As a user, I want to edit a link's title, URL, or category, so that I can fix a mistake or
   update a stale link without deleting and re-adding it.
7. As a user, I want to delete a link, so that I can remove documents that are no longer relevant.
8. As a user, I want the app to reject a URL that isn't a plausible `http(s)://` link, so that I
   catch typos before they end up in my list.
9. As a user, I want only my own links to be visible to me, so that my document list stays
   private — no other user (including someone I share the household/org with) can see or edit it.
10. As a user, I want to add as many or as few links as I actually need, so that the app doesn't
    arbitrarily block me even though I only expect to keep around 5 important items.
11. As a user, I want links within a category sorted alphabetically by title, and categories
    themselves sorted alphabetically, so that the ordering is predictable without me having to
    manage it manually.
12. As a user, I want Doc Library to appear in the OrganizeMe sidebar like any other app, so that
    I can navigate to it the same way I navigate to Dashboard/Settings/etc.
13. As a user, I want to reach Doc Library only when logged into OrganizeMe, so that an
    unauthenticated visitor is redirected to login rather than seeing anyone's document list.

## Implementation Decisions

- **New repo `doc-library`**, following the `event-creator`-established pattern exactly:
  - Own Cloud Run service(s) (`doc-library-qa`/`doc-library-prod`), own `doc_library` Postgres
    schema (shared Supabase instance, own Alembic history with `version_table_schema` set to
    `doc_library`), own CI/CD mirroring `.github/workflows/` shape from `event-creator`.
  - No login/session/registration code — trusts the Host-issued JWT cookie, verified via the
    `organizeme-chrome` package's standalone JWT-verify helper (signature + expiry, no
    fastapi-users import, no network call).
  - Reads `JWT_SECRET` from GCP Secret Manager (`jwt-secret-{qa,prod}`), same value as the Host.
    No `ENCRYPTION_KEY` needed (no third-party credentials stored).
  - Every page route passes `dark_mode` into the shared chrome's `theme_attr()` context, read via
    a `HostUser`/`get_dark_mode()` helper against `host.users`, same pattern as `event-creator`'s
    `app/services/host_user.py` (see the R7 gotcha in `host-integration-guide.md`).
- **App registry entry** (added to `organize-me`'s
  `packages/chrome/src/organizeme_chrome/registry.py`, then `organizeme-chrome` version bumped
  and pinned by `doc-library`):
  - `service_name="doc-library"`
  - `nav=[AppNavItem("/doc-library", "Doc Library")]`
  - No `settings_tabs` (view preference lives in-page, not in the Settings shell).
  - `api_prefixes=["/api/v1/doc-links"]` (or whatever the API router prefix ends up being —
    finalize in `/to-design`).
- **Data model** (`doc_library` schema):
  - `doc_links` table: `id` (UUID PK), `user_id` (UUID, FK → `host.users.id`, `ON DELETE CASCADE`,
    `REFERENCES`-only grant per the R1 schema-separation contract), `title` (text, required),
    `url` (text, required), `category` (text, required), `created_at`.
  - No `sort_order` column — ordering is computed at query/render time (category then title,
    alphabetical), not stored.
  - No dedicated categories table — `category` is a plain text column on `doc_links`; grouping is
    a `GROUP BY category` (or equivalent in-memory grouping) on whatever string value is present,
    not a managed/foreign-keyed taxonomy.
- **View preference**: one boolean/enum column (e.g. `view_mode`) on a per-user preferences row in
  `doc_library`'s own schema (its own `user_settings`-equivalent table, not the Host's `users`
  table — same reasoning as `event_creator.user_settings`, created lazily get-or-create on first
  write, not eagerly at registration). No Settings-tab UI; the toggle lives directly on the Doc
  Library page and saves via a small API call when clicked. Defaults to list view when no
  preference row exists yet.
- **API surface** (finalize exact routes/verbs in `/to-design`, but the shape is):
  - `GET /doc-library` — page route, renders the grouped list/tile view server-side using the
    user's current `view_mode`.
  - `POST /api/v1/doc-links` — create.
  - `PATCH /api/v1/doc-links/{id}` — edit.
  - `DELETE /api/v1/doc-links/{id}` — delete.
  - `PUT /api/v1/doc-links/view-mode` (or similar) — persist the list/tile toggle.
  - Every endpoint scopes all reads/writes to the requesting user's own `user_id` extracted from
    the verified JWT — no endpoint accepts or trusts a `user_id` from the request body/query.
- **Validation**: `url` must parse as `http://` or `https://` with a non-empty host, checked
  client-side (fast feedback) and re-checked server-side (source of truth) on create/edit; no
  liveness check against the URL itself. `title` and `category` are required, non-empty after
  trim.
- **No item cap** — `doc_links` has no per-user row limit enforced anywhere in the stack.
- **No sharing** — no concept of a shared/household list, no admin visibility into another user's
  links; this is out of scope entirely, not just deferred UI.

## Testing Decisions

- Good tests here assert observable behavior through the app's actual seams (HTTP responses, page
  content, DB state after a request) — not internal function calls or ORM-object shape.
- **Primary seam: FastAPI HTTP layer**, `httpx.AsyncClient` against the real app with a real test
  Postgres session (async), following `event-creator`'s existing pattern almost exactly:
  - `tests/test_doc_links_api.py` — modeled on `event-creator/tests/test_events_api.py`: auth
    required (401 unauthenticated), a user only ever sees/edits/deletes their own rows (never
    another user's, even by guessing an id), create/edit validation (rejects malformed URL, empty
    title/category), delete removes the row, `PATCH` on a nonexistent/foreign id returns 404 not a
    silent no-op.
  - `tests/test_doc_library_page.py` — modeled on
    `event-creator/tests/test_dashboard_page.py`/`test_processing_page.py`: unauthenticated
    request redirects to Host login; authenticated request renders 200 with the user's links
    grouped by category, correctly ordered; empty-list state renders without erroring; `dark_mode`
    context flows through per the R7 pattern.
  - `tests/test_view_mode_api.py` — persisting and reading back the list/tile preference,
    including the get-or-create-on-first-write path (no row yet ⇒ defaults to list).
  - `tests/test_doc_link_model.py` — DB-level `ON DELETE CASCADE` test against `host.users`,
    matching the R10 pattern (`test_event_model.py`) for schema-separation cascade coverage that
    isn't observable over HTTP.
- **Boundary/e2e**: no new entry needed in `organize-me`'s
  `e2e/tests/host-event-creator-boundary.spec.ts`-style suite is required for this app alone per
  se — but if `doc-library` wants its own boundary coverage (JWT trust, logout propagation), it
  follows the same rule from `how-to-add-a-hosted-app.md`'s "Test ownership" section: a spec
  asserting the Host↔app auth seam lives in the Host (`organize-me`); everything else lives in
  `doc-library`'s own repo, including a Playwright/browser-level smoke test of add → view →
  toggle-view → edit → delete, once the UI exists to drive.
- Unit tests for the URL-validation helper (valid/invalid schemes, missing host, empty string)
  live in `doc-library`'s own repo alongside the helper, no prior-art dependency on another app.

## Out of Scope

- Sharing a list between users, household/admin visibility into another user's links.
- A managed/predefined category taxonomy, autocomplete, or category rename/merge tooling.
- Any per-user or global maximum on the number of links.
- Manual/drag-and-drop ordering — ordering is always alphabetical (category, then title).
- A description/notes field, tags beyond the single category, icons, thumbnails, or link-preview
  fetching.
- URL liveness/reachability checking (only format validation).
- A Settings-tab presence in the shared Settings shell.
- Document storage/upload of any kind — this app only stores links to documents that live
  elsewhere, never the documents themselves.

## Further Notes

- This is the platform's third hosted app (after the Host itself and `event-creator`), so it's a
  good forcing function to validate `how-to-add-a-hosted-app.md`'s playbook against a genuinely
  new, independent team — flag anything in that doc that turns out to be stale or
  `event-creator`-specific during `/to-design`/`/to-implementation`.
- Because this repo doesn't exist yet, this PRD (and the TDD/WBS that follow it) live in
  `organize-me/docs/features/doc-library/` per the project convention for a brand-new app; once
  the `doc-library` repo is created, its own future feature work's docs move there, matching how
  `event-creator` now owns its own `docs/features/` going forward.
- Infra provisioning (Cloud Run services, Serverless NEG/backend service, Secret Manager grants,
  URL-map regeneration/import) are manual operator steps per
  [`host-integration-guide.md`](../../host-integration-guide.md)'s checklist — not something CI
  performs, and worth sequencing explicitly in the WBS so implementation doesn't stall waiting on
  them.
