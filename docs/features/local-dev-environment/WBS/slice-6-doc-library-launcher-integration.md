# Slice 6 — `doc-library`: local-dev launcher integration

> Part of the `local-dev-environment` feature. PRD: [`../PRD.md`](../PRD.md) · Technical design:
> [`../TDD.md`](../TDD.md)

**Delivers:** A developer runs `uv run python scripts/local_dev.py --apps doc-library` (or with no
`--apps` filter, alongside any other checked-out app), logs in once, and sees `doc-library` render
with a real, server-synced cross-app sidebar nav — same pattern as Slice 4's `event-creator`
integration, proving the pattern generalizes to an app with no third-party integrations at all.

## What to build

Identical shape to [Slice 4](slice-4-event-creator-launcher-integration.md), applied to
`doc-library`:

- `doc-library/scripts/dev.py` (new): `uv run uvicorn app.main:app --reload` + CSS watcher, port
  from `PORT`.
- `doc-library`'s `Settings` gains `registry_local_dev_bypass: bool = False` (read from
  `REGISTRY_LOCAL_DEV_BYPASS`) and reads `registry_host_url` from `REGISTRY_HOST_URL` when the
  flag is set — both environment variables already set generically by `organize-me`'s launcher for
  any non-Host app (Slice 2), no launcher change needed. `registry_client.py`'s `_refresh_loop`
  selects `build_local_dev_token_provider()` the same way `event-creator`'s does.
- Companion change (separate tiny PR in `organize-me`, not part of this slice's own repo work):
  `infra/local_dev/ports.py` gains one entry, `"doc-library": 8002`.
- `doc-library`'s `README.md` gets a pointer to the Host's "Local development" doc section.

No `mock_integrations` work — `doc-library` has no third-party integration to mock (confirmed in
the PRD and TDD).

## Design notes

Same ADRs as Slice 4:
[`local-dev-environment-registry-sync-auth-bypass.md`](../../../adr/local-dev-environment-registry-sync-auth-bypass.md)
and
[`local-dev-environment-launcher-orchestration-boundary.md`](../../../adr/local-dev-environment-launcher-orchestration-boundary.md).
This slice is a close-to-mechanical repeat of Slice 4's pattern applied to a second consumer — the
main thing worth double-checking during implementation is that nothing about Slice 4's `event-
creator`-specific wiring accidentally leaked into a shared/generic place instead of staying
per-app, per the orchestration-boundary ADR's decision.

## Blocked by

- [Slice 2](slice-2-launcher-and-proxy-host-only.md) — needs the launcher/Caddy proxy to exist.
- [Slice 3](slice-3-registry-bypass-host-side.md) — needs the Host-side bypass to exist.

Independent of Slices 4/5 — can be implemented in parallel with either.

## Acceptance criteria

- [ ] `uv run python scripts/local_dev.py --apps doc-library` starts the Host, `doc-library`, and
      Caddy.
- [ ] Logging in via `http://localhost:10000/login` and navigating to a `doc-library` page works
      without a second login, with real registry-synced cross-app nav (not the `SELF_APP_ENTRY`
      fallback).
- [ ] `DOC_LIBRARY_REPO_PATH` (or equivalent) correctly overrides the sibling-directory default.
- [ ] Running `scripts/local_dev.py` with no `--apps` filter starts every hosted app repo actually
      present on disk, `doc-library` included, without needing to be named explicitly.
- [ ] `doc-library`'s own test suite still passes with `registry_local_dev_bypass` unset/`False`.

## Testing

Same shape as Slice 4: a direct test of `doc-library`'s consumer-side bypass selection
(`registry_host_url` override, token-provider selection), plus manual verification of the
end-to-end nav-rendering acceptance criteria above.

<!-- /to-implementation appends a "## Delivered" section here once this slice ships. -->
