from jinja2 import Environment

from organizeme_chrome.registry import list_apps
from organizeme_chrome.templating import register_chrome


def test_nav_items_are_merged_across_all_registered_apps() -> None:
    # Since R6, /dashboard is served by event-creator while the rest of the sidebar is served by
    # the Host — but both services must render the same unified sidebar, so nav_items can't be
    # scoped to just the caller's own registry entry.
    env = Environment()

    register_chrome(env, app_service_name="organizeme")

    expected_paths = [item.path for entry in list_apps() for item in entry.nav]
    assert [item.path for item in env.globals["nav_items"]] == expected_paths
    assert "/dashboard" in [item.path for item in env.globals["nav_items"]]


def test_settings_tabs_are_scoped_to_the_callers_own_app() -> None:
    env = Environment()

    register_chrome(env, app_service_name="event-creator")

    assert env.globals["settings_tabs"] == []
