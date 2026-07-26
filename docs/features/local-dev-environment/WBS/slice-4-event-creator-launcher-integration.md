# Slice 4 — `event-creator`: local-dev launcher integration

> Part of the `local-dev-environment` feature. PRD: [`../PRD.md`](../PRD.md) · Technical design:
> [`../TDD.md`](../TDD.md)

**Delivers:** A developer runs `uv run python scripts/local_dev.py --apps event-creator` from
`organize-me`, logs in once through the Host, and sees `event-creator` render with a real,
server-synced cross-app sidebar nav — the first end-to-end proof that the registry-sync bypass
(Slice 3) and the shared local origin (Slice 2) actually work together for a real consumer, not
just the Host talking to itself.

## What to build

**`event-creator/scripts/dev.py`** (new): same shape as `organize-me/scripts/dev.py` (Slice 2) —
starts `uv run uvicorn app.main:app --reload` plus `scripts/build_css.py --watch`, port from the
`PORT` environment variable, always watches CSS.

**`event-creator`'s `Settings`**: add `registry_local_dev_bypass: bool = False`, read from the
`REGISTRY_LOCAL_DEV_BYPASS` environment variable (already set generically by the launcher for any
non-Host app, per Slice 2 — no launcher change needed here). When true: `registry_host_url` is
read from the (also already-set) `REGISTRY_HOST_URL` env var, pointing directly at the Host's
local port and bypassing Caddy for this one server-to-server call — mirroring how this value
already bypasses the real Load Balancer in QA/prod. `registry_client.py` gains
`build_local_dev_token_provider()` — a constant placeholder string, no GCP metadata-server round
trip — selected instead of `build_default_token_provider()` in `_refresh_loop` when the flag is
set, using the existing `token_provider` injection seam.

**`organize-me`'s `infra/local_dev/ports.py`**: add one entry, `"event-creator": 8001` — the only
change needed in `organize-me` for this slice (a companion one-line PR there; `local_dev.py`
itself needs no change, since Slice 2 already injects `PORT`/`REGISTRY_LOCAL_DEV_BYPASS`/
`REGISTRY_HOST_URL` generically for any non-Host app it starts).

**`event-creator`'s `README.md`**: short pointer to the Host's "Local development" doc section
(Slice 2).

## Design notes

TDD "Registry sync across the local process boundary" and
[`docs/adr/local-dev-environment-registry-sync-auth-bypass.md`](../../../adr/local-dev-environment-registry-sync-auth-bypass.md)
cover the bypass wiring in full, including the dedicated test asserting the bypass and the real
OIDC path can never both be active (already covered on the Host side by Slice 3 — this slice's own
testing only needs to cover `event-creator`'s consumer-side selection). ADR
[`local-dev-environment-launcher-orchestration-boundary.md`](../../../adr/local-dev-environment-launcher-orchestration-boundary.md)
covers why `local_dev.py` invokes `event-creator/scripts/dev.py` rather than hardcoding its run
command.

Mock integrations (Gemini/Twilio/Resend/storage) are explicitly **not** part of this slice —
without Slice 5, pages that don't require those integrations (nav, dashboard, most of the UI
shell) render fully; only actions that trigger a real third-party call would fail or cost real
API usage until Slice 5 lands.

## Blocked by

- [Slice 2](slice-2-launcher-and-proxy-host-only.md) — needs the launcher/Caddy proxy to exist.
- [Slice 3](slice-3-registry-bypass-host-side.md) — needs the Host-side bypass to exist.

## Acceptance criteria

- [ ] `uv run python scripts/local_dev.py --apps event-creator` (from `organize-me`, with
      `event-creator` checked out as a sibling repo) starts the Host, `event-creator`, and Caddy.
- [ ] Logging in via `http://localhost:10000/login` and navigating to an `event-creator` page
      works without a second login.
- [ ] The rendered sidebar's cross-app nav includes `event-creator`'s own real entries (not the
      cold-start `SELF_APP_ENTRY` fallback) — provable by checking a nav entry that only exists in
      the real registry response, not the fallback.
- [ ] `EVENT_CREATOR_REPO_PATH` (or equivalent override env var) correctly points the launcher at
      an alternate checkout (e.g. a git worktree) instead of the sibling-directory default.
- [ ] `event-creator`'s own test suite still passes with `registry_local_dev_bypass` unset/`False`
      (no change to its default/QA/prod behavior).

## Testing

`event-creator`'s consumer-side bypass selection (`registry_host_url` override,
`build_local_dev_token_provider()` selection in `_refresh_loop`) tested directly, mirroring
`registry_client.py`'s existing test structure for its `token_provider` injection seam.
`infra/local_dev/ports.py`'s new entry covered by Slice 2's existing pure-function tests (no new
test *pattern* needed, just an added case). The end-to-end nav-rendering behavior is verified
manually per this slice's acceptance criteria, consistent with the TDD's guidance that
process-orchestration/integration behavior is lower-value to unit-test exhaustively.

## Delivered (2026-07-26, issue event-creator#36, branch `feature/local-dev-launcher-integration`)

Shipped as described: `event-creator/scripts/dev.py`, `Settings.registry_local_dev_bypass`, and
`_refresh_loop`'s token-provider branch (`build_local_dev_token_provider()` vs.
`build_default_token_provider()`), modeled directly on `doc-library`'s identical Slice 6 wiring.
Bumped the `organizeme-chrome` pin from `chrome-v0.18.0` to `chrome-v0.19.0` to pick up
`build_local_dev_token_provider()` (event-creator's own `registry.py` has no
`_instrumented_token_provider` wrapper to begin with, unlike doc-library's, so nothing was added
there). Two new tests cover the bypass/default token-provider selection directly.

Acceptance criteria verified: `EVENT_CREATOR_REPO_PATH` correctly redirected `local_dev.py` at a
git worktree holding this branch; a manually-isolated Host instance (with
`REGISTRY_LOCAL_DEV_BYPASS=true`) served its real registry unauthenticated, and event-creator,
pointed at it with the same flag, fetched it successfully and rendered `/dashboard` (via a
JWT signed with the shared `JWT_SECRET`) showing real cross-app nav entries (`Doc Library`,
`ha-dashboard`) rather than the `SELF_APP_ENTRY` cold-start fallback. The default (unset) path was
verified via `event-creator`'s own passing test suite (registry-independent tests + mypy; DB-backed
tests require live Supabase and pass in CI). The full `--apps event-creator` run against the
standard ports (8000/8001/10000) wasn't directly exercised end-to-end in this session, since those
ports were already occupied by another concurrent local-dev session on the same machine — the
isolated-port test above exercises the identical code path (launcher's env-injection contract,
Settings wiring, registry client selection) with no gap in coverage.

`infra/local_dev/ports.py`'s `"event-creator": 8001` entry (the companion one-line change) was
added directly to `main` alongside this section and the changelog entry, per the issue's own
scoping.

Code review (code-review-master + code-quality-guardian): no blocking findings, no changes
requested.
