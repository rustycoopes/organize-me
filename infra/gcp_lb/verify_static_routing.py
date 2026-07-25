"""Verifies the shared domain routes an already-migrated app's static assets to that app's own
Cloud Run backend, rather than falling through to the Host — the failure mode static-asset-routing
(docs/features/static-asset-routing/PRD.md) exists to close. Manual-run only, not wired into CI
per the PRD — see infra/gcp_lb/README.md.

For each app service_name passed on the command line, fetches a known static asset
(static_mount_path(app)/css/app.css) via the shared domain and via that app's own direct Cloud Run
URL, and asserts the bytes are identical.

Only checks the apps explicitly named on the command line. Slice 3's LB regen adds an inert
static-asset path rule for every hosted app at once, including ones that haven't migrated their own
FastAPI mount to the prefixed path yet — running this against one of those would report a false
failure (its prefix legitimately falls through to the Host by design until that app's own
migration PR ships). It's the caller's job (this slice's own manual run, and each of Slices 4-6) to
only pass apps that have actually migrated.

Usage:
    uv run python -m infra.gcp_lb.verify_static_routing --env prod doc-library event-creator
"""

import argparse
import json
import re
import subprocess
import sys
import urllib.request
from urllib.error import HTTPError, URLError

from organizeme_chrome.static_paths import static_mount_path

REGION = "northamerica-northeast1"
KNOWN_ASSET_SUFFIX = "/css/app.css"
GCLOUD_TIMEOUT_SECONDS = 30
DEFAULT_HOSTS = {
    "qa": "organizeme.qa.russcoopersoftware.com",
    "prod": "organizeme.russcoopersoftware.com",
}

class VerificationError(Exception):
    """Raised for any condition that should fail this app's check loudly rather than silently
    comparing against (or reporting on) a non-representative target."""


# Matches organizeme_chrome.registry.AppEntry's own service_name validation — every real registry
# entry already satisfies this. Enforced again here because this script's app names come from the
# CLI, not the registry: on Windows, `gcloud` is invoked with shell=True (see _gcloud() below), so
# an unvalidated argument reaching it would be a real cmd.exe command-injection vector (`%VAR%`
# expansion is re-parsed for shell operators after substitution), not just a theoretical one.
_SAFE_SERVICE_NAME = re.compile(r"^[a-z][a-z0-9-]*$")


def _validate_service_name(app_service_name: str) -> None:
    if not _SAFE_SERVICE_NAME.match(app_service_name):
        raise VerificationError(
            f"{app_service_name!r} is not a valid service_name (must match "
            f"{_SAFE_SERVICE_NAME.pattern!r}) — refusing to pass it to gcloud."
        )


def _gcloud(*args: str) -> str:
    # On Windows, `gcloud` resolves to a .cmd wrapper — CreateProcess can't exec that directly
    # (only cmd.exe can), so shell=True is required there; on POSIX gcloud is a normal
    # executable/script and shell=True isn't needed. _validate_service_name() above is what
    # actually keeps this safe against shell metacharacters/expansion — args here are always
    # either static strings or a value that's already passed that check.
    try:
        result = subprocess.run(
            ["gcloud", *args],
            capture_output=True,
            text=True,
            shell=(sys.platform == "win32"),
            timeout=GCLOUD_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise VerificationError(
            f"`gcloud {' '.join(args)}` did not complete within {GCLOUD_TIMEOUT_SECONDS}s"
        ) from exc
    if result.returncode != 0:
        raise VerificationError(
            f"`gcloud {' '.join(args)}` failed: {result.stderr.strip()}"
        )
    return result.stdout.strip()


def _run_service_name(app_service_name: str, env: str) -> str:
    return f"{app_service_name}-{env}"


def assert_single_revision_full_traffic(run_service: str) -> None:
    """Fails loudly rather than silently comparing against a non-representative target if
    `run_service` isn't serving 100% of traffic from exactly one revision — this org's deploy
    pattern has no traffic-splitting today, but nothing here should assume that stays true
    forever (see the TDD's "Verification script" section)."""
    raw = _gcloud(
        "run", "services", "describe", run_service,
        f"--region={REGION}", "--format=json",
    )
    traffic = json.loads(raw).get("status", {}).get("traffic") or []
    active = [t for t in traffic if t.get("percent")]
    if len(active) != 1 or active[0].get("percent") != 100:
        raise VerificationError(
            f"{run_service!r} is not serving 100% traffic from a single revision "
            f"(status.traffic={traffic!r}) — refusing to compare against it."
        )


def direct_service_url(run_service: str) -> str:
    return _gcloud(
        "run", "services", "describe", run_service,
        f"--region={REGION}", "--format=value(status.url)",
    )


def fetch(url: str) -> bytes:
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            body: bytes = response.read()
            return body
    except HTTPError as exc:
        raise VerificationError(f"GET {url} returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise VerificationError(f"GET {url} failed: {exc.reason}") from exc


def verify_app(app_service_name: str, *, shared_host: str, env: str) -> None:
    _validate_service_name(app_service_name)
    run_service = _run_service_name(app_service_name, env)
    assert_single_revision_full_traffic(run_service)

    direct_base = direct_service_url(run_service)
    asset_path = f"{static_mount_path(app_service_name)}{KNOWN_ASSET_SUFFIX}"

    shared_bytes = fetch(f"https://{shared_host}{asset_path}")
    direct_bytes = fetch(f"{direct_base}{asset_path}")

    if shared_bytes != direct_bytes:
        raise VerificationError(
            f"{app_service_name!r}: content at {asset_path} differs between the shared domain "
            f"(https://{shared_host}) and the direct Cloud Run URL ({direct_base}) — the shared "
            "domain is not serving this app's own static assets."
        )
    print(f"OK  {app_service_name}: {len(shared_bytes)} bytes match at {asset_path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "apps", nargs="+", help="service_name of each already-migrated app to verify"
    )
    parser.add_argument("--env", choices=["qa", "prod"], default="qa")
    parser.add_argument(
        "--host", default=None, help="Override the shared-domain host (defaults per --env)"
    )
    args = parser.parse_args(argv)
    shared_host = args.host or DEFAULT_HOSTS[args.env]

    failures = []
    for app in args.apps:
        try:
            verify_app(app, shared_host=shared_host, env=args.env)
        except Exception as exc:  # noqa: BLE001 - one app's unexpected failure (e.g. malformed
            # `gcloud` JSON, an unhandled urllib exception) must not abort checking the rest;
            # report it against this app and keep going, per this script's per-app-report design.
            failures.append(f"{app}: {exc}")

    for failure in failures:
        print(f"FAIL {failure}", file=sys.stderr)

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
