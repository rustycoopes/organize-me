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
