# Slice 7 — `ha-dashboard`: local-dev launcher integration

> Part of the `local-dev-environment` feature. PRD: [`../PRD.md`](../PRD.md) · Technical design:
> [`../TDD.md`](../TDD.md)

**Delivers:** A developer runs `uv run python scripts/local_dev.py --apps ha-dashboard`, logs in
once, and sees `ha-dashboard` render with a real, server-synced cross-app sidebar nav — same
pattern as Slices 4 and 6. Dashboard tiles themselves will show a connection-failed state absent a
real Home Assistant instance until Slice 8 lands — expected and acceptable at this point, since a
developer without HA access can already skip starting `ha-dashboard` at all via `--apps` (no
special-casing needed, since app selection already just omits whatever wasn't listed/found).

## What to build

Identical shape to [Slice 4](slice-4-event-creator-launcher-integration.md), applied to
`ha-dashboard`:

- `ha-dashboard/scripts/dev.py` (new): `uv run uvicorn app.main:app --reload` + CSS watcher, port
  from `PORT`.
- `ha-dashboard`'s `Settings` gains `registry_local_dev_bypass: bool = False` (read from
  `REGISTRY_LOCAL_DEV_BYPASS`) and reads `registry_host_url` from `REGISTRY_HOST_URL` when the
  flag is set — both already set generically by `organize-me`'s launcher for any non-Host app
  (Slice 2), no launcher change needed. Wired the same way as `event-creator`'s otherwise.
- Companion change (separate tiny PR in `organize-me`, not part of this slice's own repo work):
  `infra/local_dev/ports.py` gains one entry, `"ha-dashboard": 8003`.
- `ha-dashboard`'s `README.md` gets a pointer to the Host's "Local development" doc section.

## Design notes

Same ADRs as Slice 4. `ha-dashboard`'s real Home Assistant WebSocket connection is strictly
outbound from that process and is never proxied through Caddy (per TDD, "Local reverse proxy"), so
no WS-upgrade handling is needed in the generated Caddy config for this slice.

`ha-dashboard`'s existing "no QA environment" ADR is a precedent for this app opting out of parts
of the platform's standard environment story declaratively — worth keeping in mind, though nothing
in this slice needs to act on it.

## Blocked by

- [Slice 2](slice-2-launcher-and-proxy-host-only.md) — needs the launcher/Caddy proxy to exist.
- [Slice 3](slice-3-registry-bypass-host-side.md) — needs the Host-side bypass to exist.

Independent of Slices 4/5/6 — can be implemented in parallel with either.

## Acceptance criteria

- [ ] `uv run python scripts/local_dev.py --apps ha-dashboard` starts the Host, `ha-dashboard`,
      and Caddy.
- [ ] Logging in via `http://localhost:10000/login` and navigating to an `ha-dashboard` page works
      without a second login, with real registry-synced cross-app nav.
- [ ] `HA_DASHBOARD_REPO_PATH` (or equivalent) correctly overrides the sibling-directory default.
- [ ] Running `scripts/local_dev.py` with `--apps event-creator` (omitting `ha-dashboard`) starts
      cleanly with no error or special-case needed for the omitted app.
- [ ] `ha-dashboard`'s own test suite still passes with `registry_local_dev_bypass` unset/`False`.

## Testing

Same shape as Slice 4: a direct test of `ha-dashboard`'s consumer-side bypass selection, plus
manual verification of the end-to-end nav-rendering acceptance criteria above.

<!-- /to-implementation appends a "## Delivered" section here once this slice ships. -->
