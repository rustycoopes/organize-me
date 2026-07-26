# Slice 3 — Registry-sync local-dev bypass: Host side

> Part of the `local-dev-environment` feature. PRD: [`../PRD.md`](../PRD.md) · Technical design:
> [`../TDD.md`](../TDD.md)

**Delivers:** The Host can serve its real `GET /internal/app-registry.json` endpoint to an
unauthenticated local caller when explicitly configured to, with a boot-time crash guarding
against that configuration ever being live on real Cloud Run infra. No developer-visible effect
on its own yet — this is the Host half of the fix; Slice 4 is the first consumer that actually
exercises it.

## What to build

Add `registry_local_dev_bypass: bool = False` to the Host's `Settings`
(`app/core/config.py`). In `app/api/internal/registry.py`'s `_verify_registry_read_token`, check
`settings.registry_local_dev_bypass` first, before reading any `Authorization` header, and return
immediately (no exception) if true.

Add a startup guard (Host's own startup path, e.g. `app/main.py`'s lifespan/startup hook): if
`registry_local_dev_bypass` is true while the `K_SERVICE` environment variable is present (Cloud
Run's own signal, never present locally), raise — converting "bypass left on in a real deployment"
into a boot-time crash rather than a silently reopened unauthenticated-read hole.

## Design notes

Full rationale, alternatives considered, and severity assessment:
[`docs/adr/local-dev-environment-registry-sync-auth-bypass.md`](../../../adr/local-dev-environment-registry-sync-auth-bypass.md).
Key constraint from the ADR: the bypass is evaluated *only* from the Host's own configuration,
never from anything a caller claims about itself. This setting is set by the launcher as a
subprocess environment variable (wired in Slice 4, the first consumer) — never hand-added to a
developer's own `.env.local`.

## Blocked by

None — independent of Slice 2 (no dependency on the launcher or Caddy existing), though it has no
observable effect until Slice 4 wires up a consumer.

## Acceptance criteria

- [ ] `registry_local_dev_bypass` defaults to `False`; existing OIDC-verification behavior is
      unchanged when it's unset.
- [ ] With `registry_local_dev_bypass=True`, `GET /internal/app-registry.json` succeeds with no
      `Authorization` header.
- [ ] With `registry_local_dev_bypass=True` **and** `registry_endpoint_url`/
      `registry_invoker_service_account` populated, the bypass is inert — the real OIDC check still
      runs — so the two states can never both be "on" at once.
- [ ] Host startup raises if `registry_local_dev_bypass=True` while `K_SERVICE` is set in the
      environment.

## Testing

Direct test of `_verify_registry_read_token` asserting (a) it short-circuits when
`registry_local_dev_bypass` is true and no token is present, and (b) it's inert — falls through to
the real OIDC check — whenever `registry_endpoint_url`/`registry_invoker_service_account` are
populated. Mirrors `tests/test_internal_registry.py`'s existing structure. A second test asserts
the startup guard raises when `registry_local_dev_bypass=True` and `K_SERVICE` is set.

<!-- /to-implementation appends a "## Delivered" section here once this slice ships. -->
