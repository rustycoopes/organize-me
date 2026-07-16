"""Tests for the authenticated sidebar shell + placeholder pages (issue #17).

The sidebar is a shared layout element: rather than re-assert its contents on every
route, these tests check auth-gating on all nav routes and verify the shared sidebar
(presence + documented order) on a representative couple of authenticated routes, per
the issue's "asserted via a shared layout test across at least two routes" criterion.

R13 (#168): Dashboard/Upload/Processing/Logs/Prompt are event-creator-owned routes (moved
there in R11's QA cutover) - the merged sidebar (organizeme_chrome.templating.register_chrome)
still renders links to them (nav_items is merged across every registered app, per that
function's docstring), but the Host's own ASGI app no longer serves them at all, so they're
only exercised here as *links rendered in the sidebar*, not as routes this app's test client can
fetch directly (that's event-creator's own test suite's job now).
"""

import uuid

import pytest
from httpx import AsyncClient

# Every route reachable from the sidebar, in the documented order
# (Dashboard -> Upload -> Processing -> Logs -> Prompt -> Settings -> Profile). Dashboard through
# Prompt are event-creator-owned (see module docstring); only Settings/Profile are routes the
# Host itself serves.
NAV_ROUTES = [
    "/dashboard",
    "/upload",
    "/processing",
    "/logs",
    "/prompt",
    "/settings",
    "/profile",
]

NAV_LABELS_IN_ORDER = [
    "Dashboard",
    "Upload",
    "Processing",
    "Logs",
    "Prompt",
    "Settings",
    "Profile",
]

# Routes the Host's own ASGI app actually serves (Dashboard/Upload/Processing/Logs/Prompt are
# event-creator-owned - see module docstring - and 404 against the Host directly).
HOST_OWNED_ROUTES = ["/settings", "/profile"]


def unique_email() -> str:
    return f"sidebar-test-{uuid.uuid4().hex}@example.com"


async def register_and_login(client: AsyncClient) -> None:
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})


@pytest.mark.parametrize("route", HOST_OWNED_ROUTES)
async def test_nav_route_redirects_anonymous_visitor_to_login(
    client: AsyncClient, route: str
) -> None:
    response = await client.get(route)

    assert response.status_code in (302, 303, 307)
    assert response.headers["location"] == "/login"


@pytest.mark.parametrize("route", HOST_OWNED_ROUTES)
async def test_nav_route_returns_200_when_authenticated(
    client: AsyncClient, route: str
) -> None:
    await register_and_login(client)

    response = await client.get(route)

    assert response.status_code == 200


@pytest.mark.parametrize("route", ["/settings", "/profile"])
async def test_sidebar_lists_every_nav_item_in_order(client: AsyncClient, route: str) -> None:
    await register_and_login(client)

    response = await client.get(route)
    assert response.status_code == 200
    body = response.text

    # Scope assertions to the sidebar nav region: labels like "Settings" also appear in
    # the page <title>/heading, so ordering must be checked within the nav, not the page.
    assert 'id="sidebar-nav"' in body
    nav_html = body[body.index('id="sidebar-nav"') :]

    # Every nav route is linked from the sidebar.
    for nav_route in NAV_ROUTES:
        assert f'href="{nav_route}"' in nav_html

    # ...and the visible labels appear in the documented order.
    positions = [nav_html.index(label) for label in NAV_LABELS_IN_ORDER]
    assert positions == sorted(positions)


@pytest.mark.parametrize("route", ["/settings", "/profile"])
async def test_sidebar_marks_only_the_current_route_active(
    client: AsyncClient, route: str
) -> None:
    await register_and_login(client)

    response = await client.get(route)
    assert response.status_code == 200
    body = response.text

    # Exactly one nav item is flagged as the current page...
    assert body.count('aria-current="page"') == 1
    # ...and it's the link to the route we're on.
    anchor_start = body.index(f'href="{route}"')
    anchor = body[anchor_start : body.index(">", anchor_start)]
    assert 'aria-current="page"' in anchor


async def test_sidebar_offers_logout(client: AsyncClient) -> None:
    await register_and_login(client)

    response = await client.get("/settings")
    assert response.status_code == 200
    body = response.text
    assert "Log out" in body
    assert "/api/v1/auth/logout" in body


@pytest.mark.parametrize("route", ["/", "/login", "/register"])
async def test_sidebar_absent_on_unauthenticated_pages(client: AsyncClient, route: str) -> None:
    response = await client.get(route)

    assert response.status_code == 200
    # The sidebar nav carries a stable landmark id; it must not appear on public pages.
    assert 'id="sidebar-nav"' not in response.text


# --- Collapsible per-app nav groups (sidebar-nav-groups, organize-me#212) -------------------


async def test_new_user_sees_all_groups_expanded_by_default(client: AsyncClient) -> None:
    await register_and_login(client)

    response = await client.get("/settings")
    assert response.status_code == 200
    body = response.text

    assert 'aria-expanded="true"' in body
    assert 'aria-expanded="false"' not in body
    # No stored preference yet -> nothing rendered as pre-hidden.
    assert "display:none" not in body


async def test_collapsed_group_renders_hidden_and_aria_expanded_false(
    client: AsyncClient,
) -> None:
    await register_and_login(client)
    await client.patch(
        "/api/v1/users/me", json={"nav_collapsed_groups": {"event-creator": True}}
    )

    response = await client.get("/settings")
    assert response.status_code == 200
    body = response.text

    assert 'aria-expanded="false"' in body
    group_start = body.index('aria-controls="nav-group-event-creator"')
    group_button = body[max(0, group_start - 400) : group_start]
    assert 'aria-expanded="false"' in group_button


async def test_flat_items_always_visible_regardless_of_any_group_state(
    client: AsyncClient,
) -> None:
    await register_and_login(client)
    await client.patch(
        "/api/v1/users/me", json={"nav_collapsed_groups": {"event-creator": True}}
    )

    response = await client.get("/settings")
    assert response.status_code == 200
    body = response.text

    # Settings/Profile links are present and not inside a hidden ("display:none") container.
    settings_link_index = body.index('href="/settings"')
    profile_link_index = body.index('href="/profile"')
    assert "display:none" not in body[max(0, settings_link_index - 200) : settings_link_index]
    assert "display:none" not in body[max(0, profile_link_index - 200) : profile_link_index]


async def test_group_toggle_button_is_a_real_button_with_aria_controls(
    client: AsyncClient,
) -> None:
    await register_and_login(client)

    response = await client.get("/settings")
    assert response.status_code == 200
    body = response.text

    assert '<button' in body
    assert 'aria-controls="nav-group-event-creator"' in body
