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
