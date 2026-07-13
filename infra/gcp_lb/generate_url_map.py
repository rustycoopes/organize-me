"""Generates the LB's URL-map path rules from the R3 app-registry (organizeme_chrome.registry) —
the single source of truth for routing, per the platform-restructure design (docs/platform-
restructure/WBS/slice-R5.md). Path rules must never be hand-maintained separately from the
registry that also drives the Host chrome's sidebar/Settings-tab rendering.

Host-owned routes (auth pages, the shared shell's own static paths) aren't part of any hosted
app's nav, so they aren't in the registry — they're the one fixed list here. Everything else is
derived: each app-registry entry's nav paths route to that app's own backend service.

Run directly to print the generated URL map as YAML for `gcloud compute url-maps import`:
    uv run python -m infra.gcp_lb.generate_url_map
"""

from dataclasses import dataclass, field

from organizeme_chrome.registry import AppEntry, list_apps

HOST_BACKEND = "host-backend"

# Auth/shell routes the Host itself serves — not sourced from any app's nav (see module docstring).
HOST_PATHS: list[str] = [
    "/",
    "/login",
    "/register",
    "/forgot-password",
    "/reset-password",
    "/profile",
]


@dataclass(frozen=True)
class PathRule:
    service: str
    paths: list[str] = field(default_factory=list)


def _prefix_patterns(prefix: str) -> list[str]:
    """Renders an `api_prefixes` entry as `gcloud compute url-maps import` path patterns.

    GCP's `/*` wildcard suffix (https://cloud.google.com/load-balancing/docs/url-map-concepts
    #wildcards) only matches paths with *something* after the trailing `/` — it does NOT also
    match the bare prefix string itself. Several of this slice's endpoints are hit at exactly the
    bare path (e.g. `GET/PUT /api/v1/storage-config`, `GET/PATCH /api/v1/user-settings`), so both
    the exact path and its `/*` wildcard must be emitted, or those bare-path requests silently
    fall through to defaultService (the Host) — caught in review before this shipped.
    """
    bare = prefix.rstrip("/")
    return [bare, f"{bare}/*"]


def generate_path_rules(apps: list[AppEntry] | None = None) -> list[PathRule]:
    if apps is None:
        apps = list_apps()

    rules = [PathRule(service=HOST_BACKEND, paths=list(HOST_PATHS))]
    seen_paths: dict[str, str] = {path: HOST_BACKEND for path in HOST_PATHS}
    for app in apps:
        service = f"{app.service_name}-backend"
        app_paths = []
        for item in app.nav:
            if item.path in HOST_PATHS:
                continue
            owner = seen_paths.get(item.path)
            if owner is not None:
                raise ValueError(
                    f"Path {item.path!r} is claimed by both {owner!r} and {service!r} — "
                    "the app-registry must not assign the same nav path to two different apps."
                )
            seen_paths[item.path] = service
            app_paths.append(item.path)
        # R7 (#178): an app's route surface isn't just its nav — its own API/fragment routes
        # (declared via api_prefixes) need path rules too, or the LB falls through to
        # defaultService (the Host) for everything else the app actually serves.
        for prefix in app.api_prefixes:
            for pattern in _prefix_patterns(prefix):
                owner = seen_paths.get(pattern)
                if owner is not None:
                    raise ValueError(
                        f"Path {pattern!r} is claimed by both {owner!r} and {service!r} — "
                        "the app-registry must not assign the same api_prefixes entry to two "
                        "different apps."
                    )
                seen_paths[pattern] = service
                app_paths.append(pattern)
        if app_paths:
            rules.append(PathRule(service=service, paths=app_paths))
    return rules


def _backend_service_ref(name: str) -> str:
    """`gcloud compute url-maps import`'s YAML schema expects backend services as a resource
    path, not a bare name — a bare name is silently misresolved rather than rejected."""
    return f"global/backendServices/{name}"


def to_url_map_yaml(rules: list[PathRule], *, name: str, default_service: str) -> str:
    """Renders `rules` as a `gcloud compute url-maps import` YAML document."""
    default_ref = _backend_service_ref(default_service)
    lines = [
        f"name: {name}",
        f"defaultService: {default_ref}",
        "pathMatchers:",
        "  - name: app-registry-path-matcher",
        f"    defaultService: {default_ref}",
        "    pathRules:",
    ]
    for rule in rules:
        lines.append(f"      - service: {_backend_service_ref(rule.service)}")
        lines.append("        paths:")
        for path in rule.paths:
            lines.append(f"          - {path}")
    lines.append("hostRules:")
    lines.append("  - hosts:")
    lines.append("      - $LB_HOST")
    lines.append("    pathMatcher: app-registry-path-matcher")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    print(to_url_map_yaml(generate_path_rules(), name="organizeme-qa-url-map", default_service=HOST_BACKEND))
