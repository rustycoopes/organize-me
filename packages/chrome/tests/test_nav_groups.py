from organizeme_chrome.nav_groups import build_nav_groups, flat_nav_items
from organizeme_chrome.registry import AppEntry, AppNavItem

_EVENT_CREATOR = AppEntry(
    service_name="event-creator",
    nav=[AppNavItem("/dashboard", "Dashboard"), AppNavItem("/prompt", "Prompt")],
    settings_tabs=[],
)
_SOME_OTHER_APP = AppEntry(
    service_name="some-other-app",
    nav=[AppNavItem("/some-other-app/only-page", "Only Page")],
    settings_tabs=[],
)
_ORGANIZEME = AppEntry(
    service_name="organizeme",
    nav=[AppNavItem("/settings", "Settings"), AppNavItem("/profile", "Profile")],
    settings_tabs=[],
)
_APPS = [_EVENT_CREATOR, _SOME_OTHER_APP, _ORGANIZEME]


def test_apps_with_no_stored_preference_default_to_expanded() -> None:
    groups = build_nav_groups(_APPS, collapsed={}, current_path="/anything")

    assert all(group.collapsed is False for group in groups)


def test_stored_collapsed_state_is_honored() -> None:
    groups = build_nav_groups(
        _APPS, collapsed={"event-creator": True}, current_path="/anything"
    )

    by_service = {group.service_name: group for group in groups}
    assert by_service["event-creator"].collapsed is True
    assert by_service["some-other-app"].collapsed is False


def test_current_page_forces_its_own_group_open_without_mutating_input() -> None:
    collapsed = {"event-creator": True}

    groups = build_nav_groups(_APPS, collapsed=collapsed, current_path="/dashboard")

    by_service = {group.service_name: group for group in groups}
    assert by_service["event-creator"].collapsed is False
    # The override must not leak back into the caller's stored-preference dict.
    assert collapsed == {"event-creator": True}


def test_current_page_in_a_different_group_does_not_force_open_unrelated_groups() -> None:
    groups = build_nav_groups(
        _APPS,
        collapsed={"event-creator": True, "some-other-app": True},
        current_path="/some-other-app/only-page",
    )

    by_service = {group.service_name: group for group in groups}
    assert by_service["event-creator"].collapsed is True
    assert by_service["some-other-app"].collapsed is False


def test_flat_service_names_are_excluded_from_groups_even_with_one_nav_item() -> None:
    single_item_app = AppEntry(
        service_name="tiny-app", nav=[AppNavItem("/tiny", "Tiny")], settings_tabs=[]
    )

    groups = build_nav_groups([single_item_app, _ORGANIZEME], collapsed={}, current_path="/tiny")

    service_names = [group.service_name for group in groups]
    assert service_names == ["tiny-app"]
    assert "organizeme" not in service_names


def test_group_order_matches_input_app_order() -> None:
    groups = build_nav_groups(_APPS, collapsed={}, current_path="/nowhere")

    assert [group.service_name for group in groups] == ["event-creator", "some-other-app"]


def test_group_label_is_humanized_from_service_name() -> None:
    groups = build_nav_groups(_APPS, collapsed={}, current_path="/nowhere")

    by_service = {group.service_name: group for group in groups}
    assert by_service["event-creator"].label == "Event Creator"
    assert by_service["some-other-app"].label == "Some Other App"


def test_flat_nav_items_returns_only_flat_service_items_in_order() -> None:
    items = flat_nav_items(_APPS)

    assert [item.path for item in items] == ["/settings", "/profile"]


def test_flat_nav_items_empty_when_no_flat_app_registered() -> None:
    items = flat_nav_items([_EVENT_CREATOR, _SOME_OTHER_APP])

    assert items == []
