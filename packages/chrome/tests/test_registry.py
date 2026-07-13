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
    # R7: Storage/Notifications/Preferences moved to "event-creator" — the Host still renders the
    # Settings shell but no longer owns any tab's content.
    assert app.settings_tabs == []
    assert app.api_prefixes == []


def test_get_app_event_creator_owns_dashboard() -> None:
    # R6: /dashboard is served by the independent event-creator service, not the Host.
    app = get_app("event-creator")

    assert [item.path for item in app.nav] == ["/dashboard"]


def test_get_app_event_creator_owns_settings_tabs_and_api_prefixes() -> None:
    # R7: storage-connection + settings functionality migrated into Event Creator.
    app = get_app("event-creator")

    assert [tab.id for tab in app.settings_tabs] == ["storage", "notifications", "preferences"]
    assert [tab.label for tab in app.settings_tabs] == ["Storage", "Notifications", "Preferences"]
    assert app.api_prefixes == [
        "/api/v1/storage-config",
        "/api/v1/user-settings",
        "/settings/event-creator",
    ]


def test_get_app_raises_for_unknown_service() -> None:
    with pytest.raises(KeyError):
        get_app("does-not-exist")
