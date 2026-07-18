import html
import json
from collections.abc import Iterator

import pytest
from jinja2 import Environment
from markupsafe import Markup

from organizeme_chrome.registry import (
    AppEntry,
    AppNavItem,
    SettingsTab,
    configure_registry_source,
    reset_registry_source,
)
from organizeme_chrome.templating import register_chrome


class _FakeSource:
    def __init__(self, apps: list[AppEntry]) -> None:
        self._apps = apps

    def get_apps(self) -> list[AppEntry]:
        return self._apps


@pytest.fixture(autouse=True)
def _configure_sample_registry() -> Iterator[None]:
    # register_chrome() calls get_app(), which needs a configured RegistrySource - registry-
    # decoupling Slice 3 (organize-me#220) removed the compiled-in fallback these tests used to
    # read implicitly.
    configure_registry_source(
        _FakeSource(
            [
                AppEntry(service_name="organizeme", nav=[], settings_tabs=[]),
                AppEntry(
                    service_name="event-creator",
                    nav=[AppNavItem("/dashboard", "Dashboard")],
                    settings_tabs=[
                        SettingsTab("storage", "Storage"),
                        SettingsTab("notifications", "Notifications"),
                        SettingsTab("preferences", "Preferences"),
                    ],
                ),
            ]
        )
    )
    try:
        yield
    finally:
        reset_registry_source()


def test_tojson_filter_is_registered_and_produces_safe_markup() -> None:
    env = Environment()

    register_chrome(env, app_service_name="organizeme")

    result = env.filters["tojson"]({"event-creator": True})
    assert isinstance(result, Markup)
    assert "event-creator" in result
    assert "true" in result
    # Must not contain a literal, unescaped `"` — this is embedded inside a double-quoted HTML
    # attribute (x-data="...") in chrome_authenticated_base.html; an unescaped quote there
    # truncates the attribute value at the first key/value pair on every render.
    assert '"' not in result


def test_tojson_filter_output_decodes_to_valid_json() -> None:
    # Regression test: an earlier version of this filter replaced every `"` with the JS unicode
    # escape sequence for it, which is only valid *inside* a JS string literal - but json.dumps's
    # own quote-delimiter characters sit outside any string context, so that produced invalid
    # JS/JSON that silently broke every Alpine x-data expression using it. HTML-entity escaping
    # (this filter's actual approach) must round-trip: what the browser's HTML parser decodes
    # from the attribute value has to be valid JSON again, since that's what Alpine hands to its
    # JS evaluator.
    env = Environment()
    register_chrome(env, app_service_name="organizeme")

    value = {"event-creator": True, "some-other-app": False}
    result = env.filters["tojson"](value)

    decoded = html.unescape(str(result))
    assert json.loads(decoded) == value


def test_settings_tabs_are_scoped_to_the_callers_own_app() -> None:
    env = Environment()

    # R7: Storage/Notifications/Preferences moved to "event-creator" — "organizeme" (the caller
    # here) no longer owns any Settings tab's content, though it still renders the Settings shell
    # itself (app/pages/settings.py passes event-creator's tabs into the template context
    # explicitly for that purpose, rather than relying on this scoped-to-caller global).
    register_chrome(env, app_service_name="organizeme")

    assert env.globals["settings_tabs"] == []


def test_settings_tabs_scoped_to_event_creator_include_its_own_tabs() -> None:
    env = Environment()

    register_chrome(env, app_service_name="event-creator")

    settings_tabs = env.globals["settings_tabs"]
    assert isinstance(settings_tabs, list)
    assert [tab.id for tab in settings_tabs] == ["storage", "notifications", "preferences"]
