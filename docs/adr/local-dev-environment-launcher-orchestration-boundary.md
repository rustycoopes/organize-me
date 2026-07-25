# Local-dev launcher stays a pure orchestrator; each app owns its own start command

**Status:** Proposed
**Date:** 2026-07-25
**Feature:** [`local-dev-environment`](../features/local-dev-environment/TDD.md)

## Context

The PRD wants one command to start the Host plus a chosen subset of hosted apps locally, each
running its own dev server (`uv run uvicorn --reload`) and CSS watcher (`scripts/build_css.py
--watch`) as plain subprocesses (no Docker). The natural home for this orchestrator is
`organize-me`, the one repo that already authors the canonical app-registry
(`app/core/registry.py`) and generates real routing from it. But a launcher that starts other
repos' processes needs to decide *how much* it knows about those repos: just where they live and
what port to use, or the literal command line to run them.

## Decision

Each app repo — `organize-me` included, for symmetry — gets its own conventional
`scripts/dev.py` that declares how to start *itself* for local dev (its own `uvicorn --reload` +
CSS-watcher invocation, reading its port from an environment variable/CLI argument). The Host's
new orchestrator (`scripts/local_dev.py`) only handles: discovering each selected app's repo path
(sibling-directory convention, with a per-app override for worktrees), looking up its assigned
local port, invoking that repo's own `scripts/dev.py` as a subprocess, generating/starting the
local Caddy proxy, and multiplexing/color-coding every subprocess's output. The orchestrator never
hardcodes another repo's literal run command.

## Alternatives considered

- **A monolithic launcher that hardcodes each app's start command** (e.g. `uv run uvicorn
  app.main:app --reload --port {port}` plus `uv run python scripts/build_css.py --watch`, looked
  up by app name). Rejected: any app changing its own dev-server invocation — a different ASGI
  server, an extra watcher process, a changed CLI flag — silently breaks the shared launcher until
  someone remembers to update `organize-me` too. This coupling is worse than the registry's own:
  the registry only declares what an app *owns* (its routes), never *how it runs*.

## Consequences

- Onboarding app #4 into local dev means adding its own `scripts/dev.py` (a file it needs the shape
  of anyway) plus one entry in the Host's port-mapping config — no changes to the orchestrator's
  code itself. This should be folded into `how-to-add-a-hosted-app.md`'s checklist.
- Minor duplication: every app repo carries a near-identical `scripts/dev.py`
  (uvicorn-plus-CSS-watcher boilerplate) — the same order of duplication `build_css.py` already
  tolerates across repos today, and preferable to the coupling the rejected alternative would add.
