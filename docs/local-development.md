# Local development: running the platform locally, no Docker

Part of the [`local-dev-environment`](features/local-dev-environment/PRD.md) feature. This is the
Host's own doc; each hosted app's own README links back here rather than duplicating it.

The Host and every hosted app run as plain local processes (`uv run uvicorn --reload` + a CSS
watcher) behind a shared local reverse proxy, so cross-app nav links, the shared SSO cookie, and
static assets all behave the same way locally as they do in QA/prod — no containers involved
anywhere in this design.

## Installing Caddy (one-time)

The local reverse proxy is [Caddy](https://caddyserver.com/), a single static binary:

```bash
winget install CaddyServer.Caddy   # Windows
brew install caddy                 # macOS
```

Confirm it's on `PATH`: `caddy version`.

## Running it

From `organize-me`:

```bash
uv run python scripts/local_dev.py
```

With no other hosted apps checked out yet, this starts just the Host plus Caddy, bound to
`http://localhost:10000` (the shared local origin — see
`infra/local_dev/ports.py`'s `CADDY_LOCAL_PORT`, overridable via a `CADDY_LOCAL_PORT` environment
variable if something else already owns `:10000`). Once Caddy is up, the launcher opens it in
your default browser automatically — use that origin, not an individual app's own bare port
(e.g. `:8000`), since only Caddy knows how to route every onboarded app's paths (a bare-port tab
404s on any cross-app nav link). Log in at
`http://localhost:10000/login` exactly as you would against `http://localhost:8000` directly —
the Host's own pages, static assets, and auth cookie all route through the proxy identically.

Once a hosted app has been onboarded into local dev (its own `scripts/dev.py` plus a
`ports.py` entry — see below), start it alongside the Host with `--apps`:

```bash
uv run python scripts/local_dev.py --apps event-creator
```

With no `--apps` given, every onboarded app whose repo the launcher can find on disk (the sibling-
directory convention below) is started automatically.

Each subprocess's output is relayed to this one terminal with a `[service-name]` prefix. **Ctrl-C**
terminates every child process, including Caddy — including whatever grandchild processes each
app's own `scripts/dev.py` spawned (`uvicorn --reload`'s own supervisor process, the CSS watcher),
so a second run immediately after doesn't hit a port-in-use error from a leftover process.

### Repo discovery

Non-Host apps are found next to `organize-me` by convention (`../event-creator`, `../doc-library`,
`../ha-dashboard`). Point at a different checkout — e.g. a git worktree holding an in-progress
branch — with a per-app environment variable:

```bash
EVENT_CREATOR_REPO_PATH=/path/to/a/worktree uv run python scripts/local_dev.py --apps event-creator
```

### Errors

A missing `caddy` binary or a port already bound (e.g. something else already listening on `:8000`
or `:10000`) surfaces as a clear, labeled error rather than a raw traceback — a busy port fails
only that one app's startup; everything else still starts.

### `mock-integrations`

A future addition (landing with Slices 5/8): a flag selecting each onboarded app's fake
third-party integrations (Gemini, Twilio, storage, Home Assistant) instead of the real ones, so
local dev never needs real credentials or makes real external calls for pages that don't
specifically exercise them. Not yet available as of this slice.

## Adding a new app to local dev

Onboarding an app (its own local-dev integration slice) needs, in `organize-me`:

- One entry in `infra/local_dev/ports.py`'s `PORTS` mapping (`"<service-name>": <port>`) — the
  only change needed here; `scripts/local_dev.py` and `infra/local_dev/generate_caddyfile.py`
  need no code change for a new app, since both are already pure functions of the whole
  app-registry plus this port map.

And in that app's own repo:

- Its own `scripts/dev.py`, matching the shape of `organize-me/scripts/dev.py` (uvicorn --reload +
  CSS watcher, port from the `PORT` environment variable).
- A `registry_local_dev_bypass` setting (once the registry-sync bypass, Slice 3, exists) so its
  registry-fetch trusts the launcher's already-injected `REGISTRY_HOST_URL` instead of requiring
  real OIDC credentials.

See
[`docs/adr/local-dev-environment-launcher-orchestration-boundary.md`](adr/local-dev-environment-launcher-orchestration-boundary.md)
and
[`docs/adr/local-dev-environment-local-reverse-proxy.md`](adr/local-dev-environment-local-reverse-proxy.md)
for the full design.
