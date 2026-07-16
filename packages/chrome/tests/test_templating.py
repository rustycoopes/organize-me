from jinja2 import Environment
from markupsafe import Markup

from organizeme_chrome.templating import register_chrome


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
