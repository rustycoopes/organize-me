"""App-registry: the single source of truth for every hosted app's sidebar nav, Settings tabs,
and (from R7) API path prefixes. Rendering (this package's chrome templates) and, from R5 onward,
the load balancer's path-routing map are both driven from this one list, per the
platform-restructure design.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AppNavItem:
    path: str
    label: str


@dataclass(frozen=True)
class SettingsTab:
    # id (not a route path): today's Settings page is a single route with client-side Alpine
    # tab-switching (see macros/chrome_tabs.html), not per-tab routes. The design doc's sketch
    # shows path-based tabs for a future multi-page Settings area; revisit this field if/when a
    # hosted app actually needs that instead of in-page switching.
    #
    # R7: a tab's *content*, unlike the tab-bar chrome itself, can now be owned by a different app
    # than the one rendering the Settings shell (see AppEntry.api_prefixes) — the id still isn't a
    # route path for the shell's own purposes, but the owning app is free to expose one at
    # `/settings/{service_name}/{id}` for the shell to fetch (app/pages/settings.py, app/templates/
    # settings.html).
    id: str
    label: str


@dataclass(frozen=True)
class AppEntry:
    service_name: str
    nav: list[AppNavItem]
    settings_tabs: list[SettingsTab]
    # R7: API path prefixes this app owns beyond its nav's page routes — e.g. its own `/api/v1/*`
    # surface and any `/settings/{service_name}/*` tab-content fragment routes it serves for the
    # Host Settings shell. Feeds infra/gcp_lb/generate_url_map.py so the LB's path rules cover an
    # app's full route surface, not just its nav (closes #178). A `default_factory` (rather than a
    # bare `[]`, which NamedTuple's lack of one previously forced) so each entry gets its own list.
    api_prefixes: list[str] = field(default_factory=list)


APPS: list[AppEntry] = [
    # R6: /dashboard is now served by the independent event-creator service (the Host↔Event
    # Creator boundary tracer bullet). Listed first so the merged sidebar nav (see
    # templating.register_chrome) keeps Dashboard in its original position, ahead of the
    # still-Host-served pages below.
    AppEntry(
        service_name="event-creator",
        nav=[
            AppNavItem("/dashboard", "Dashboard"),
        ],
        # R7: Storage + Notifications move here from "organizeme" — the storage-connection and
        # settings functionality migrated into Event Creator (docs/platform-restructure/WBS/
        # slice-R7.md). Preferences is a deliberate stub: it was never built in the monolith
        # (dark-mode lives on the Host Profile page instead), declared now so the Host Settings
        # shell shows the tab while Event Creator's fragment route serves placeholder content.
        settings_tabs=[
            SettingsTab("storage", "Storage"),
            SettingsTab("notifications", "Notifications"),
            SettingsTab("preferences", "Preferences"),
        ],
        # R7: storage-config CRUD/OAuth (moved off the Host — see app/api/v1/storage_config.py,
        # storage_google_drive.py, storage_dropbox.py), the notification-toggle endpoint
        # (GET/PATCH /api/v1/user-settings), and the Settings tab-content fragment routes
        # (GET /settings/event-creator/{storage,notifications,preferences}) the Host's Settings
        # shell fetches via HTMX (see app/pages/settings.py).
        api_prefixes=[
            "/api/v1/storage-config",
            "/api/v1/user-settings",
            "/settings/event-creator",
        ],
    ),
    AppEntry(
        service_name="organizeme",
        nav=[
            AppNavItem("/upload", "Upload"),
            AppNavItem("/processing", "Processing"),
            AppNavItem("/logs", "Logs"),
            AppNavItem("/prompt", "Prompt"),
            AppNavItem("/settings", "Settings"),
            AppNavItem("/profile", "Profile"),
        ],
        # R7: Storage/Notifications/Preferences tabs moved to "event-creator" above — the Host
        # still renders the Settings shell (tab-bar chrome) but no longer owns any tab's content.
        settings_tabs=[],
    ),
]


def list_apps() -> list[AppEntry]:
    return APPS


def get_app(service_name: str) -> AppEntry:
    for app in APPS:
        if app.service_name == service_name:
            return app
    raise KeyError(f"No app registered under service_name={service_name!r}")
