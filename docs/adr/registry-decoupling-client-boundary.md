# Keep the registry fetch/cache client a leaf module with no self-scheduling

**Status:** Proposed
**Date:** 2026-07-18
**Feature:** [`registry-decoupling`](../features/registry-decoupling/TDD.md)

## Context

`organizeme_chrome` today is deliberately free of `Request`/DB/network coupling in its core
modules: `nav_groups.py`'s combine logic is pure (per
[`sidebar-nav-groups-render-boundary`](sidebar-nav-groups-render-boundary.md)), and `jwt_verify.py`
does signature/expiry checks only, no network call. This PRD adds a genuinely new kind of
dependency to the package: an HTTP client, a background refresh loop, mutable process-global cache
state, and (for consumers other than the Host) GCP-specific OIDC token minting via the metadata
server.

Two questions forced a decision: (1) where does this new code live relative to the package's
existing pure modules, and (2) does the background refresh loop itself live inside the package
(self-starting) or does the package only do the fetching, with each consumer's own app owning the
scheduling?

## Decision

1. **Split into a `RegistrySource` protocol + two implementations, not an if-branch.**
   `organizeme_chrome/registry.py` keeps `list_apps()`/`get_app()` as pure reads against a
   `RegistrySource` (`get_apps() -> list[AppEntry]`) — zero I/O, same testability as today. Two
   concrete sources exist: `InProcessRegistrySource` (the Host wraps its own in-app `APPS` list in
   this, no network) and `FetchedRegistrySource` (every other consumer wraps the background-swapped
   cache in this, falling back to a cold-start self-only default). Each app calls a
   `configure_registry_source()` once at startup; `list_apps()`/`get_app()` read whichever source
   was configured. This keeps the Host's in-process path and every other consumer's HTTP-backed path
   as two honest implementations of one interface, not one function lying about where the data
   actually comes from.

2. **New HTTP/GCP code lives in a new leaf module, `organizeme_chrome/registry_client.py`,
   imported by nothing else in the package.** `templating.py`, `nav_groups.py`, and `jwt_verify.py`
   stay import-clean of `httpx`/`asyncio`/`google.auth` — a caller that only needs template
   rendering (or `generate_url_map.py`, which explicitly stays network-free per this feature's own
   PRD) never transitively pulls in an HTTP stack.

3. **The module exposes a pure, awaitable `fetch_registry_once(client, host_url, token_provider)`,
   not a self-starting background task.** Each consumer's own `lifespan` owns the
   `while True: sleep(interval)` loop, spawns the `asyncio.Task`, stores it on `app.state`, and
   cancels it on shutdown. `token_provider` is an injected `Callable[[], Awaitable[str]]` — the
   default implementation calls `google.oauth2.id_token.fetch_id_token` via `asyncio.to_thread`
   (it's blocking), but the package's own tests inject a fake, keeping `registry_client.py` itself
   free of a hard GCP dependency in its test suite.

## Alternatives considered

- **A single `list_apps()` with an `if is_host: ... else: ...` branch reading either the literal
  or the cache directly.** Rejected: this is the "lying abstraction" PRD user story 6 explicitly
  warns against — two genuinely different data sources masquerading as one function's internal
  conditional, harder to test in isolation, and it couples `registry.py` to knowing about HTTP
  fetching at all.
- **A separate `organizeme-chrome-client` package/distribution**, fully isolating the network code
  from the templating/theme code. Rejected as over-engineering for three consumers — the leaf-module
  split inside the existing package achieves the same import-cleanliness without a second package
  to version and release.
- **Self-starting background task inside the package** (the package spawns its own
  `asyncio.create_task` on first `list_apps()` call or via a package-level `init()`). Rejected: this
  silently assumes every consumer runs under a compatible event loop/lifespan, is harder to unit
  test without spinning up real asyncio infrastructure inside the package's own test suite, and
  couples a shared library to FastAPI's lifespan protocol specifically — a future non-FastAPI
  consumer (unlikely today, but not ruled out) would have no clean way to opt out of the
  self-scheduling.

## Consequences

- Each consumer repo carries a small (a few lines) duplicated scheduling loop in its own
  `lifespan` — an accepted, existing trade-off pattern on this platform (the same shape
  `nav_groups()`'s per-consumer call sites already accept, per the render-boundary ADR).
- `packages/chrome/tests/` can unit-test `fetch_registry_once` and the `RegistrySource`
  implementations with `httpx.MockTransport` and a fake `token_provider`, with no real network,
  timers, or GCP credentials — matching the PRD's Testing Decisions section.
- A future consumer that isn't FastAPI (or doesn't want a background loop at all — e.g. a one-shot
  CLI script) can still call `fetch_registry_once` directly without inheriting scheduling machinery
  it doesn't want.
