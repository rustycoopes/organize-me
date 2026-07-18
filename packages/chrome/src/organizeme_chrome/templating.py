from jinja2 import ChoiceLoader, Environment, PackageLoader

from organizeme_chrome.cdn import ALPINE_CDN
from organizeme_chrome.design import (
    BADGE_VARIANT_CLASSES,
    BUTTON_VARIANT_CLASSES,
    DENSITY_CARD_PADDING,
    DENSITY_PADDING,
    FOCUS_RING,
    STATUS_VARIANT_CLASSES,
)
from organizeme_chrome.json_filter import tojson_filter
from organizeme_chrome.registry import get_app
from organizeme_chrome.theme import theme_attr


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
    env.globals["ALPINE_CDN"] = ALPINE_CDN
    env.globals["BUTTON_VARIANT_CLASSES"] = BUTTON_VARIANT_CLASSES
    env.globals["BADGE_VARIANT_CLASSES"] = BADGE_VARIANT_CLASSES
    env.globals["STATUS_VARIANT_CLASSES"] = STATUS_VARIANT_CLASSES
    env.globals["DENSITY_PADDING"] = DENSITY_PADDING
    env.globals["DENSITY_CARD_PADDING"] = DENSITY_CARD_PADDING
    env.globals["FOCUS_RING"] = FOCUS_RING
    env.filters["tojson"] = tojson_filter
