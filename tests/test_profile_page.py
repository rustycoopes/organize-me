import uuid

from httpx import AsyncClient


def unique_email() -> str:
    return f"profile-test-{uuid.uuid4().hex}@example.com"


async def test_profile_page_redirects_anonymous_visitor_to_login(client: AsyncClient) -> None:
    response = await client.get("/profile")

    assert response.status_code in (302, 303, 307)
    assert response.headers["location"] == "/login"


async def test_profile_page_renders_current_values_for_logged_in_user(
    client: AsyncClient,
) -> None:
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})

    response = await client.get("/profile")

    assert response.status_code == 200
    body = response.text
    # design-refresh Slice 4: profile.html no longer renders a static value="..." attribute -
    # the fields are Alpine x-model-bound to profile_data, seeded via the JSON blob in x-data.
    assert f'&#34;email&#34;: &#34;{email}&#34;' in body
    assert 'id="email"' in body


async def test_profile_page_defaults_to_light_theme(client: AsyncClient) -> None:
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})

    response = await client.get("/profile")

    assert response.status_code == 200
    assert '<html lang="en" class="">' in response.text


async def test_profile_page_reflects_dark_mode_after_api_toggle(client: AsyncClient) -> None:
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})

    patch_response = await client.patch("/api/v1/users/me", json={"dark_mode": True})
    assert patch_response.status_code == 200

    response = await client.get("/profile")

    assert response.status_code == 200
    assert '<html lang="en" class="dark">' in response.text


async def test_profile_page_has_delete_confirmation_modal(client: AsyncClient) -> None:
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})

    response = await client.get("/profile")

    assert response.status_code == 200
    body = response.text
    assert '<dialog' in body
    assert 'x-ref="deleteModal"' in body
    assert "Delete permanently" in body
