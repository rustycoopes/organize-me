# Slice 1 — Repo & infra setup

> Part of the `doc-library` feature. PRD: [`../PRD.md`](../PRD.md) · Technical design:
> [`../TDD.md`](../TDD.md)

**Delivers:** A new `doc-library` repo whose CI/CD pipeline builds, tests, and deploys a minimal
FastAPI skeleton to its own QA Cloud Run service — with every secret and GitHub Actions
credential it will ever need for this feature already in place, before any real page or endpoint
exists.

## What to build

Stand up the `doc-library` repo and its deploy pipeline, with no Doc Library feature logic yet —
this is pure scaffolding so Slice 2 onward can focus entirely on the SSO-trust seam and feature
code, not on infra.

- New GitHub repo `doc-library`, FastAPI project skeleton (mirroring `event-creator`'s repo
  layout: `app/`, `tests/`, `migrations/`, `pyproject.toml`, `Dockerfile`, `.github/workflows/`)
  with a trivial health-check route and no other behavior yet.
- CI workflow (build → test → deploy) mirroring `event-creator`'s `.github/workflows/` shape,
  targeting a `doc-library-qa` Cloud Run service.
- GitHub Actions secrets set in the new repo: `GCP_SA_KEY` (copied from the existing shared
  deploy service account — no new GCP SA needed), `SUPABASE_QA_URL`, `SUPABASE_PROD_URL`.
- Confirm (don't recreate) that the shared deploy SA already has `secretmanager.secretAccessor` on
  `jwt-secret-{qa,prod}` — it does today since every service shares one deploy SA.
- Explicitly confirm and document that `ENCRYPTION_KEY` is **not** needed for this app (no
  third-party credentials stored) — a deliberate omission, not an oversight, per the TDD.
- Own Postgres schema (`doc_library`) created in the shared Supabase instance, with its own
  Alembic history (`version_table_schema=doc_library`) — no tables yet, just the schema and
  migration scaffolding wired up.
- Confirm the `doc_library` migration role has `REFERENCES` privilege on `host.users` (TDD Open
  Question #2) — extend the R1 grant mechanism if it doesn't.

## Design notes

Implements TDD's "Manual setup — repo, secrets, infra" section A (steps 1-6). See
[`host-integration-guide.md`](../../../host-integration-guide.md)'s manual-steps checklist and
[`how-to-add-a-hosted-app.md`](../../../how-to-add-a-hosted-app.md) for the general pattern this
follows — this slice does *not* yet touch the Host repo's registry or the Load Balancer (that's
Slice 2's job); it only needs the service reachable at its own `*.run.app` URL for smoke-testing.

## Blocked by

None — can start immediately.

## Acceptance criteria

- [ ] `doc-library` repo exists with a working CI/CD pipeline (build, test, deploy stages all
      green).
- [ ] A deploy of the skeleton app succeeds and the health-check route responds at the Cloud
      Run `*.run.app` URL for `doc-library-qa`.
- [ ] `GCP_SA_KEY`, `SUPABASE_QA_URL`, `SUPABASE_PROD_URL` are set as GitHub Actions secrets in
      the new repo (not inherited from the Host repo).
- [ ] `doc_library` Postgres schema exists with its own independent Alembic history
      (`version_table_schema=doc_library`), verified by running an empty migration successfully.
- [ ] `doc_library`'s migration role has confirmed `REFERENCES` privilege on `host.users`.
- [ ] `ENCRYPTION_KEY` is confirmed unnecessary and explicitly noted as such in the new repo's own
      setup docs (e.g. its README or an equivalent doc), not silently omitted.

## Testing

Infra/CI verification, not application-level tests: a green CI run on the new repo is the
acceptance signal for the pipeline; a successful `alembic upgrade head` against QA (creating no
tables yet) verifies the schema/migration-history setup. No unit or HTTP-level tests are
meaningful yet since there's no feature code — `tests/test_health.py` (a trivial 200-OK check,
matching `event-creator`'s own `tests/test_health.py`) is the only test this slice needs.

<!-- /to-implementation appends a "## Delivered" section here once this slice ships. -->
