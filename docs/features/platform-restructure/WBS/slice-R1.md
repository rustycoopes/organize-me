# Slice R1 — Database Schema Separation

> Part of the OrganizeMe Platform Restructure. Structural PRD:
> [`../platform-restructure-prd.md`](../platform-restructure-prd.md) ·
> Technical design: [`../platform-restructure-design.md`](../platform-restructure-design.md)

**Delivers:** The existing single-`public`-schema database re-organised into `host` and
`event_creator` schemas with least-privilege roles, done **in place in the current monolith** so
the app keeps working unchanged — the foundation for two services owning separate schemas.

## What to build

Introduce two Postgres schemas in the shared Supabase instance and move the existing tables into
them via metadata-only `ALTER TABLE … SET SCHEMA` (no data is rewritten). Keep the app running as
a single service throughout; this slice is pure prefactoring that de-risks the later repo split.

End-to-end: after this slice, every existing page and API works exactly as before, but queries
resolve against schema-qualified tables and the cross-schema foreign key is enforced through a
narrow grant rather than same-schema access.

## Includes
- Create schemas `host` and `event_creator`.
- Create least-privilege DB roles: `host_app` (full R/W on `host`, **no** access to
  `event_creator`) and `event_creator_app` (full R/W on `event_creator`, **no** access to `host`
  except a `REFERENCES`-only grant on `host.users`).
- Move tables via `ALTER TABLE … SET SCHEMA`:
  - → `host`: `users`, `oauth_accounts`
  - → `event_creator`: `storage_configs`, `llm_prompts`, `processing_runs`, `processing_steps`, `events`
- Preserve the cross-schema FK `event_creator.*.user_id → host.users.id` with `ON DELETE CASCADE`,
  backed by the `REFERENCES`-only grant.
- Set Alembic `version_table_schema` so the migration history table lives in a defined schema
  (prepares for per-repo Alembic in R6).
- Update SQLAlchemy models / metadata to declare `__table_args__ = {"schema": ...}` (or engine
  search_path) so ORM queries resolve to the new schemas.

## Relevant schema — ownership map
| Schema | Tables |
|---|---|
| `host` | `users`, `oauth_accounts` |
| `event_creator` | `storage_configs`, `llm_prompts`, `processing_runs`, `processing_steps`, `events` |

## Relevant files
- `app/models/*.py` — add schema to `__table_args__` (`user.py`, `oauth_account.py`,
  `storage_config.py`, `llm_prompt.py`, `processing_run.py`, `processing_step.py`, `event.py`).
- `app/db/base.py`, `app/db/session.py` — search_path / metadata schema wiring if used.
- `migrations/env.py` — `version_table_schema`; new migration under `migrations/versions/`.
- `app/db/url.py` — unaffected, but confirm pooler/`statement_cache_size=0` behaviour holds.

## Design notes
- **Metadata-only move:** `SET SCHEMA` doesn't rewrite rows — this is the concrete mechanism
  behind the PRD's "no data migration required" claim, and makes rollback trivial.
- **Roles are logical separation** enforced at the DB layer, not just convention — the design
  tenet. `event_creator_app` must be unable to `SELECT host.users`; only `REFERENCES` for the FK.
- **Supabase pooler gotcha still applies:** keep `statement_cache_size=0` and the IPv4 pooler URL.
- Do this while still a single service so any breakage is caught by the existing QA deploy + E2E.

## Blocked by
- None — can start immediately.

## Acceptance criteria
- [ ] `host` and `event_creator` schemas exist with the tables moved as mapped above.
- [ ] `host_app` cannot access `event_creator`; `event_creator_app` cannot `SELECT host.users` but
      the FK to `host.users.id` still enforces `ON DELETE CASCADE`.
- [ ] Alembic history table lives in its configured schema; `alembic upgrade head` is clean in QA.
- [ ] The full app (auth, profile, settings, dashboard, upload, pipeline, logs, prompt) works
      unchanged in QA against the schema-qualified tables.
- [ ] Existing pytest + mypy + Playwright E2E suites pass in CI.

## Testing
- Migration test: apply on a QA clone; assert table→schema placement and role grants via
  `information_schema`.
- Delete-cascade test: deleting a `host.users` row removes the user's `event_creator` rows.
- Regression: existing pytest suite + QA E2E (unchanged behaviour is the whole point).
