import pytest

from organizeme_chrome.registry import get_app, list_apps


def test_list_apps_includes_organizeme_and_event_creator() -> None:
    service_names = [app.service_name for app in list_apps()]

    assert "organizeme" in service_names
    assert "event-creator" in service_names
    assert "doc-library" in service_names


def test_get_app_doc_library_owns_its_own_nav_and_api_prefixes() -> None:
    # Slice 2 (issue #2): a brand-new hosted app, not a migration off the Host.
    app = get_app("doc-library")

    assert [item.path for item in app.nav] == ["/doc-library"]
    assert [item.label for item in app.nav] == ["Doc Library"]
    assert app.settings_tabs == []
    assert app.api_prefixes == ["/api/v1/doc-links", "/doc-library/fragments"]


def test_get_app_returns_the_matching_entry() -> None:
    app = get_app("organizeme")

    assert app.service_name == "organizeme"
    # R11 (QA cutover, #166): Upload/Processing/Logs/Prompt moved to "event-creator" below - the
    # Host now owns only its own auth-adjacent pages.
    assert [item.path for item in app.nav] == [
        "/settings",
        "/profile",
    ]
    # R7: Storage/Notifications/Preferences moved to "event-creator" — the Host still renders the
    # Settings shell but no longer owns any tab's content.
    assert app.settings_tabs == []
    assert app.api_prefixes == []


def test_get_app_event_creator_owns_dashboard_and_r11_migrated_pages() -> None:
    # R6: /dashboard is served by the independent event-creator service, not the Host. R11:
    # Upload/Processing/Logs/Prompt join it, completing the parity slices' (R7-R9) routing cutover.
    app = get_app("event-creator")

    assert [item.path for item in app.nav] == [
        "/dashboard",
        "/upload",
        "/processing",
        "/logs",
        "/prompt",
    ]


def test_get_app_event_creator_owns_settings_tabs_and_api_prefixes() -> None:
    # R7: storage-connection + settings functionality migrated into Event Creator. R11: the
    # Upload/Processing/Logs/Prompt route surface's own API/fragment paths join the same list.
    app = get_app("event-creator")

    assert [tab.id for tab in app.settings_tabs] == ["storage", "notifications", "preferences"]
    assert [tab.label for tab in app.settings_tabs] == ["Storage", "Notifications", "Preferences"]
    assert app.api_prefixes == [
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
    ]


def test_get_app_raises_for_unknown_service() -> None:
    with pytest.raises(KeyError):
        get_app("does-not-exist")
