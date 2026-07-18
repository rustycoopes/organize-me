from httpx import AsyncClient


async def test_landing_page_returns_200_without_auth(client: AsyncClient) -> None:
    response = await client.get("/")

    assert response.status_code == 200


async def test_landing_page_has_hero_features_and_cta_sections(client: AsyncClient) -> None:
    response = await client.get("/")

    body = response.text
    assert 'id="hero"' in body
    assert 'id="features"' in body
    assert 'id="cta"' in body


async def test_landing_page_cta_links_to_register(client: AsyncClient) -> None:
    response = await client.get("/")

    body = response.text
    cta_start = body.index('id="cta"')
    cta_section = body[cta_start : cta_start + 2000]
    assert 'href="/register"' in cta_section


async def test_landing_page_hero_also_links_to_register(client: AsyncClient) -> None:
    response = await client.get("/")

    body = response.text
    hero_start = body.index('id="hero"')
    features_start = body.index('id="features"')
    hero_section = body[hero_start:features_start]
    assert 'href="/register"' in hero_section


async def test_landing_page_has_login_and_register_nav_links(client: AsyncClient) -> None:
    response = await client.get("/")

    body = response.text
    assert 'href="/login"' in body
    assert 'href="/register"' in body


async def test_landing_page_nav_links_resolve_to_200(client: AsyncClient) -> None:
    login_response = await client.get("/login")
    register_response = await client.get("/register")

    assert login_response.status_code == 200
    assert register_response.status_code == 200


async def test_landing_page_has_meta_description(client: AsyncClient) -> None:
    response = await client.get("/")

    assert 'name="description"' in response.text


async def test_landing_page_no_longer_references_tailwind_cdn_or_daisyui(
    client: AsyncClient,
) -> None:
    response = await client.get("/")

    body = response.text
    assert "cdn.tailwindcss.com" not in body
    assert "daisyui" not in body.lower()
    assert '/static/css/app.css' in body


async def test_anonymous_visitor_does_not_get_the_dark_class(client: AsyncClient) -> None:
    """First instance of the class="dark" tracking pattern - see test_profile_page.py for the
    authenticated (User.dark_mode-driven) counterpart."""
    response = await client.get("/")

    assert '<html lang="en" class="">' in response.text


async def test_landing_page_hero_has_the_chat_to_calendar_signature_moment(
    client: AsyncClient,
) -> None:
    response = await client.get("/")

    body = response.text
    hero_start = body.index('id="hero"')
    features_start = body.index('id="features"')
    hero_section = body[hero_start:features_start]
    assert "Let&#39;s meet Thursday" in hero_section or "Let's meet Thursday" in hero_section
