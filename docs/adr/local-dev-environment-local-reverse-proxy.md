# Caddy as the local stand-in for the GCP Load Balancer, config generated from the app-registry

**Status:** Proposed
**Date:** 2026-07-25
**Feature:** [`local-dev-environment`](../features/local-dev-environment/TDD.md)

## Context

The shared chrome package renders sidebar nav links as paths relative to one shared origin — true
in QA/prod because the GCP External HTTPS Load Balancer path-routes across services, generated
from the app-registry by `infra/gcp_lb/generate_url_map.py`. Locally, each service runs on its own
port with nothing playing the LB's role, so cross-app nav links (and, if unaddressed, static
assets) would silently 404 or hit the wrong service. No Docker is available on the reference
development machine, ruling out a docker-compose-fronting-nginx style solution.

## Decision

Use [Caddy](https://caddyserver.com/) — a single static binary with native Windows support — as
the local reverse proxy, bound to a configurable non-privileged default port (Windows generally
can't bind `:80`/`:443` without elevation). Its configuration is **generated, never hand-
maintained**, by a new script (`infra/local_dev/generate_caddyfile.py`) that reads the same
app-registry data `generate_url_map.py` already reads, plus a new local-dev-only port-mapping
config (`infra/local_dev/ports.py`) giving each app's `service_name` its local port. The pure
path-rule-derivation logic already in `generate_url_map.py`
(`PathRule`/`generate_path_rules`/`_claim_path`/`_prefix_patterns`, including the static-asset
prefix handling from the static-asset-routing feature) is extracted into a provider-neutral
`infra/path_rules.py`, imported by both the GCP generator and the new Caddy generator — so a future
routing-rule bug fix (e.g. the documented GCP wildcard-vs-bare-path gotcha) only has to happen
once, and the two generators can't silently diverge.

The generator is a pure function of the **entire** registry, not the launcher's session-selected
subset — it stays a simple `(registry, port-map) -> Caddyfile` function, matching the existing
generator's own purity and its test suite's style
(`tests/test_url_map_generator.py`: constructed `AppEntry` objects, no real I/O). An app the
developer didn't start that session then surfaces as a clean connection-refused/502 through Caddy,
which is the correct signal, not a gap to work around.

## Alternatives considered

- **Direct multi-port access, no proxy.** Rejected: this is the exact gap the feature exists to
  close — cross-app nav links in the rendered chrome would keep breaking, and the local topology
  would diverge from prod in the one way that actually matters for testing nav/routing changes.
- **A hand-rolled Python ASGI proxy** instead of Caddy. Rejected: would mean hand-maintaining
  forwarding, path-matching, and SSE-streaming (non-buffering) behavior that Caddy already
  provides correctly out of the box, for no benefit over installing one more well-established local
  tool.
- **Adding a `local_port` field to the shared `AppEntry` dataclass** instead of a separate
  port-mapping config. Rejected: `AppEntry` is versioned and distributed via the `organizeme-
  chrome` package and also drives real QA/prod routing — local-only port data has no bearing on
  either and would force a package version bump on every hosted app just to add a new app's local
  port.
- **A session-aware generator** (only emitting rules for apps the developer actually started).
  Rejected: adds a second axis of variability to a function that's meant to stay simple and
  registry-driven; an unstarted app 502ing cleanly through Caddy is already the correct, legible
  behavior.

## Consequences

- Adds one new local dependency (the Caddy binary) each developer installs once.
- Static-asset and API-prefix routing automatically stay in sync with real LB routing, since both
  generators share the same rule-derivation logic.
- Caddy's own path-matching semantics must still be verified directly rather than assumed identical
  to GCP's (the existing generator's `_prefix_patterns()` docstring already documents one
  GCP-specific wildcard gotcha caught in review) — each `PathRule`'s paths should be emitted as
  literal Caddy `path` matchers rather than collapsed into Caddy-specific shorthand.
- `event-creator`'s SSE endpoint (`GET /api/v1/processing-runs/{run_id}/sse`) needs an explicit
  non-buffering directive in the generated Caddyfile, or progress updates will arrive in one lump
  instead of streaming.
