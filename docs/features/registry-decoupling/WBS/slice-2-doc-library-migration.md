# Slice 2 — doc-library migration

> Part of the `registry-decoupling` feature. PRD: [`../PRD.md`](../PRD.md) · Technical design:
> [`../TDD.md`](../TDD.md)

**Delivers:** A registry change made in organize-me reaches doc-library's live sidebar too, the
same way it already does for event-creator — doc-library is no longer the odd one out still
depending on a package pin for registry data.

## What to build

Apply the same client wiring Slice 1 built for event-creator, to doc-library:

- Add the new Settings fields (`registry_host_url`, `registry_refresh_interval_seconds`,
  `registry_fetch_timeout_seconds`, shared runtime service account identity) to doc-library's
  `app/core/config.py` — genuinely new fields there, since doc-library has no prior
  internal-endpoint pattern to draw on (unlike event-creator, which already had
  `/internal/pipeline/run`'s OIDC verification as prior art — that prior art doesn't help here
  since doc-library is the *minting*, not verifying, side).
- Wire doc-library's `lifespan` to construct a `FetchedRegistrySource` (self-only default =
  doc-library's own `AppEntry`), call `configure_registry_source()`, and spawn/cancel the
  background refresh task — identical shape to event-creator's Slice 1 wiring.
- Set `registry_host_url` as a plain (non-secret) env var per environment in doc-library's
  `deploy.yml`/CI config.
- Bump doc-library's `organizeme-chrome` pin to whatever tag includes Slice 1's
  `registry_client.py`/`RegistrySource` additions.

## Design notes

Identical pattern to Slice 1's event-creator wiring — see TDD "Background refresh loop (per
consumer)" and "Settings additions per consumer." No new design decisions in this slice; it's a
mechanical application of Slice 1's already-proven pattern to a second consumer, confirming the
mechanism generalizes rather than being event-creator-specific.

## Blocked by

- Slice 1 (needs `organizeme_chrome`'s `registry_client.py`/`RegistrySource` machinery and a live
  Host endpoint to fetch from)

## Acceptance criteria

- [ ] doc-library's sidebar renders correctly on a cold start with no reachable Host (self-only
      default).
- [ ] A registry change made only in organize-me appears in doc-library's live sidebar within one
      refresh interval, with no doc-library deploy.
- [ ] A sustained Host outage leaves doc-library serving its last-known-good cache indefinitely,
      same as event-creator's Slice 1 behavior.
- [ ] event-creator (migrated in Slice 1) is unaffected by this slice's changes.

## Testing

- doc-library: same test shape as Slice 1's event-creator tests — `lifespan` startup/shutdown
  task lifecycle, existing sidebar-rendering tests continuing to pass. No new tests needed in
  `packages/chrome/tests/` (the client machinery itself was already covered in Slice 1).

## Delivered (2026-07-18, issue #219, branch `feature/registry-decoupling-slice-2` in
`doc-library`)

Shipped exactly as planned — a mechanical port of Slice 1's event-creator wiring, confirming the
mechanism generalizes to a second consumer with no new design decisions:

- `app/core/config.py`: added `registry_host_url`, `registry_refresh_interval_seconds`,
  `registry_fetch_timeout_seconds` (same defaults as event-creator's Slice 1 fields). No separate
  "shared runtime service account identity" field was added — as with event-creator's Slice 1,
  the client mints its OIDC token via the metadata server for whatever service account the Cloud
  Run revision runs as, so nothing needs to name that identity on the client side; only the Host
  (organize-me) needs `registry_invoker_service_account` to verify against.
- `app/core/registry.py` (new): `SELF_APP_ENTRY` (doc-library's own `AppEntry`, copied verbatim
  from organize-me's compiled-in `APPS` entry for `"doc-library"`), `configure_client_registry_source()`,
  `start_registry_refresh_task()`/`stop_registry_refresh_task()` — byte-for-byte the same shape as
  event-creator's Slice 1 module.
- `app/main.py`: `lifespan` now constructs the `FetchedRegistrySource` and spawns/cancels the
  background refresh task, alongside the existing DB-engine-disposal shutdown step.
- `pyproject.toml`: bumped `organizeme-chrome` pin to `chrome-v0.6.1` (the same tag event-creator's
  Slice 1 used, not the newer `chrome-v0.8.0` which also carries the unrelated design-refresh
  theme changes doc-library hasn't opted into yet). **Fix made during review:** `httpx` was moved
  from the `dev` dependency group into `[project.dependencies]` — `app/core/registry.py`'s refresh
  loop constructs an `httpx.AsyncClient` at runtime, and the import was previously satisfied only
  incidentally via `organizeme-chrome`'s own transitive `httpx` dependency (code-quality-guardian
  review finding).
- CI/deploy (`ci.yml`/`deploy.yml`): looks up organize-me's Cloud Run URL live
  (`gcloud run services describe organizeme-{qa,prod}`) into `REGISTRY_HOST_URL`, mirroring
  event-creator's identical Slice 1 step. Verified doc-library's Cloud Run deploy has no
  `--service-account` override, so it runs as the same shared compute default service account
  (`170051512639-compute@developer.gserviceaccount.com`) organize-me's endpoint already expects
  via `registry_invoker_service_account` — no new IAM/identity wiring needed for this slice.
- Tests: `tests/test_registry_client_wiring.py` (new), 4/4 passing — refresh-task cache update on
  success, last-known-good retention on a failed fetch, clean cancel on shutdown, cold-start
  default. mypy --strict clean (38 source files). Full suite blocked locally on no reachable local
  Postgres (this environment's standing limitation, same as Slice 1); every DB-independent test,
  including all new ones, passes.
