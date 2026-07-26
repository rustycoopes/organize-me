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

## Delivered (2026-07-26, issue ha-dashboard#18, branch `feature/local-dev-launcher-integration`)

Shipped as designed: `ha-dashboard/scripts/dev.py` (new, mirrors organize-me's own), `Settings.
registry_local_dev_bypass: bool = False` (read from `REGISTRY_LOCAL_DEV_BYPASS`), and
`app/core/registry.py`'s `_refresh_loop` selecting `organizeme_chrome.registry_client.
build_local_dev_token_provider()` instead of the real OIDC provider when the flag is true.
`registry_host_url` needed no separate override code - the launcher already injects
`REGISTRY_HOST_URL` generically (Slice 2), and `Settings` already read that field for the
QA/prod Load-Balancer-bypass case.

Two companion changes landed in `organize-me` ahead of this repo's own PR, since `build_local_dev_
token_provider()` didn't exist yet in `organizeme_chrome.registry_client` (event-creator/doc-
library's Slice 4/6 were still in flight in parallel, so this is the first of the three consumer
slices to add it to the shared package rather than a private copy):

- #273 — adds `build_local_dev_token_provider()` to `packages/chrome` + the `"ha-dashboard": 8003`
  `infra/local_dev/ports.py` entry (`chrome-v0.19.0`).
- #274 — a code-review-master pass caught a dead-code duplicate `return _provider` statement left
  over from #273's edit (harmless - the function already returns on the first `return`, no
  functional bug); fixed as a clean patch release (`chrome-v0.19.1`), which `ha-dashboard`'s PR
  pins to directly rather than the short-lived `chrome-v0.19.0`.

One test-shape refinement beyond the WBS's literal wording, surfaced during the code-review pass
(`code-review-master` + `code-quality-guardian`, both independently flagged the same thing): the
first draft of the two bypass-selection tests monkeypatched `build_local_dev_token_provider` itself
away to a sentinel object, which was unnecessary over-mocking of a real, pure, I/O-free function.
Rewritten to mirror doc-library's identical Slice 6 tests instead - drive the real
`start_registry_refresh_task`, capture whichever token provider actually got passed to a faked
`fetch_registry_once`, and assert on the actual token string returned by `await token_provider()`,
only faking `build_default_token_provider` (the one that genuinely needs an unreachable GCP
metadata server). The review also flagged an initial `_build_token_provider` helper extracted out
of `_refresh_loop` as an unnecessary structural divergence from doc-library's identical slice
(which kept the bypass `if`/`else` inline) - reverted to match.

`ha-dashboard`'s own DB-backed test suite couldn't be run end-to-end in this session's local dev
environment (a pre-existing Supabase-pooler connectivity issue, confirmed present on unmodified
`main` too and unrelated to this change) - relied on this repo's own CI (throwaway Postgres
container) for that coverage instead, plus manual verification that `scripts/dev.py` boots cleanly
and that the bypass path reaches a real Host process over HTTP without ever calling google-auth's
metadata server.
