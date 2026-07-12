"""App-registry: the single source of truth for every hosted app's sidebar nav and Settings
tabs. Rendering (this package's chrome templates) and, from R5 onward, the load balancer's
path-routing map are both driven from this one list, per the platform-restructure design.
"""

from typing import NamedTuple


class AppNavItem(NamedTuple):
    path: str
    label: str


class SettingsTab(NamedTuple):
    # id (not a route path): today's Settings page is a single route with client-side Alpine
    # tab-switching (see macros/chrome_tabs.html), not per-tab routes. The design doc's sketch
    # shows path-based tabs for a future multi-page Settings area; revisit this field if/when a
    # hosted app actually needs that instead of in-page switching.
    id: str
    label: str


class AppEntry(NamedTuple):
    service_name: str
    nav: list[AppNavItem]
    settings_tabs: list[SettingsTab]


APPS: list[AppEntry] = [
    AppEntry(
        service_name="organizeme",
        nav=[
            AppNavItem("/dashboard", "Dashboard"),
            AppNavItem("/upload", "Upload"),
            AppNavItem("/processing", "Processing"),
            AppNavItem("/logs", "Logs"),
            AppNavItem("/prompt", "Prompt"),
            AppNavItem("/settings", "Settings"),
            AppNavItem("/profile", "Profile"),
        ],
        settings_tabs=[
            SettingsTab("storage", "Storage"),
            SettingsTab("notifications", "Notifications"),
        ],
    ),
]


def list_apps() -> list[AppEntry]:
    return APPS


def get_app(service_name: str) -> AppEntry:
    for app in APPS:
        if app.service_name == service_name:
            return app
    raise KeyError(f"No app registered under service_name={service_name!r}")
