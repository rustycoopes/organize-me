from jinja2 import ChoiceLoader, Environment, PackageLoader

from organizeme_chrome.json_filter import tojson_filter
from organizeme_chrome.registry import get_app
from organizeme_chrome.theme import ALPINE_CDN, DAISYUI_CDN, TAILWIND_CDN, theme_attr


def register_chrome(env: Environment, app_service_name: str) -> None:
    """Wire a host app's Jinja environment up to this package's chrome.

    Adds the package's template directory to the environment's loader (so hosted templates can
    `{% extends "chrome_authenticated_base.html" %}` / import `macros/chrome_tabs.html`) and
    exposes the app's settings tabs, theme config, CDN links, and a `tojson` filter as
    environment-wide globals/filters.

    The sidebar itself is NOT computed here: grouping nav items by app and resolving each group's
    collapsed/expanded state depends on the current request's user and path, both unknown at this
    env-setup-time call. Callers render the sidebar by passing `nav_groups`
    (`organizeme_chrome.nav_groups.build_nav_groups`) and `flat_nav_items`
    (`organizeme_chrome.nav_groups.flat_nav_items`) into each page's own template context —
    see docs/adr/sidebar-nav-groups-render-boundary.md in the organize-me repo. `settings_tabs`
    stays scoped to the caller's own entry — a Settings page only shows the tabs relevant to the
    app that owns it.
    """
    package_loader = PackageLoader("organizeme_chrome", "templates")
    env.loader = (
        ChoiceLoader([env.loader, package_loader]) if env.loader is not None else package_loader
    )

    app = get_app(app_service_name)
    env.globals["settings_tabs"] = app.settings_tabs
    env.globals["theme_attr"] = theme_attr
    env.globals["TAILWIND_CDN"] = TAILWIND_CDN
    env.globals["ALPINE_CDN"] = ALPINE_CDN
    env.globals["DAISYUI_CDN"] = DAISYUI_CDN
    env.filters["tojson"] = tojson_filter
