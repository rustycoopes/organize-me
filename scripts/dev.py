"""Starts the Host locally for development: `uvicorn --reload` plus the CSS watcher
(`scripts/build_css.py --watch`), relayed to this process's own stdout/stderr. This is the
conventional per-app dev-server entrypoint every hosted app's own `scripts/dev.py` mirrors — see
docs/adr/local-dev-environment-launcher-orchestration-boundary.md. Port comes from the `PORT`
environment variable (the same convention `scripts/local_dev.py` relies on to invoke this and
every other app's `scripts/dev.py` uniformly).

Always runs the CSS watcher — no `--no-css-watch` escape hatch (a developer who wants uvicorn
alone can just run it directly instead of via this script).

Usage:
    uv run python scripts/dev.py            # PORT defaults to 8000
    PORT=8010 uv run python scripts/dev.py
"""

import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    port = os.environ.get("PORT", "8000")

    uvicorn_cmd = [sys.executable, "-m", "uvicorn", "app.main:app", "--reload", "--port", port]
    css_cmd = [sys.executable, str(REPO_ROOT / "scripts" / "build_css.py"), "--watch"]

    processes = [
        ("uvicorn", subprocess.Popen(uvicorn_cmd, cwd=REPO_ROOT)),
        ("css-watch", subprocess.Popen(css_cmd, cwd=REPO_ROOT)),
    ]
    reported_exit = {label: False for label, _ in processes}

    try:
        # Only uvicorn exiting should end this script - a css-watch crash (e.g. a broken
        # tailwindcss install) degrades to no live CSS rebuilds rather than tearing down the
        # whole dev server out from under it.
        _, uvicorn_process = processes[0]
        while uvicorn_process.poll() is None:
            for label, p in processes:
                code = p.poll()
                if code is not None and not reported_exit[label]:
                    print(f"[{label}] exited with code {code}", file=sys.stderr)
                    reported_exit[label] = True
            time.sleep(0.5)
    except KeyboardInterrupt:
        # Expected way to stop this script; not a failure.
        pass
    finally:
        for _, p in processes:
            if p.poll() is None:
                p.terminate()
        for _, p in processes:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()


if __name__ == "__main__":
    main()
