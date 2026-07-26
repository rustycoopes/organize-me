# Slice 2 — Local launcher + Caddy proxy, Host-only

> Part of the `local-dev-environment` feature. PRD: [`../PRD.md`](../PRD.md) · Technical design:
> [`../TDD.md`](../TDD.md)

**Delivers:** A developer runs one command (`uv run python scripts/local_dev.py`) and gets the
Host running locally behind a shared local Caddy origin (`http://localhost:10000`), can log in
through the real `/login` flow, and sees Host-owned pages (dashboard, profile, static assets)
render correctly through the proxy — with zero other hosted apps required to be checked out yet.

## What to build

**`organize-me/scripts/dev.py`** (new): starts `uv run uvicorn app.main:app --reload` plus
`scripts/build_css.py --watch`, reading its port from an environment variable (`PORT`, matching
the convention every later app's own `scripts/dev.py` will follow). Always runs the CSS watcher —
no `--no-css-watch` escape hatch (decided at `/to-wbs` time: adds a rarely-needed branch for
little benefit; a developer who wants uvicorn alone can just run it directly instead of via this
script).

**`infra/local_dev/ports.py`** (new): plain Python module mapping `service_name -> int` port,
starting with just `"organizeme": 8000` (the Host's existing default — no change for a
Host-only session) plus a top-level `CADDY_LOCAL_PORT = 10000` constant (overridable via a
`CADDY_LOCAL_PORT` environment variable). Deliberately kept out of the shared `AppEntry`
dataclass — see
[`docs/adr/local-dev-environment-local-reverse-proxy.md`](../../../adr/local-dev-environment-local-reverse-proxy.md).
Each later app-integration slice (4, 6, 7) adds exactly one entry here.

**`infra/local_dev/generate_caddyfile.py`** (new): `generate_caddyfile(apps, ports) -> str`, a
pure function over the *entire* registry (`list_apps()`, not any launcher-session subset) plus the
port map, built on `infra/path_rules.py`'s `generate_path_rules()` (Slice 1). Emits each
`PathRule`'s paths as literal Caddy `path` matchers (not collapsed into Caddy shorthand — Caddy's
wildcard semantics aren't guaranteed identical to GCP's). Includes the Host's own `HOST_PATHS`
routed to `localhost:{ports["organizeme"]}`. An app present in the registry but absent from `ports`
(not yet onboarded into local dev) or not started this session surfaces as a clean
connection-refused/502 through Caddy — correct, not a gap to special-case.

**`organize-me/scripts/local_dev.py`** (new): the orchestrator.
- CLI accepts an optional list of service names (`--apps event-creator doc-library`); with none
  given, starts every hosted app repo it finds present on disk (Slice 2 itself only has
  `organizeme` — i.e. the Host — capable of being "found," since no other app's `scripts/dev.py`
  or port entry exists until Slices 4/6/7 land; this slice's own demo is necessarily Host-only).
- Repo discovery: sibling-directory convention (`../event-creator`, etc.), overridable per app via
  an environment variable (e.g. `EVENT_CREATOR_REPO_PATH`) — implement this resolution as a pure
  function (`resolve_repo_path(service_name, env=os.environ) -> Path`) even though only
  `organizeme` (the launcher's own repo, trivially "discovered") is exercised end-to-end this
  slice.
- Starts the Host's own `scripts/dev.py` as a subprocess with `PORT` set from `ports.py`.
- TCP-connect readiness check on the Host's port before considering startup complete.
- For every *non-Host* app it starts, sets three subprocess environment variables generically —
  `PORT` (from `ports.py`), `REGISTRY_LOCAL_DEV_BYPASS=true`, and `REGISTRY_HOST_URL` (pointed at
  the Host's own local port) — regardless of whether that app's own `Settings` class reads them
  yet. This is written once, generically, here in Slice 2, so that Slices 4/6/7 (onboarding each
  consumer app) only need to add that app's own `registry_local_dev_bypass` setting + consumer
  wiring in its own repo, plus its one `ports.py` entry — not touch `local_dev.py` itself. An app
  whose `Settings` doesn't read these yet (i.e. every app before its own onboarding slice ships)
  simply ignores the extra environment variables.
- Generates the Caddyfile via `generate_caddyfile()` and starts `caddy run --config <path>` as a
  subprocess. If the `caddy` binary isn't on PATH, fail with a clear, actionable error pointing at
  the install docs (below) rather than a raw `FileNotFoundError` traceback.
- Relays every subprocess's stdout/stderr with a per-service color-coded prefix (e.g.
  `[organizeme] ...`).
- Failure handling (deliberately minimal, per TDD): a port already in use fails that one app's
  startup with a clear labeled error but doesn't stop the others; a subprocess crash is logged
  with its exit code and everything else keeps running; no dependency-install preflight, no
  auto-restart, no auto port-reassignment.
- On Ctrl-C: terminates every child process, including Caddy.

**Documentation** (folded into this slice per `/to-wbs` decision, since this is the slice that
introduces `ports.py` — the file a new app's author needs to edit): a new "Local development"
section in the Host's own docs covering (a) installing Caddy once (e.g.
`winget install CaddyServer.Caddy` / `brew install caddy`), (b) running
`scripts/local_dev.py`, (c) the `mock-integrations` flag (full description added once Slice 5/8
exist — this slice can stub the section and note mock-integrations lands in a later slice), (d)
adding a new app to `ports.py`. `organize-me`'s own `README.md` gets a pointer to this section.

## Design notes

TDD "Local process orchestration" and "Local reverse proxy & registry-driven routing generation";
[`docs/adr/local-dev-environment-launcher-orchestration-boundary.md`](../../../adr/local-dev-environment-launcher-orchestration-boundary.md)
and
[`docs/adr/local-dev-environment-local-reverse-proxy.md`](../../../adr/local-dev-environment-local-reverse-proxy.md).
Caddy port and install approach resolved at `/to-wbs` time: `:10000` default, manual one-time
install, no auto-detect/auto-install logic in the launcher itself. Plain HTTP (no TLS) is correct
— `app/auth/backend.py`'s existing comment already establishes `cookie_secure=True` works over
`http://localhost`.

Cross-app cookie sharing (PRD story 13) isn't fully provable until a second local service exists
(Slice 4) — this slice only proves the Host's own login-and-render path through Caddy.

## Blocked by

- [Slice 1](slice-1-extract-path-rules.md) — needs `infra/path_rules.py` to exist.

## Acceptance criteria

- [ ] `uv run python scripts/local_dev.py` starts the Host + Caddy with no other apps checked
      out, with no errors.
- [ ] Browsing to `http://localhost:10000/login`, logging in, and reaching `/dashboard` works
      identically to running the Host directly on `:8000` (routed correctly through Caddy).
- [ ] Static assets (compiled CSS) load correctly through `http://localhost:10000`.
- [ ] Ctrl-C cleanly terminates both the Host subprocess and Caddy — a second run immediately
      after doesn't hit a port-in-use error from a leftover process.
- [ ] A labeled, actionable error (not a traceback) appears if `caddy` isn't installed, or if
      port 8000/10000 is already in use.
- [ ] `generate_caddyfile()` includes a rule for every app in the registry (not just `organizeme`)
      even though only the Host was started this session — proving it's a pure function of the
      whole registry, not the launcher's session selection.
- [ ] The Host's docs and `README.md` describe the new workflow.

## Testing

`infra/local_dev/generate_caddyfile.py`: pure-function unit tests against constructed `AppEntry`
objects and a constructed port map, no real Caddy binary/filesystem/subprocess — mirroring
`tests/test_path_rules.py` (Slice 1) and the existing `tests/test_url_map_generator.py` style.
Include a case asserting an app absent from `ports` is simply omitted from the generated config
rather than raising.

`infra/local_dev/ports.py` and `resolve_repo_path()`: unit tested as pure functions (given a
service name and constructed env vars, resolve the port/path to use) — no real filesystem/
subprocess dependency.

`scripts/local_dev.py`'s actual process-orchestration behavior (starting/stopping subprocesses,
output relaying/prefixing) is explicitly lower-value to unit test exhaustively per the TDD — this
slice's acceptance criteria above (manually verified: run it, log in, Ctrl-C, run it again) are the
intended coverage instead of mocked-subprocess unit tests.

<!-- /to-implementation appends a "## Delivered" section here once this slice ships. -->
