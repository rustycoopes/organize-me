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

## Delivered (2026-07-26, issue #266, branch `feature/registry-local-dev-bypass-host`)

Shipped as designed: `registry_local_dev_bypass: bool = False` on the Host's `Settings`
(`app/core/config.py`); `_verify_registry_read_token` (`app/api/internal/registry.py`) checks it
before parsing any `Authorization` header and short-circuits with a `logger.warning` when true;
`app/main.py`'s `lifespan` calls a new `_reject_registry_bypass_on_cloud_run` before `yield`,
raising `RuntimeError` if the bypass is on while `K_SERVICE` is set.

One refinement beyond the WBS's literal wording, surfaced during the code-review pass
(`code-review-master` + `code-quality-guardian`, both independently flagged it): the bypass's
inertness condition uses `registry_endpoint_url OR registry_invoker_service_account` (either one
populated disables the bypass), not `AND`. Firing only when *both* are still empty is stricter
than "inert once populated" read literally as an AND - a half-migrated deployment with just one
of the two settings set now still fails closed (503 `not_configured`) exactly as it would with the
bypass off, rather than silently serving an unauthenticated read. Added
`test_local_dev_bypass_is_inert_when_only_one_oidc_setting_is_populated` (parametrized over both
settings) plus `test_local_dev_bypass_does_not_affect_a_valid_token_when_oidc_settings_are_populated`
to `tests/test_internal_registry.py` to pin this down; `tests/test_main_startup.py` is new,
covering the three meaningful `(registry_local_dev_bypass, K_SERVICE)` combinations for the
startup guard directly.

A lower-priority follow-up (a lifespan-level integration test for the startup guard, since the
current tests call `_reject_registry_bypass_on_cloud_run` directly rather than booting the real
ASGI app) was filed as issue #271 rather than done here.
