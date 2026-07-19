from collections.abc import Iterator

import pytest
from conftest import FakeRegistrySource

from organizeme_chrome.registry import (
    AppEntry,
    AppNavItem,
    SettingsTab,
    configure_registry_source,
    get_app,
    list_apps,
    reset_registry_source,
)


@pytest.fixture(autouse=True)
def _reset_source_after_each_test() -> Iterator[None]:
    # Registry-decoupling Slice 3 (organize-me#220): there is no compiled-in default anymore, so
    # every test in this file must configure its own source and this fixture guarantees no test
    # leaks a configured source into the next one.
    try:
        yield
    finally:
        reset_registry_source()


def _sample_apps() -> list[AppEntry]:
    return [
        AppEntry(
            service_name="organizeme",
            nav=[AppNavItem("/settings", "Settings"), AppNavItem("/profile", "Profile")],
            settings_tabs=[],
        ),
        AppEntry(
            service_name="event-creator",
            nav=[AppNavItem("/dashboard", "Dashboard")],
            settings_tabs=[SettingsTab("storage", "Storage")],
            api_prefixes=["/api/v1/events"],
        ),
        AppEntry(
            service_name="doc-library",
            nav=[AppNavItem("/doc-library", "Doc Library")],
            settings_tabs=[],
            api_prefixes=["/api/v1/doc-links", "/doc-library/fragments"],
        ),
    ]


def test_list_apps_reads_the_configured_source() -> None:
    configure_registry_source(FakeRegistrySource(_sample_apps()))

    service_names = [app.service_name for app in list_apps()]

    assert service_names == ["organizeme", "event-creator", "doc-library"]


def test_get_app_returns_the_matching_entry() -> None:
    configure_registry_source(FakeRegistrySource(_sample_apps()))

    app = get_app("doc-library")

    assert app.service_name == "doc-library"
    assert [item.path for item in app.nav] == ["/doc-library"]
    assert app.api_prefixes == ["/api/v1/doc-links", "/doc-library/fragments"]


def test_get_app_raises_for_unknown_service() -> None:
    configure_registry_source(FakeRegistrySource(_sample_apps()))

    with pytest.raises(KeyError):
        get_app("does-not-exist")


def test_configure_registry_source_is_what_list_apps_and_get_app_actually_read() -> None:
    # Registry-decoupling (organize-me#218): confirms the configured source, not some other
    # global state, is what a consumer reads.
    fake_app = AppEntry(
        service_name="fake-app",
        nav=[AppNavItem("/fake", "Fake")],
        settings_tabs=[],
    )
    configure_registry_source(FakeRegistrySource([fake_app]))

    assert [app.service_name for app in list_apps()] == ["fake-app"]
    assert get_app("fake-app") is fake_app


def test_list_apps_raises_before_any_source_is_configured() -> None:
    # Registry-decoupling Slice 3 (organize-me#220): a genuine behavior change - Slices 1-2 relied
    # on the now-deleted compiled-in fallback masking this case entirely.
    with pytest.raises(RuntimeError, match="not configured"):
        list_apps()


def test_get_app_raises_before_any_source_is_configured() -> None:
    with pytest.raises(RuntimeError, match="not configured"):
        get_app("organizeme")


def test_reset_registry_source_clears_a_previously_configured_source() -> None:
    configure_registry_source(FakeRegistrySource(_sample_apps()))
    assert list_apps() != []

    reset_registry_source()

    with pytest.raises(RuntimeError, match="not configured"):
        list_apps()


def test_configure_registry_source_called_twice_fully_replaces_the_first_source() -> None:
    # Now that there's no compiled-in fallback to catch a stray leftover source, a second
    # configure_registry_source() call must win outright, not merge with or defer to the first.
    configure_registry_source(FakeRegistrySource(_sample_apps()))

    other_app = AppEntry(service_name="other-app", nav=[], settings_tabs=[])
    configure_registry_source(FakeRegistrySource([other_app]))

    assert [app.service_name for app in list_apps()] == ["other-app"]
