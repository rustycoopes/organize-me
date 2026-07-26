"""Provider-neutral derivation of path rules from the R3 app-registry
(organizeme_chrome.registry) — the single source of truth for routing, per the platform-
restructure design (docs/platform-restructure/WBS/slice-R5.md). Path rules must never be
hand-maintained separately from the registry that also drives the Host chrome's sidebar/Settings-
tab rendering.

Host-owned routes (auth pages, the shared shell's own static paths) aren't part of any hosted
app's nav, so they aren't in the registry — they're the one fixed list here. Everything else is
derived: each app-registry entry's nav paths route to that app's own backend service.

Shared by infra/gcp_lb/generate_url_map.py (the GCP Load-Balancer URL-map generator) and, from
Slice 2 onward, the local Caddyfile generator — see docs/adr/local-dev-environment-local-reverse-
proxy.md for why this extraction exists.
"""

from dataclasses import dataclass, field

from organizeme_chrome.registry import AppEntry, list_apps
from organizeme_chrome.static_paths import static_mount_path

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


def _claim_path(seen_paths: dict[str, str], path: str, service: str, source: str) -> None:
    """Records `path` as owned by `service` in `seen_paths`, or raises if some other service
    already claimed it — shared by every path source below (nav, api_prefixes, static-asset)
    so a registry authoring mistake is caught the same way regardless of which one it came from.
    """
    owner = seen_paths.get(path)
    if owner is not None:
        raise ValueError(
            f"Path {path!r} is claimed by both {owner!r} and {service!r} — the app-registry "
            f"must not assign the same {source} to two different apps."
        )
    seen_paths[path] = service


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


def generate_path_rules(
    apps: list[AppEntry] | None = None,
    *,
    backend_suffix: str = "",
    apply_qa_filter: bool = True,
) -> list[PathRule]:
    if apps is None:
        apps = list_apps()

    # An empty backend_suffix always means QA (see __main__ below: only qa runs unsuffixed, every
    # other environment gets "-{env}"). An app with no QA deployment (organize-me#257, e.g.
    # ha-dashboard — docs/adr/ha-dashboard-no-qa-environment.md) has no QA backend service to route
    # to, so it must be skipped entirely when generating QA's URL map, not just left unsuffixed.
    # This filtering is GCP-specific (QA/prod is a real distinction there); the local Caddyfile
    # generator (infra/local_dev/generate_caddyfile.py) passes apply_qa_filter=False, since there's
    # only one local environment and an app's lack of a QA deployment has no bearing on whether it
    # can run locally — see docs/adr/local-dev-environment-local-reverse-proxy.md.
    if apply_qa_filter:
        is_qa = backend_suffix == ""
        apps = [app for app in apps if app.qa_available or not is_qa]

    host_backend = f"{HOST_BACKEND}{backend_suffix}"
    rules = [PathRule(service=host_backend, paths=list(HOST_PATHS))]
    seen_paths: dict[str, str] = {path: host_backend for path in HOST_PATHS}
    for app in apps:
        service = f"{app.service_name}-backend{backend_suffix}"
        app_paths = []
        for item in app.nav:
            if item.path in HOST_PATHS:
                continue
            _claim_path(seen_paths, item.path, service, "nav path")
            app_paths.append(item.path)
        # R7 (#178): an app's route surface isn't just its nav — its own API/fragment routes
        # (declared via api_prefixes) need path rules too, or the LB falls through to
        # defaultService (the Host) for everything else the app actually serves.
        for prefix in app.api_prefixes:
            for pattern in _prefix_patterns(prefix):
                _claim_path(seen_paths, pattern, service, "api_prefixes entry")
                app_paths.append(pattern)
        # static-asset-routing Slice 3 (organize-me#255): each app's static assets are mounted
        # under static_mount_path(app.service_name) in that app's own FastAPI process — the LB
        # needs a matching path rule or those requests fall through to defaultService (the Host).
        # Unlike api_prefixes' _prefix_patterns() above, only the `/*` wildcard form is emitted,
        # not the bare prefix: the bare prefix (e.g. `/doc-library/static` with nothing after it)
        # has no file for StaticFiles to serve either way, so there's no real request that needs
        # an exact-match rule the way api_prefixes' bare-path endpoints do.
        static_pattern = f"{static_mount_path(app.service_name)}/*"
        _claim_path(seen_paths, static_pattern, service, "static-asset prefix")
        app_paths.append(static_pattern)
        # Every registered app now always contributes at least its static-asset rule above, so
        # `app_paths` can no longer be empty here — but the rule is still built explicitly per
        # app (rather than unconditionally appended above) to keep this the one place that
        # decides an app gets a PathRule at all.
        rules.append(PathRule(service=service, paths=app_paths))
    return rules
