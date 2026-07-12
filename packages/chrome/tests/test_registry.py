import pytest

from organizeme_chrome.registry import get_app, list_apps


def test_list_apps_includes_organizeme_and_event_creator() -> None:
    service_names = [app.service_name for app in list_apps()]

    assert "organizeme" in service_names
    assert "event-creator" in service_names


def test_get_app_returns_the_matching_entry() -> None:
    app = get_app("organizeme")

    assert app.service_name == "organizeme"
    assert [item.path for item in app.nav] == [
        "/upload",
        "/processing",
        "/logs",
        "/prompt",
        "/settings",
        "/profile",
    ]
    assert [tab.id for tab in app.settings_tabs] == ["storage", "notifications"]


def test_get_app_event_creator_owns_dashboard() -> None:
    # R6: /dashboard is served by the independent event-creator service, not the Host.
    app = get_app("event-creator")

    assert [item.path for item in app.nav] == ["/dashboard"]
    assert app.settings_tabs == []


def test_get_app_raises_for_unknown_service() -> None:
    with pytest.raises(KeyError):
        get_app("does-not-exist")
