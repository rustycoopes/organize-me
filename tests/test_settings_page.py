"""Tests for the Settings page shell (issue #46).

R7 (docs/features/platform-restructure/WBS/slice-R7.md): the Host renders only the Settings *shell*
here (the tab-bar chrome, driven by aggregating every registered app's settings_tabs — see
app/pages/settings.py) — Storage, Notifications, and Preferences tab *content* lives in the
independent event-creator service; ha-dashboard's own "HA Dashboard" tab (its Slice 3) lives in
ha-dashboard. Each is fetched as an HTML fragment via HTMX from its *owning* app
(GET /settings/{service_name}/{tab.id}) — never hardcoded to a single service. These tests
therefore only cover the shell: tab-bar rendering and each panel's HTMX wiring, not the tab
content itself (that's each owning app's own test suite, in its own repo).
"""

import uuid

from httpx import AsyncClient


def unique_email() -> str:
    return f"settings-page-{uuid.uuid4().hex}@example.com"


async def _register_and_login(client: AsyncClient) -> str:
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})
    return email


async def test_settings_page_redirects_anonymous_visitor_to_login(client: AsyncClient) -> None:
    response = await client.get("/settings")

    assert response.status_code in (302, 303, 307)
    assert response.headers["location"] == "/login"


async def test_settings_page_renders_tab_bar_aggregated_across_every_registered_app(
    client: AsyncClient,
) -> None:
    await _register_and_login(client)

    response = await client.get("/settings")

    assert response.status_code == 200
    body = response.text
    assert "Settings" in body
    assert 'role="tablist"' in body
    # Tabs are declared on each owning app's own app-registry entry, not organizeme's own — see
    # packages/chrome/src/organizeme_chrome/registry.py. event-creator contributes three;
    # ha-dashboard contributes its own "HA Dashboard" tab (Slice 3 there).
    assert "Storage" in body
    assert "Notifications" in body
    assert "Preferences" in body
    assert "HA Dashboard" in body


async def test_settings_page_defaults_the_active_tab_to_the_first_registered_tab(
    client: AsyncClient,
) -> None:
    await _register_and_login(client)

    response = await client.get("/settings")

    assert response.status_code == 200
    assert "activeTab: 'storage'" in response.text


async def test_settings_page_fetches_each_tabs_content_from_its_owning_app_via_htmx(
    client: AsyncClient,
) -> None:
    await _register_and_login(client)

    response = await client.get("/settings")

    assert response.status_code == 200
    body = response.text
    # Each tab's panel is a same-origin HTMX fragment fetch to its owning app's own service_name —
    # never rendered inline by the Host, and never hardcoded to a single service.
    assert 'id="storage-tab-panel"' in body
    assert 'hx-get="/settings/event-creator/storage"' in body
    assert 'id="notifications-tab-panel"' in body
    assert 'hx-get="/settings/event-creator/notifications"' in body
    assert 'id="preferences-tab-panel"' in body
    assert 'hx-get="/settings/event-creator/preferences"' in body
    assert 'id="ha-dashboard-tab-panel"' in body
    assert 'hx-get="/settings/ha-dashboard/ha-dashboard"' in body
    assert "htmx.org" in body


async def test_settings_page_only_the_first_tab_panel_is_visible_without_x_cloak(
    client: AsyncClient,
) -> None:
    # The first tab (storage) matches the default activeTab and renders without x-cloak, so it's
    # visible before Alpine hydrates; the rest are x-cloak'd so they don't flash visible.
    await _register_and_login(client)

    response = await client.get("/settings")

    body = response.text
    storage_panel_start = body.index('id="storage-tab-panel"')
    storage_panel = body[storage_panel_start : body.index(">", storage_panel_start)]
    assert "x-cloak" not in storage_panel

    notifications_panel_start = body.index('id="notifications-tab-panel"')
    notifications_panel = body[
        notifications_panel_start : body.index(">", notifications_panel_start)
    ]
    assert "x-cloak" in notifications_panel

    ha_dashboard_panel_start = body.index('id="ha-dashboard-tab-panel"')
    ha_dashboard_panel = body[
        ha_dashboard_panel_start : body.index(">", ha_dashboard_panel_start)
    ]
    assert "x-cloak" in ha_dashboard_panel
