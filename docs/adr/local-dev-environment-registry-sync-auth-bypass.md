# Host-controlled local-dev bypass for the registry-fetch OIDC check

**Status:** Proposed
**Date:** 2026-07-25
**Feature:** [`local-dev-environment`](../features/local-dev-environment/TDD.md)

## Context

`GET /internal/app-registry.json`'s `_verify_registry_read_token`
(`app/api/internal/registry.py`) requires a real Google-signed OIDC token and fails closed with a
503 whenever its own `registry_endpoint_url`/`registry_invoker_service_account` settings are
unset — which is local dev's default state. Separately, the consumer side's default token
provider (`registry_client.py::build_default_token_provider`) mints its token via the GCP metadata
server, which isn't reachable off real GCP infrastructure at all.

Net effect, confirmed while designing this feature: **every hosted app running locally today only
ever serves its own single-entry cold-start `SELF_APP_ENTRY` fallback and never actually syncs the
real registry.** Cross-app nav links — one of this feature's headline goals — silently don't work
locally, regardless of the new local reverse proxy, because the mechanism that's supposed to teach
a locally-running `event-creator` about `doc-library`'s and `ha-dashboard`'s nav entries (and vice
versa) never succeeds.

This is a genuinely new problem to solve, not something the PRD's Auth section already covered —
that section is about the user-facing JWT/SSO cookie flow, which needs no change; this is a
separate, machine-to-machine auth path.

## Decision

Add a Host-controlled bypass, evaluated **only from the Host's own configuration**, never from
anything a caller claims about itself:

- A new boolean setting on the Host, `registry_local_dev_bypass` (default `False`). `
  _verify_registry_read_token` checks it *first*, before parsing any `Authorization` header, and
  returns immediately if true.
- A fail-safe guard: at startup, if `registry_local_dev_bypass` is true while Cloud Run's own
  `K_SERVICE` environment variable is present (a reliable signal that this process is actually
  running on Cloud Run, never present locally), the app raises rather than starts — turning "the
  bypass was accidentally left on in a real deployment" into a boot-time crash instead of a
  silently reopened unauthenticated-read hole.
- Each consumer app (`event-creator`, `doc-library`, `ha-dashboard`) gets a matching
  `registry_local_dev_bypass` setting that, when true: (a) points `registry_host_url` directly at
  the Host's local port rather than through the local Caddy proxy — mirroring how this same value
  already bypasses the real Load Balancer in QA/prod for the identical server-to-server reason —
  and (b) selects a new trivial token provider (a constant placeholder string, no metadata-server
  call) in place of `build_default_token_provider`, using `registry_client.py`'s existing
  `token_provider` injection seam (already exercised by that package's own tests).
- All of these flags are set by the local-dev launcher itself, as subprocess environment
  variables — never hand-added to a developer's own `.env.local` — so a plain `uv run uvicorn`
  invocation started outside the launcher never accidentally gets the bypass.
- A dedicated test asserts the bypass is inert whenever the real OIDC settings
  (`registry_endpoint_url`/`registry_invoker_service_account`) are populated, so the two states can
  never both be "on" at once.

## Alternatives considered

- **A separate, unauthenticated endpoint for local dev** (e.g.
  `/internal/app-registry-local.json`). Keeps the real endpoint's code path completely untouched,
  lowering the risk of the bypass ever executing for real traffic. Rejected as the primary
  approach: it forks the route and its response-shaping (`_APPS_ADAPTER.dump_json(APPS)`) into two
  implementations that must stay in sync, and pushes an "is this local dev" branch out to every
  consumer's own fetch call site instead of one place.
- **Bypassing the network fetch entirely** — the local launcher assembles/injects the full
  registry directly into each started process instead of exercising the real HTTP fetch. Rejected
  as the primary approach: it means local dev never exercises the real background-refresh/cache
  mechanism (`FetchedRegistrySource`, `_refresh_loop`) — new, central infrastructure to this
  platform's own nav/SSO trust story — so a regression there could ship undetected until QA,
  undercutting one of this feature's core value props (catching integration issues before a QA
  deploy).
- **Requiring real `gcloud` Application Default Credentials configured locally**, so the existing
  OIDC flow works completely unmodified. Rejected as the primary path: reintroduces exactly the
  cloud-tooling dependency this feature exists to remove. Nothing in this decision prevents a
  developer who already has ADC configured from leaving the bypass off and using the real flow
  instead — the bypass is opt-in via the new flag, not the only supported path.

## Consequences

- This is a genuine, if narrow, new local-dev-only relaxation of an existing auth-enforcing code
  path — accepted because the data behind it (nav labels, path prefixes, settings-tab labels) is
  already visible in any logged-in user's rendered sidebar HTML today; the realistic worst case of
  the bypass firing somewhere it shouldn't is low-severity routing-structure disclosure, not a
  credential or PII leak.
- The `K_SERVICE` guard converts the highest-severity failure mode (bypass silently active in a
  real deployment) into a boot-time crash rather than a silent hole.
- Every consumer needs its hard-coded "where's the Host" configuration to gain a local override
  pointing at the Host's *local* port — without this, a consumer could silently fetch the real
  QA Host's registry while the developer believes they're testing fully locally. This wiring is
  needed regardless of which alternative above had been chosen instead.
