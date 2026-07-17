# Slice 5 — Prod cutover

> Part of the `doc-library` feature. PRD: [`../PRD.md`](../PRD.md) · Technical design:
> [`../TDD.md`](../TDD.md)

**Delivers:** Doc Library is live at `organizeme.russcoopersoftware.com/doc-library` for real
users, with the full CRUD + view-toggle feature set verified working in production.

## What to build

- `doc-library-prod` Cloud Run service, deployed via the same CI/CD pipeline (Slice 1) with prod
  configuration.
- Prod secrets: `SUPABASE_PROD_URL`, `jwt-secret-prod` access confirmed (same shared deploy SA,
  same secret the Host and `event-creator` already use).
- Prod Postgres schema migration (`doc_library` schema, both `doc_links` and `user_preferences`
  tables) run against the prod database.
- `infra/gcp_lb/provision-prod.sh` run to provision `doc-library-prod`'s Serverless NEG/backend
  service; `generate_url_map.py prod` regenerated and imported into the prod URL map.
- Smoke verification against the live prod domain: login → add a link → see it grouped → toggle
  view → edit → delete, all against real prod infra.

## Design notes

Implements the TDD's "Manual setup" section C. Mirrors `event-creator`'s Slice R12 production
cutover — see [`host-integration-guide.md`](../../../host-integration-guide.md)'s R12 section for
the kind of latent, first-exercised-by-cutover bugs to watch for (e.g. stale encryption keys,
missing env vars that unit tests mock around). Doc Library has no OAuth tokens or
`ENCRYPTION_KEY`-dependent state, so the specific bugs R12 hit don't apply here, but the general
lesson — smoke-test the real thing, don't assume QA parity implies prod correctness — still does.

## Blocked by

- Slice 3 (Doc link CRUD)
- Slice 4 (View-mode toggle)

## Acceptance criteria

- [ ] `doc-library-prod` Cloud Run service is deployed and healthy.
- [ ] `GET https://organizeme.russcoopersoftware.com/doc-library` requires login and renders
      correctly for an authenticated prod user.
- [ ] Add/edit/delete and view-mode toggle all verified working against live prod (not just QA).
- [ ] Prod `doc_library` schema migration applied successfully with no errors.
- [ ] `docs/host-integration-guide.md` updated with a new `## Slice R<n> — Doc Library` (or
      feature-scoped equivalent) section per its "How to keep this doc current" instructions,
      covering infra/routing/secrets/interface-contract for this app.

## Testing

Manual smoke verification against live prod (same shape as `event-creator`'s R12 post-cutover
smoke tests) — no new automated tests are expected in this slice; QA's automated coverage
(Slices 2-4) is presumed to already prove correctness, prod cutover only proves deployment/infra
parity.

<!-- /to-implementation appends a "## Delivered" section here once this slice ships. -->
