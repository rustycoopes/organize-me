# Registry Decoupling — Technical Design

**Feature:** [`PRD.md`](PRD.md)
**Date:** 2026-07-18
**Status:** Draft

## Architecture at a Glance

- The Host (organize-me) owns the hand-authored `APPS` data in its own app code and serves it from
  a new internal endpoint, `GET /internal/app-registry.json`, authenticated app-level via a
  Google-signed OIDC token (mirroring the existing `/internal/pipeline/run` pattern) — see
  [`registry-decoupling-endpoint-auth`](../../adr/registry-decoupling-endpoint-auth.md).
- `organizeme_chrome` gains a `RegistrySource` protocol: `list_apps()`/`get_app()` become pure
  reads against whichever source each app configures at startup — `InProcessRegistrySource` for
  the Host (no network), `FetchedRegistrySource` for every other consumer (backed by a
  background-refreshed in-memory cache). See
  [`registry-decoupling-client-boundary`](../../adr/registry-decoupling-client-boundary.md).
- The HTTP fetch, OIDC token minting, and cache live in a new leaf module,
  `organizeme_chrome/registry_client.py`, imported by nothing else in the package — `nav_groups.py`,
  `templating.py`, `jwt_verify.py` stay network-free, as does `generate_url_map.py` (unaffected,
  keeps its direct import).
- Each consumer's own `lifespan` owns the refresh loop (spawn on startup, cancel on shutdown) —
  the package exposes only a pure, awaitable `fetch_registry_once()`, never a self-starting task.
- On fetch failure, a consumer keeps serving its last-known-good cache indefinitely (no
  escalation); before any fetch has ever succeeded, it serves a self-only cold-start default
  containing just its own `AppEntry`.
- Migration is per-repo and independent: `organizeme_chrome` keeps a compiled-in fallback for one
  transitional release so an unmigrated consumer doesn't break; the fallback is deleted once all
  three consumers (organize-me, event-creator, doc-library) are confirmed migrated.

## Design Decisions

### Host endpoint shape

New module `app/api/internal/registry.py` in organize-me, sibling in spirit to
`app/api/v1/internal_e2e.py` and event-creator's `app/api/v1/internal_pipeline.py`:

- `router = APIRouter(prefix="/internal", tags=["internal"])`, route `GET /internal/app-registry.json`.
  Not under `/api/v1` — this isn't a public/versioned API surface for any client, matching the
  existing internal-route convention.
- Response body is the current `AppEntry` list serialized via Pydantic v2's native dataclass
  support (`TypeAdapter(list[AppEntry])`, built once at module import, not per-request) — no
  hand-maintained duplicate schema.
- Auth dependency `_verify_registry_read_token` copies `_verify_push_token`'s shape (see
  event-creator's `app/api/v1/internal_pipeline.py`): checks the bearer token's `aud` against the
  Host's own audience URL and `email` against the shared runtime service account, using
  `google.oauth2.id_token.verify_oauth2_token` wrapped in a module-level
  `cachecontrol.CacheControl(requests.Session())`-backed `Request()`. Same error shape: 401
  `missing_token`/`invalid_token`, 403 `wrong_identity`, 503 `not_configured` if settings are
  unset in the current environment (fail closed).
- Full rationale for app-level verification over Cloud Run's IAM invoker gate:
  [`registry-decoupling-endpoint-auth`](../../adr/registry-decoupling-endpoint-auth.md).
- **Flagged, not blocking:** this duplicates `_verify_push_token`'s verification logic across two
  repos (organize-me and event-creator). Factoring a shared helper is left as a follow-up — see
  Open Questions.

### `organizeme_chrome` package structure

- `registry.py` keeps `AppEntry`/`AppNavItem`/`SettingsTab` (unchanged shape) and adds a
  `RegistrySource` protocol (`get_apps() -> list[AppEntry]`). `list_apps()`/`get_app()` become
  thin functions reading whichever source was registered via a new
  `configure_registry_source(source: RegistrySource)`, called once at each app's startup. No
  compiled-in `APPS` literal remains here after the transitional-fallback period (see Rollout
  below).
- `registry_client.py` (new, leaf module) exposes:
  - `async def fetch_registry_once(client: httpx.AsyncClient, host_url: str, token_provider: Callable[[], Awaitable[str]]) -> list[AppEntry]` — pure, awaitable, no scheduling.
  - `class FetchedRegistrySource(RegistrySource)` — holds the current cache (initialized to the
    caller-supplied self-only default), exposes `update(apps: list[AppEntry])` for the consumer's
    own loop to call after each successful fetch. A single reference reassignment
    (`self._apps = new_list`) is atomic under CPython's GIL — no lock needed.
  - A default `token_provider` implementation wrapping
    `google.oauth2.id_token.fetch_id_token` (blocking; called via `asyncio.to_thread`), injectable
    for tests.
- `InProcessRegistrySource(RegistrySource)` lives on the Host's side (organize-me's own app code,
  not the package) — a two-line wrapper around the Host's in-app `APPS` list, registered via
  `configure_registry_source()` at Host startup. No network, no cache.
- Full rationale: [`registry-decoupling-client-boundary`](../../adr/registry-decoupling-client-boundary.md).

### Background refresh loop (per consumer)

Each of event-creator's and doc-library's `lifespan` (both already `asynccontextmanager`-based,
confirmed present in both repos' `app/main.py`) gains a startup half (today both only act on
teardown):

1. Construct `FetchedRegistrySource(self_only_default=<this app's own AppEntry>)`, call
   `configure_registry_source(source)`.
2. Spawn an `asyncio.Task` looping: `await asyncio.sleep(interval)`, then
   `fetch_registry_once(...)`, then `source.update(apps)` on success — log-only on failure (no
   escalation), storing the task on `app.state` for clean cancellation in `lifespan` teardown
   (`task.cancel()` + `contextlib.suppress(asyncio.CancelledError)` around awaiting it).
3. Log lines distinguish three states for operability (per Testing/Observability note below):
   still-on-cold-start-default, freshly-refreshed, and stale-since-`<timestamp>` (serving
   last-known-good after N failed attempts) — so a permanently-misconfigured consumer (wrong
   `HOST_INTERNAL_URL`, Host endpoint never deployed to that environment, wrong `aud`) is
   distinguishable in logs from a transient blip, addressing PRD user story 10.

### Settings additions per consumer

New fields, named to match the existing `pipeline_endpoint_url`-style convention
(event-creator's `app/core/config.py`):

- `registry_host_url: str` — the Host's own per-environment `*.run.app` URL, set as a **plain,
  non-secret env var** in each consumer's `deploy.yml`/CI config (not Secret Manager — see the
  auth ADR's alternatives). Known in advance (the Host already exists in both environments before
  any consumer migrates), so no self-referential post-deploy capture step is needed, unlike
  `PIPELINE_ENDPOINT_URL`.
- `registry_refresh_interval_seconds: float = 60`
- `registry_fetch_timeout_seconds: float = 5`
- Reuse whichever field already names the shared runtime service account's email (event-creator's
  `pipeline_invoker_service_account`-equivalent identity), rather than inventing a new name per
  repo.

doc-library's `app/core/config.py` currently has none of these fields — this is genuinely new
config there, not a rename, since doc-library has no prior internal-endpoint pattern to draw on.

### `generate_url_map.py`

Unaffected — confirmed consistent with this design: it's an operator-run local script, never
inside a live Cloud Run service, and this feature's traffic never touches the Load Balancer at all
(same as `/internal/pipeline/run` — no NEG/backend-service/URL-map change needed anywhere in this
feature).

### Rollout mechanics

- **Within the transitional period**, `organizeme_chrome.registry` keeps today's compiled-in
  `APPS` literal as the default `RegistrySource` an unmigrated consumer implicitly uses if it never
  calls `configure_registry_source()` — preserving today's behavior for any repo mid-migration.
- **Deployment order per environment:** the Host's endpoint slice must deploy to an environment
  before any consumer's fetch-client migration deploys to that *same* environment (QA and prod are
  independent; only same-environment ordering matters).
- **Blast radius of migrating early:** confirmed non-fatal by design — a consumer whose fetches
  never succeed (Host endpoint not yet live in that environment) serves its self-only cold-start
  default indefinitely. Its own nav renders correctly; only other apps' nav/Settings entries are
  missing from its sidebar until the Host's slice deploys there too — never a crash, never blank
  chrome.
- **Decommission step:** once organize-me, event-creator, and doc-library are all confirmed on the
  new fetch-based client, a small follow-up PR deletes the compiled-in `APPS` fallback from
  `organizeme_chrome.registry` entirely (its own WBS slice, per the PRD's Further Notes).

## Component/Data Flow

```mermaid
sequenceDiagram
    participant EC as event-creator (or doc-library)
    participant Cache as FetchedRegistrySource (in-memory)
    participant Loop as background refresh task
    participant Host as organize-me /internal/app-registry.json
    participant Page as EC page handler

    Note over EC,Loop: On startup (lifespan)
    EC->>Cache: configure_registry_source(self-only default)
    EC->>Loop: spawn asyncio.Task

    loop every registry_refresh_interval_seconds
        Loop->>Loop: mint OIDC token (token_provider)
        Loop->>Host: GET /internal/app-registry.json (Bearer <token>)
        alt success
            Host-->>Loop: 200, [AppEntry, ...]
            Loop->>Cache: update(apps)
        else failure (network, 401/403, timeout)
            Loop->>Loop: log failure, keep existing cache
        end
    end

    Note over Page: Any incoming request
    Page->>Cache: list_apps() / get_app() (sync, no I/O)
    Cache-->>Page: current cached AppEntry list
    Page->>Page: build_nav_groups() / flat_nav_items() (pure, unchanged)
```

For the Host itself: `Page->>Cache` resolves against `InProcessRegistrySource` wrapping the
in-app `APPS` list directly — no Loop, no Host round-trip, same diagram minus the top two
lifelines.

## Testing Approach

- **`packages/chrome/tests/`** (pure unit tests, no real network/timers, matching
  `test_registry.py`/`test_nav_groups.py`'s existing style):
  - `fetch_registry_once` against `httpx.AsyncClient(transport=httpx.MockTransport(handler))` with
    a fake `token_provider` — exercises real OIDC header construction against a fake transport.
    Cases: 200 with valid payload, 401/403/5xx, timeout, malformed JSON.
  - `FetchedRegistrySource`: `update()` replaces the cache; `get_apps()` before any `update()`
    returns the constructor-supplied self-only default.
  - `RegistrySource`/`configure_registry_source()`/`list_apps()`/`get_app()` wiring: confirms the
    configured source is what's actually read, for both `InProcessRegistrySource` and
    `FetchedRegistrySource`.
- **Host's endpoint** (organize-me's existing `AsyncClient`-against-`app` test pattern): valid
  shared-SA-signed token → 200 with current registry JSON; missing/invalid/wrong-`aud`/wrong-`email`
  token → 401/403; settings unset → 503. Round-trips through `organizeme_chrome`'s own dataclasses
  on the decode side to confirm the wire shape matches.
- **Per-consumer `lifespan` wiring** (event-creator, doc-library, each in their own repo): a
  focused test that the refresh task starts on app startup and is cancelled on shutdown (no real
  sleep — inject a fake interval or drive the loop directly), plus the existing
  sidebar-rendering page tests (already fixed for the 3-app registry, e.g. event-creator's
  `test_*_page.py` `storedCollapsed` assertions) continue to exercise the rendered chrome
  end-to-end against whatever `RegistrySource` the test fixtures configure.
- **Out of scope for automated coverage:** real Cloud Run-to-Cloud-Run networking, real OIDC
  minting against the live metadata server, and real multi-environment rollout-ordering — these
  are exercised by manual QA verification per environment during implementation, the same way
  the existing `/internal/pipeline/run` push path is verified live rather than in CI.

## Open Questions

1. **Shared OIDC-verification helper.** `_verify_registry_read_token` (Host) and
   `_verify_push_token` (event-creator) will share nearly identical logic across two repos.
   Factor into a common helper now, or accept the duplication and revisit later? Recommend
   deferring — a premature shared package for two call sites, with no clear home (it isn't
   `organizeme_chrome`'s concern, since that package is being kept GCP-agnostic per the
   client-boundary ADR) risks over-engineering ahead of a third real need. `/to-wbs` should flag
   this as a noted-but-deferred item rather than a blocking decision.
2. **Host service recreation risk.** If organize-me's Cloud Run service is ever recreated (not
   redeployed) under a new `*.run.app` suffix, every consumer's `registry_host_url` goes stale
   silently, with no automatic re-discovery under this design. Is a code comment sufficient, or
   does this warrant a lightweight health-check/alert? Recommend a comment only for now (this has
   never happened on this platform), but `/to-wbs` should confirm that's acceptable risk
   tolerance.
3. **Exact log/metric shape for the three refresh states** (cold-start-default /
   freshly-refreshed / stale-since-`<timestamp>`) isn't fully specified here — left for
   `/to-implementation` to match whatever logging convention each consumer repo already uses.
4. **Slice boundaries** — this TDD assumes (per the PRD's Further Notes) four slices: Host
   endpoint + data move, event-creator migration, doc-library migration, and a final
   fallback-decommission slice. `/to-wbs` should confirm that shape or propose a different split
   (e.g. combining the Host slice with the first consumer migration for an end-to-end tracer
   bullet, rather than shipping the Host slice with no live consumer yet).
