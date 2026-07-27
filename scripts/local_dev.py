"""Local dev orchestrator: starts the Host (and any selected/discovered hosted apps) as plain
subprocesses behind a generated local Caddy proxy, so cross-app nav, the shared SSO cookie, and
static assets all behave the same way locally as they do in QA/prod. See
docs/adr/local-dev-environment-launcher-orchestration-boundary.md and
docs/adr/local-dev-environment-local-reverse-proxy.md.

Never hardcodes another repo's run command — it only discovers each selected app's repo path,
looks up its local port (`infra/local_dev/ports.py`), and invokes that repo's own
`scripts/dev.py`.

Usage:
    uv run python scripts/local_dev.py                       # Host + Caddy only
    uv run python scripts/local_dev.py --apps event-creator   # + event-creator
"""

import argparse
import itertools
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from collections.abc import Mapping
from pathlib import Path

if sys.platform != "win32":
    import signal

# Side-effect import: configures organizeme_chrome's registry source against the Host's own
# in-process APPS (registry-decoupling, organize-me#218) before list_apps() below is called - see
# app/core/registry.py's module docstring and infra/gcp_lb/generate_url_map.py's identical need.
from app.core import registry as _registry  # noqa: F401
from organizeme_chrome.registry import list_apps

from infra.local_dev.generate_caddyfile import generate_caddyfile
from infra.local_dev.ports import CADDY_LOCAL_PORT, HOST_SERVICE_NAME, PORTS

REPO_ROOT = Path(__file__).resolve().parent.parent

_COLORS = ["\033[36m", "\033[35m", "\033[33m", "\033[32m", "\033[34m", "\033[91m"]
_RESET = "\033[0m"


def resolve_repo_path(service_name: str, env: Mapping[str, str] = os.environ) -> Path:
    """Sibling-directory convention (`../event-creator`, etc.), overridable per app via an
    environment variable (e.g. `EVENT_CREATOR_REPO_PATH`) so a developer can point at a git
    worktree holding an in-progress branch instead of the main checkout. The Host resolves to
    this launcher's own repo, trivially."""
    if service_name == HOST_SERVICE_NAME:
        return REPO_ROOT
    override_var = f"{service_name.upper().replace('-', '_')}_REPO_PATH"
    override = env.get(override_var)
    if override:
        return Path(override)
    return REPO_ROOT.parent / service_name


def host_subprocess_env(
    ports: dict[str, int], base_env: Mapping[str, str] | None = None
) -> dict[str, str]:
    """The Host isn't a registry *consumer* like `non_host_subprocess_env` below, but it is the
    one that *verifies* `GET /internal/app-registry.json` requests
    (`app/api/internal/registry.py`'s `_verify_registry_read_token`), and that check reads
    `registry_local_dev_bypass` from the Host's own `Settings` - so the bypass has to be set here,
    on the Host's subprocess env, not on the consumers that read the resulting unauthenticated
    response."""
    env = dict(base_env if base_env is not None else os.environ)
    env["PORT"] = str(ports[HOST_SERVICE_NAME])
    env["REGISTRY_LOCAL_DEV_BYPASS"] = "true"
    return env


def non_host_subprocess_env(
    service_name: str, ports: dict[str, int], base_env: Mapping[str, str] | None = None
) -> dict[str, str]:
    """The three subprocess environment variables set generically for *any* non-Host app this
    launcher starts, regardless of whether that app's own `Settings` class reads them yet — see
    docs/features/local-dev-environment/WBS/slice-2-launcher-and-proxy-host-only.md. Each
    consumer app's own onboarding slice (4/6/7) only needs to add its own `registry_local_dev_
    bypass` setting + wiring in its own repo, not touch this launcher."""
    env = dict(base_env if base_env is not None else os.environ)
    env["PORT"] = str(ports[service_name])
    env["REGISTRY_LOCAL_DEV_BYPASS"] = "true"
    env["REGISTRY_HOST_URL"] = f"http://localhost:{ports[HOST_SERVICE_NAME]}"
    return env


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("localhost", port)) == 0


def _wait_until_ready(port: int, timeout: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _port_in_use(port):
            return True
        time.sleep(0.2)
    return False


def _dev_py_path(service_name: str) -> Path:
    return resolve_repo_path(service_name) / "scripts" / "dev.py"


def _discoverable_non_host_services() -> list[str]:
    return [
        name for name in PORTS if name != HOST_SERVICE_NAME and _dev_py_path(name).exists()
    ]


def _select_non_host_services(requested: list[str] | None) -> list[str]:
    if requested is None:
        return _discoverable_non_host_services()

    requested = [name for name in requested if name != HOST_SERVICE_NAME]
    known = [name for name in PORTS if name != HOST_SERVICE_NAME]
    unknown = [name for name in requested if name not in PORTS]
    if unknown:
        print(
            f"error: unknown service name(s) {unknown} - known local-dev services: {known} "
            "(add an entry to infra/local_dev/ports.py first).",
            file=sys.stderr,
        )
        sys.exit(1)

    # Checked upfront, before any subprocess starts: an explicitly-requested app whose repo (or
    # scripts/dev.py) isn't actually there would otherwise only surface as a Popen crash *after*
    # the Host (and any earlier --apps entries) had already been started, leaving them orphaned
    # with nothing to clean them up.
    missing = [name for name in requested if not _dev_py_path(name).exists()]
    if missing:
        for name in missing:
            print(
                f"error: [{name}] no scripts/dev.py found at {_dev_py_path(name)} - check out "
                f"that repo (or set {name.upper().replace('-', '_')}_REPO_PATH) first.",
                file=sys.stderr,
            )
        sys.exit(1)

    return requested


class ManagedProcess:
    """One relayed, labeled subprocess. Killing it kills its whole process tree (not just this
    one PID) — `uv run python scripts/dev.py` itself spawns uvicorn's `--reload` supervisor plus
    the CSS watcher as further children, and a plain `Popen.terminate()`/`SIGTERM` only reaches
    the immediate child, which would otherwise leave those grandchildren (and a port) bound for
    the *next* run. On Windows this is `taskkill /T /F`; on POSIX, `start_new_session=True` below
    puts the whole tree in its own process group so `os.killpg` reaches every descendant the same
    way, without depending on each app's own `scripts/dev.py` handling SIGTERM itself.
    """

    def __init__(
        self, label: str, cmd: list[str], cwd: Path, env: dict[str, str], color: str
    ) -> None:
        self.label = label
        self.reported_exit = False
        self.process = subprocess.Popen(
            cmd,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            start_new_session=sys.platform != "win32",
        )
        self._thread = threading.Thread(target=self._relay, args=(color,), daemon=True)
        self._thread.start()

    def _relay(self, color: str) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            print(f"{color}[{self.label}]{_RESET} {line}", end="")

    def terminate(self) -> None:
        if self.process.poll() is not None:
            return
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/PID", str(self.process.pid), "/T", "/F"],
                capture_output=True,
            )
        else:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            except ProcessLookupError:
                pass
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            if sys.platform != "win32":
                try:
                    os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass
            self.process.wait(timeout=5)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apps",
        nargs="*",
        default=None,
        metavar="SERVICE",
        help=(
            "Non-Host services to start (default: every service in infra/local_dev/ports.py "
            "whose repo is found on disk with its own scripts/dev.py)"
        ),
    )
    args = parser.parse_args()

    caddy_bin = shutil.which("caddy")
    if caddy_bin is None:
        print(
            "error: `caddy` was not found on PATH.\n"
            "Install it once, then re-run this script:\n"
            "  winget install CaddyServer.Caddy   (Windows)\n"
            "  brew install caddy                 (macOS)\n"
            "See the Host's \"Local development\" docs for details.",
            file=sys.stderr,
        )
        sys.exit(1)

    non_host_services = _select_non_host_services(args.apps)
    colors = itertools.cycle(_COLORS)
    managed: list[ManagedProcess] = []

    # Everything from here down is one try/finally: `finally` always terminates whatever's in
    # `managed` so far, so an unexpected failure partway through startup (e.g. a subprocess
    # genuinely refusing to spawn) can't leave an already-started Host (or earlier --apps entry)
    # orphaned with nothing to clean it up - the same guarantee Ctrl-C during the run loop gets.
    try:
        host_port = PORTS[HOST_SERVICE_NAME]
        if _port_in_use(host_port):
            print(
                f"error: [{HOST_SERVICE_NAME}] port {host_port} is already in use - stop whatever "
                "is bound to it and try again.",
                file=sys.stderr,
            )
        else:
            managed.append(
                ManagedProcess(
                    HOST_SERVICE_NAME,
                    ["uv", "run", "python", "scripts/dev.py"],
                    REPO_ROOT,
                    host_subprocess_env(PORTS),
                    next(colors),
                )
            )
            if not _wait_until_ready(host_port):
                print(
                    f"error: [{HOST_SERVICE_NAME}] didn't start listening on port {host_port} in "
                    "time.",
                    file=sys.stderr,
                )

        for service in non_host_services:
            port = PORTS[service]
            if _port_in_use(port):
                print(
                    f"error: [{service}] port {port} is already in use - skipping.",
                    file=sys.stderr,
                )
                continue
            managed.append(
                ManagedProcess(
                    service,
                    ["uv", "run", "python", "scripts/dev.py"],
                    resolve_repo_path(service),
                    non_host_subprocess_env(service, PORTS),
                    next(colors),
                )
            )

        caddyfile = generate_caddyfile(list_apps(), PORTS)
        caddyfile_path = Path(tempfile.gettempdir()) / "organizeme-local-dev-Caddyfile"
        caddyfile_path.write_text(caddyfile)

        if _port_in_use(CADDY_LOCAL_PORT):
            print(
                f"error: [caddy] port {CADDY_LOCAL_PORT} is already in use - stop whatever is "
                "bound to it and try again.",
                file=sys.stderr,
            )
        else:
            managed.append(
                ManagedProcess(
                    "caddy",
                    [caddy_bin, "run", "--config", str(caddyfile_path), "--adapter", "caddyfile"],
                    REPO_ROOT,
                    dict(os.environ),
                    next(colors),
                )
            )

        if not managed:
            print("error: nothing started - see the errors above.", file=sys.stderr)
            sys.exit(1)

        caddy_url = f"http://localhost:{CADDY_LOCAL_PORT}"
        print(f"Local dev running - browse {caddy_url}")
        # Only the Caddy-fronted origin knows how to route every onboarded app (e.g.
        # /ha-dashboard) - opening the Host's own bare port here would silently 404 on any
        # cross-app nav link, which is exactly the confusing failure mode this auto-open avoids.
        if any(p.label == "caddy" for p in managed):
            webbrowser.open(caddy_url)

        while any(p.process.poll() is None for p in managed):
            for p in managed:
                code = p.process.poll()
                if code is not None and not p.reported_exit:
                    print(f"[{p.label}] exited with code {code}")
                    p.reported_exit = True
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        print(f"error: local dev failed to start cleanly: {exc}", file=sys.stderr)
    finally:
        print("Shutting down...")
        for p in managed:
            p.terminate()


if __name__ == "__main__":
    main()
