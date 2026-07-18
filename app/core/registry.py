"""The Host's own copy of the app-registry data (organize-me#218, registry-decoupling Slice 1).

Registry-decoupling moves the hand-authored app list out of the versioned `organizeme_chrome`
package and into each app's own runtime - the Host (this app) is the one place it's authored, and
every other consumer fetches it from `GET /internal/app-registry.json` (see
`app/api/internal/registry.py`) instead of carrying its own build-time pin of the data.

Importing this module has the side effect of calling `configure_registry_source()` so that
`organizeme_chrome.list_apps()`/`get_app()` resolve against `APPS` below with no network call -
see the Host's own `app/core/nav.py` and `app/pages/settings.py`, both unchanged call sites. This
module is imported first (before any router module) in `app/main.py` specifically so that
side effect runs before any module-level `get_app()` call elsewhere (e.g.
`app/pages/settings.py`'s `_EVENT_CREATOR_APP = get_app("event-creator")`) executes.

`organizeme_chrome.registry` keeps its own compiled-in `APPS` literal, unchanged, as the
transitional fallback `RegistrySource` for any consumer that hasn't migrated yet (doc-library,
until its own Slice 2) - see docs/features/registry-decoupling/PRD.md "Rollout mechanics". The
list below is a genuine data fork from that literal, not a re-export; once every consumer has
migrated off the compiled-in fallback, a follow-up decommission slice deletes it from the package
entirely, leaving this module as the sole place `APPS` is authored.
"""

from organizeme_chrome.registry import (
    AppEntry,
    AppNavItem,
    RegistrySource,
    SettingsTab,
    configure_registry_source,
)

APPS: list[AppEntry] = [
    # R6: /dashboard is served by the independent event-creator service (the Host<->Event Creator
    # boundary tracer bullet). Listed first so the merged sidebar nav (see
    # templating.register_chrome) keeps Dashboard in its original position. R11 moved the rest of
    # this app's nav here too, so every entry below is event-creator-served, not just Dashboard.
    AppEntry(
        service_name="event-creator",
        nav=[
            AppNavItem("/dashboard", "Dashboard"),
            AppNavItem("/upload", "Upload"),
            AppNavItem("/processing", "Processing"),
            AppNavItem("/logs", "Logs"),
            AppNavItem("/prompt", "Prompt"),
        ],
        settings_tabs=[
            SettingsTab("storage", "Storage"),
            SettingsTab("notifications", "Notifications"),
            SettingsTab("preferences", "Preferences"),
        ],
        api_prefixes=[
            "/api/v1/storage-config",
            "/api/v1/user-settings",
            "/settings/event-creator",
            "/api/v1/events",
            "/api/v1/llm-prompt",
            "/api/v1/upload",
            "/api/v1/import-pending-files",
            "/api/v1/processing-runs",
            "/processing-runs",
            "/api/html/processing-runs",
        ],
    ),
    AppEntry(
        service_name="organizeme",
        nav=[
            AppNavItem("/settings", "Settings"),
            AppNavItem("/profile", "Profile"),
        ],
        settings_tabs=[],
    ),
    AppEntry(
        service_name="doc-library",
        nav=[AppNavItem("/doc-library", "Doc Library")],
        settings_tabs=[],
        api_prefixes=["/api/v1/doc-links", "/doc-library/fragments"],
    ),
]


class InProcessRegistrySource:
    """The Host's own `RegistrySource`: wraps `APPS` above directly, no network, no cache -
    see docs/adr/registry-decoupling-client-boundary.md."""

    def get_apps(self) -> list[AppEntry]:
        return APPS


# Confirms InProcessRegistrySource actually satisfies the protocol it's documented against.
_: type[RegistrySource] = InProcessRegistrySource

configure_registry_source(InProcessRegistrySource())
