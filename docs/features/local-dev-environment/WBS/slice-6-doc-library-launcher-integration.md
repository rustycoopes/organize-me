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

## Delivered (2026-07-26, issue doc-library#32, branch `feature/local-dev-launcher-integration`)

Shipped as designed: `doc-library/scripts/dev.py` (byte-identical in shape to `organize-me`'s own
`scripts/dev.py`); `registry_local_dev_bypass: bool = False` on doc-library's `Settings`
(`app/core/config.py`); `app/core/registry.py`'s `_refresh_loop` now branches on that flag,
selecting a new `_build_local_dev_token_provider()` (a constant placeholder string, no
metadata-server round trip) instead of the existing `_instrumented_token_provider(build_default_
token_provider(...), ...)` when it's true; `README.md` points at `organize-me`'s "Local
development" doc. `registry_host_url` needed no code change — it already reads unconditionally
from `REGISTRY_HOST_URL`, which the launcher sets to the Host's local port the same way CI/deploy
already set it to the real QA/prod Host URL. The companion `infra/local_dev/ports.py` entry
(`"doc-library": 8002`) shipped separately, direct to `organize-me`'s `main`, ahead of this PR.

End-to-end verified manually (this dev machine has no local Postgres, so the DB-backed half of
doc-library's own suite couldn't run locally — confirmed instead that CI, which does have QA
Supabase access via secrets, exercises those unaffected): started `organize-me`'s Host directly
with `REGISTRY_LOCAL_DEV_BYPASS=true` on an alternate port and doc-library with
`REGISTRY_LOCAL_DEV_BYPASS=true`/`REGISTRY_HOST_URL` pointed at it (equivalent to what
`scripts/local_dev.py` injects, done this way to avoid colliding with another already-running
local-dev session on the default ports) — confirmed the Host's `/internal/app-registry.json`
served unauthenticated, and doc-library's refresh loop logged `freshly-refreshed (4 apps)` within
its first attempt, proving it received the real multi-app registry rather than staying on its
1-entry `SELF_APP_ENTRY` cold-start default. Separately confirmed `DOC_LIBRARY_REPO_PATH`
correctly redirects `scripts/local_dev.py`'s `resolve_repo_path()`/`_discoverable_non_host_
services()` to an alternate checkout (this issue's own worktree, which the sibling-directory
default doesn't have `scripts/dev.py` on yet) and that doc-library is auto-discovered with no
`--apps` flag once that override is set — both by calling those functions directly against the
override env var, the same code path `scripts/local_dev.py --apps doc-library` itself uses. Full
Caddy+login UI verification wasn't re-run (Slices 2/3 already cover Caddy routing/SSO-cookie
behavior, unchanged by this diff) and this dev machine's known ARM64 gap (no `pytailwindcss`
windows-arm64 binary) means `scripts/dev.py`'s own CSS-watcher subprocess can't run here — an
existing, unrelated environment limitation, not something this issue introduced.

One divergence from the WBS's literal wording, surfaced by the `code-review-master` review: the
WBS/ADR describe `registry_client.py` gaining `build_local_dev_token_provider()`, which read
literally names the *shared* `organizeme_chrome.registry_client` module. What shipped is a private
`_build_local_dev_token_provider()` local to doc-library's own `app/core/registry.py` instead —
consistent with this file's existing `_instrumented_token_provider` convention, and avoids a
shared-package version-bump/release cycle that neither this issue nor any merged slice budgeted
for (no other consumer app has implemented this yet either, so there's no shared-package
precedent to match). Both reviewing agents agreed this shouldn't block the PR; filed as a
follow-up (doc-library#33, Intake) to promote it to `organizeme_chrome.registry_client` once a
second consumer (`event-creator` Slice 4 or `ha-dashboard` Slice 7) actually needs the same
function, at which point the duplication would cross the threshold that justifies the version
bump.
