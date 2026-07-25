"""The single source of truth for where a hosted app's static assets live, URL-wise.

Colocated with `registry.py` (not `paths.py`, which is exclusively filesystem paths into this
installed package, and not `assets.py`, which is cache-busting) because both this app's own
FastAPI static mount and the Load Balancer's URL-map generator
(`infra/gcp_lb/generate_url_map.py`, Slice 3) must derive the same prefix from the same
`service_name` - see docs/adr/static-asset-routing-prefix-derivation.md.
"""


def static_mount_path(service_name: str) -> str:
    """The URL path prefix a hosted app's static assets are served under, e.g.
    `static_mount_path("doc-library") == "/doc-library/static"` (no trailing slash)."""
    return f"/{service_name}/static"
