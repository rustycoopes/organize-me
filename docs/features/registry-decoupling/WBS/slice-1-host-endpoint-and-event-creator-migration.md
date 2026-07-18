# Slice 1 — Host registry endpoint + client machinery + event-creator migration

> Part of the `registry-decoupling` feature. PRD: [`../PRD.md`](../PRD.md) · Technical design:
> [`../TDD.md`](../TDD.md)

**Delivers:** A registry change made in organize-me (a new nav item, a new app entry) reaches
event-creator's live sidebar within one refresh interval — no event-creator rebuild, no pin bump,
no redeploy.

## What to build

**In organize-me (the Host):**

- Move the hand-authored `APPS` list out of `organizeme_chrome.registry` and into the Host's own
  app code. Wire it up via a new `InProcessRegistrySource`, registered once at Host startup —
  the Host's own `list_apps()`/`get_app()` calls (`app/core/nav.py`, `app/pages/settings.py`)
  keep working unchanged, now resolving against the in-app data directly, with no network call.
- Add a new internal endpoint, `GET /internal/app-registry.json`, that serializes the current
  registry to JSON. Protect it with app-level OIDC verification (checks the bearer token's `aud`
  and `email` claims), mirroring event-creator's existing `/internal/pipeline/run` verification
  pattern. Fail closed (503) if the expected settings aren't configured in the current
  environment.

**In `organizeme_chrome` (the shared package):**

- Add a `RegistrySource` protocol (`get_apps() -> list[AppEntry]`) that `list_apps()`/`get_app()`
  read against, via a new `configure_registry_source()` call each app makes once at startup.
- Add a new leaf module, `registry_client.py`, holding: a pure `fetch_registry_once(client,
  host_url, token_provider)` function; `FetchedRegistrySource`, a cache object with an `update()`
  method and a caller-supplied self-only cold-start default; a default OIDC `token_provider`
  (metadata-server-based token minting, injectable for tests). This module must import cleanly
  without pulling `httpx`/`asyncio`/`google.auth` into `nav_groups.py`, `templating.py`, or
  `jwt_verify.py`.
- Keep today's compiled-in `APPS` literal as the implicit fallback `RegistrySource` for any
  consumer that hasn't called `configure_registry_source()` yet — doc-library isn't migrated
  until Slice 2, and must keep working unmodified throughout this slice.

**In event-creator:**

- Add the new Settings fields (`registry_host_url`, `registry_refresh_interval_seconds`,
  `registry_fetch_timeout_seconds`, plus reusing whichever field already names the shared runtime
  service account).
- Wire `lifespan` to construct a `FetchedRegistrySource` (self-only default = event-creator's own
  `AppEntry`), call `configure_registry_source()`, and spawn/cancel the background refresh task.
- Set `registry_host_url` as a plain (non-secret) env var per environment in event-creator's
  `deploy.yml`/CI config.

## Design notes

See TDD sections "Host endpoint shape," "`organizeme_chrome` package structure," "Background
refresh loop (per consumer)," "Settings additions per consumer," and "Rollout mechanics." Full
rationale for the two hardest calls in this slice:
[`registry-decoupling-client-boundary`](../../../adr/registry-decoupling-client-boundary.md) (why
the fetch client is a leaf module with no self-scheduling) and
[`registry-decoupling-endpoint-auth`](../../../adr/registry-decoupling-endpoint-auth.md) (why
app-level OIDC over Cloud Run's IAM invoker gate, and why the Host URL is a plain env var).

Deployment order matters within an environment: the Host's endpoint must be live in QA before
event-creator's migration is deployed to QA (independent of prod's own ordering) — see TDD
"Rollout mechanics." If deployed out of order, event-creator's cold-start default keeps its own
nav correct; only other apps' entries are missing until the Host catches up — never broken chrome.

## Blocked by

None — can start immediately.

## Acceptance criteria

- [ ] organize-me's own Settings/Profile pages render correctly with `APPS` moved into Host app
      code and resolved via `InProcessRegistrySource` (no behavior change visible to the Host's
      own users).
- [ ] `GET /internal/app-registry.json` returns the current registry as JSON for a validly-signed
      OIDC token matching the expected `aud`/`email`, and rejects (401/403/503 as appropriate)
      every other case.
- [ ] event-creator's sidebar renders correctly on a cold start with no reachable Host (self-only
      default — event-creator's own nav shows, other apps' entries don't).
- [ ] A registry change made only in organize-me (e.g. a new nav item on an existing app) appears
      in event-creator's live sidebar within one `registry_refresh_interval_seconds` window, with
      no event-creator deploy.
- [ ] doc-library (not yet migrated) continues to render its sidebar unchanged throughout, proving
      the transitional compiled-in fallback still works.
- [ ] A sustained Host outage (endpoint returning errors) leaves event-creator serving its
      last-known-good cache indefinitely — no degraded UI, only a log-visible staleness signal.

## Testing

- `packages/chrome/tests/`: unit tests for `fetch_registry_once` against `httpx.MockTransport`
  (200/401/403/5xx/timeout/malformed-JSON cases) with a fake `token_provider`; `FetchedRegistrySource`
  cache-update and cold-start-default behavior; `RegistrySource`/`configure_registry_source()`
  wiring for both `InProcessRegistrySource` and `FetchedRegistrySource`. Matches the existing style
  of `test_registry.py`/`test_nav_groups.py` — no real network or timers.
- organize-me: endpoint auth matrix tested via the existing `AsyncClient`-against-`app` pattern
  (valid token → 200 with current registry; missing/invalid/wrong-`aud`/wrong-`email` → 401/403;
  unconfigured settings → 503).
- event-creator: `lifespan` startup/shutdown spawns and cleanly cancels the refresh task (no real
  sleep — inject a fake interval or drive the loop directly); existing sidebar-rendering page
  tests (the `storedCollapsed`-assertion tests already fixed for the 3-app registry) continue
  passing against whatever `RegistrySource` the test fixtures configure.

## Delivered (2026-07-18, issue #218, branches `feature/registry-decoupling-slice-1` in both
`organize-me` and `event-creator`)

Shipped as designed, with one deliberate deviation and one fix made during review:

- `organizeme_chrome`: `RegistrySource` protocol, `configure_registry_source()`,
  `reset_to_default_registry_source()` (added during review so tests — in the package and in
  downstream consumers — don't reach into the private `_CompiledRegistrySource`), and the new
  leaf module `registry_client.py` (`fetch_registry_once`, `FetchedRegistrySource`, a metadata-
  server-backed default `token_provider`). Tagged `chrome-v0.6.1` (0.6.0 shipped first; 0.6.1
  folded in the review fix above before either tag was consumed by a real pin bump).
- organize-me (Host): `APPS` forked into `app/core/registry.py` behind `InProcessRegistrySource`,
  registered as an import-time side effect. Confirmed byte-identical to the package's prior
  literal. New `GET /internal/app-registry.json` (`app/api/internal/registry.py`) mirrors
  event-creator's `_verify_push_token` shape exactly, including the 503-when-unconfigured fail-
  closed behavior. **Deviation from the original plan:** `app/pages/settings.py`'s
  `get_app("event-creator")` lookup was moved from module-import time to per-request during
  review (code-review-master flagged the import-order dependency it created as fragile) — the
  only remaining import-time call site is `app/pages/app_shell.py` (route registration genuinely
  needs it eager), and `tests/test_registry_wiring.py` now asserts the Host resolves against its
  own `InProcessRegistrySource` rather than silently falling back to the package's compiled-in
  literal if that ordering were ever broken.
- event-creator: `app/core/registry.py`'s `SELF_APP_ENTRY` cold-start default, wired into a
  `FetchedRegistrySource` via `configure_client_registry_source()`; `lifespan` spawns/cancels the
  background refresh task. **Fix made during review:** the loop originally slept a full
  `registry_refresh_interval_seconds` before its *first* fetch attempt, meaning a fresh Cloud Run
  instance would serve only its self-only default for up to a minute after every cold
  start/deploy — changed to fetch immediately on startup, then sleep between subsequent attempts.
- CI/deploy (`ci.yml`/`deploy.yml`, both repos): organize-me captures its own post-deploy URL into
  `REGISTRY_ENDPOINT_URL` (mirrors the existing `PIPELINE_ENDPOINT_URL` pattern); event-creator
  looks up organize-me's Cloud Run URL live (`gcloud run services describe organizeme-{qa,prod}`)
  into `REGISTRY_HOST_URL` rather than hardcoding it, since the exact URL wasn't known without
  querying GCP directly.
- Full test suites (both repos) blocked locally on no reachable local Postgres (this
  environment's standing limitation — see each repo's own conftest.py) beyond what each
  module's own DB-free fixtures could exercise; every new/changed module was verified via mypy
  --strict (clean across both repos) and targeted DB-free pytest runs (19/19 organize-me,
  4/4 event-creator, 38/38 `packages/chrome`). Full CI (with real Supabase QA credentials) is
  the first complete run of the DB-dependent suites.
- One suggestion from review was deferred rather than fixed now (not a correctness issue): caching
  the minted OIDC token instead of re-minting it every refresh cycle — filed as
  [organize-me#226](https://github.com/rustycoopes/organize-me/issues/226).
