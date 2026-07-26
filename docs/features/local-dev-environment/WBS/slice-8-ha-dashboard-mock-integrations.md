# Slice 8 — `ha-dashboard`: `mock_integrations` flag

> Part of the `local-dev-environment` feature. PRD: [`../PRD.md`](../PRD.md) · Technical design:
> [`../TDD.md`](../TDD.md)

**Delivers:** A developer without a real Home Assistant instance reachable from their machine can
run `ha-dashboard` locally with `MOCK_INTEGRATIONS=true` and see dashboard tiles actually render,
using the existing test-only `FakeHATransport` promoted into application code.

## What to build

Add `mock_integrations: bool = False` to `ha-dashboard`'s `Settings`.

`ha-dashboard`'s HA-transport selection is currently a bare constructor default
(`transport_factory: HATransportFactory = WebSocketsHATransport`), not a settings-driven choice.
Build a new `build_ha_transport_factory(settings) -> HATransportFactory` function that returns the
fake transport when `settings.mock_integrations` (or `settings.e2e_test_mode`, if that flag exists
in this app) is true, the real `WebSocketsHATransport` otherwise. Wire it in wherever the transport
factory is currently constructed/injected.

Promote `FakeHATransport` out of `ha-dashboard`'s own test suite into application code (e.g.
alongside where `event-creator`'s other fakes already live under `app/services/`), so it's
importable and selectable outside of tests. Update the test suite's own usage to import it from its
new location rather than maintaining two copies.

## Design notes

Full rationale in
[`docs/adr/local-dev-environment-mock-integrations-flag.md`](../../../adr/local-dev-environment-mock-integrations-flag.md).
This is the one app in this feature where the HA-transport selection point doesn't already exist
as a settings-driven factory — most of this slice's work is building that seam, not just adding a
flag to an existing branch, unlike Slice 5's storage/Gemini clauses in `event-creator`.

## Blocked by

- [Slice 7](slice-7-ha-dashboard-launcher-integration.md) — needs `ha-dashboard` running via the
  local launcher before its mocked dashboard tiles are viewable end-to-end.

## Acceptance criteria

- [ ] `build_ha_transport_factory(settings)` returns `FakeHATransport` when
      `mock_integrations=True`, the real `WebSocketsHATransport` otherwise — verified directly, not
      just manually.
- [ ] With `mock_integrations` unset, behavior is unchanged from before this slice (real transport,
      same default as today).
- [ ] Manually running `ha-dashboard` locally via the launcher with `MOCK_INTEGRATIONS=true` and no
      real Home Assistant instance reachable renders dashboard tiles with fake data, rather than a
      connection-failed state.

## Testing

Mirrors `event-creator`'s `E2E_TEST_MODE`-driven fake-provider tests (Slice 5's prior art): a
direct test of `build_ha_transport_factory()` asserting it returns the fake implementation when
`mock_integrations` is set and the real implementation otherwise. The promoted `FakeHATransport`'s
existing test-suite usages continue to pass, now importing from its new application-code location.

<!-- /to-implementation appends a "## Delivered" section here once this slice ships. -->
