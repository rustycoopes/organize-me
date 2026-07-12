from jinja2 import ChoiceLoader, Environment, PackageLoader

from organizeme_chrome.registry import get_app
from organizeme_chrome.theme import ALPINE_CDN, DAISYUI_CDN, TAILWIND_CDN, theme_attr


def register_chrome(env: Environment, app_service_name: str) -> None:
    """Wire a host app's Jinja environment up to this package's chrome.

    Adds the package's template directory to the environment's loader (so hosted templates can
    `{% extends "chrome_authenticated_base.html" %}` / import `macros/chrome_tabs.html`) and
    exposes the app's nav items, settings tabs, theme config, and CDN links as globals.
    """
    package_loader = PackageLoader("organizeme_chrome", "templates")
    env.loader = (
        ChoiceLoader([env.loader, package_loader]) if env.loader is not None else package_loader
    )

    app = get_app(app_service_name)
    env.globals["nav_items"] = app.nav
    env.globals["settings_tabs"] = app.settings_tabs
    env.globals["theme_attr"] = theme_attr
    env.globals["TAILWIND_CDN"] = TAILWIND_CDN
    env.globals["ALPINE_CDN"] = ALPINE_CDN
    env.globals["DAISYUI_CDN"] = DAISYUI_CDN
