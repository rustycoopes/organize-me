"""Local-dev-only port assignments for each hosted app's `service_name`.

Deliberately a plain `service_name -> int` module, kept separate from the shared, versioned
`AppEntry` dataclass — local port numbers have no bearing on real QA/prod routing, so they
shouldn't force a package version bump on every hosted app just to add one. See
docs/adr/local-dev-environment-local-reverse-proxy.md "Alternatives considered".

Each app-integration slice (4, 6, 7) adds exactly one entry here — no other change to this
module or to `scripts/local_dev.py` is needed to onboard a new app into local dev.
"""

import os

# The Host's own service_name - both this module and generate_caddyfile.py/local_dev.py import
# it, so the Host's identity in local dev has one shared source of truth rather than being
# hardcoded independently in each.
HOST_SERVICE_NAME = "organizeme"

PORTS: dict[str, int] = {
    HOST_SERVICE_NAME: 8000,
}

# Overridable so a developer with something else already bound to :10000 can move the shared
# local origin elsewhere without editing source.
CADDY_LOCAL_PORT = int(os.environ.get("CADDY_LOCAL_PORT", "10000"))
