"""App-registry: the single source of truth for every hosted app's sidebar nav, Settings tabs,
and (from R7) API path prefixes. Rendering (this package's chrome templates) and, from R5 onward,
the load balancer's path-routing map are both driven from this one list, per the
platform-restructure design.

Registry-decoupling (organize-me#218): `list_apps()`/`get_app()` read whichever `RegistrySource`
was registered via `configure_registry_source()` - there is no compiled-in data here anymore.
Each consumer authors its own registry data at runtime: the Host (organize-me) wraps its own
`app/core/registry.py` `APPS` list in an `InProcessRegistrySource`, and every other consumer wraps
a `FetchedRegistrySource` (`organizeme_chrome.registry_client`) that reads the Host's
`GET /internal/app-registry.json` in the background. A consumer that never calls
`configure_registry_source()` gets no implicit fallback - `list_apps()`/`get_app()` raise instead
(registry-decoupling Slice 3, organize-me#220 - the transitional compiled-in `APPS` literal this
docstring used to describe is fully retired). See docs/features/registry-decoupling/PRD.md
"Rollout mechanics."
"""

from dataclasses import dataclass, field
from typing import Protocol


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


class RegistrySource(Protocol):
    """Where `list_apps()`/`get_app()` read the current registry from.

    Two implementations exist: `InProcessRegistrySource` (organize-me's own app code - the Host
    wraps its own in-app `APPS`-equivalent list, no network) and `FetchedRegistrySource`
    (`organizeme_chrome.registry_client` - every other consumer, backed by a
    background-refreshed cache). See docs/adr/registry-decoupling-client-boundary.md.
    """

    def get_apps(self) -> list[AppEntry]: ...


_source: RegistrySource | None = None


def configure_registry_source(source: RegistrySource) -> None:
    """Called once by each app at startup to select where `list_apps()`/`get_app()` read from."""
    global _source
    _source = source


def reset_registry_source() -> None:
    """Clears whatever source `configure_registry_source()` set - for tests that call it to
    exercise a custom source and need to undo that global mutation afterward. Leaves
    `list_apps()`/`get_app()` unconfigured (they raise `RuntimeError` until reconfigured), since
    there is no compiled-in default left to fall back to (registry-decoupling Slice 3,
    organize-me#220)."""
    global _source
    _source = None


def _require_source() -> RegistrySource:
    if _source is None:
        raise RuntimeError(
            "organizeme_chrome registry source not configured - call "
            "configure_registry_source() before list_apps()/get_app()"
        )
    return _source


def list_apps() -> list[AppEntry]:
    return _require_source().get_apps()


def get_app(service_name: str) -> AppEntry:
    for app in _require_source().get_apps():
        if app.service_name == service_name:
            return app
    raise KeyError(f"No app registered under service_name={service_name!r}")
