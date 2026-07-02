import uuid

from httpx import AsyncClient


def unique_email() -> str:
    return f"auth-test-{uuid.uuid4().hex}@example.com"


async def test_register_with_valid_email_and_password_returns_201(client: AsyncClient) -> None:
    email = unique_email()

    response = await client.post(
        "/api/v1/auth/register", data={"email": email, "password": "correct-horse-battery"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == email
    assert "password" not in body
    assert "hashed_password" not in body


async def test_register_with_malformed_email_returns_4xx_not_500(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register", data={"email": "not-an-email", "password": "correct-horse-battery"}
    )

    assert 400 <= response.status_code < 500


async def test_register_with_duplicate_email_returns_4xx(client: AsyncClient) -> None:
    email = unique_email()
    payload = {"email": email, "password": "correct-horse-battery"}

    first = await client.post("/api/v1/auth/register", data=payload)
    assert first.status_code == 201

    second = await client.post("/api/v1/auth/register", data=payload)

    assert 400 <= second.status_code < 500


async def test_register_with_case_different_duplicate_email_returns_4xx(client: AsyncClient) -> None:
    email = unique_email()
    payload = {"email": email, "password": "correct-horse-battery"}

    first = await client.post("/api/v1/auth/register", data=payload)
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/auth/register",
        data={"email": email.upper(), "password": "correct-horse-battery"},
    )

    assert 400 <= second.status_code < 500


async def test_login_with_correct_credentials_sets_httponly_cookie(client: AsyncClient) -> None:
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})

    response = await client.post("/api/v1/auth/login", data={"email": email, "password": password})

    assert response.status_code in (200, 204)
    set_cookie_headers = response.headers.get_list("set-cookie")
    assert len(set_cookie_headers) == 1
    assert "httponly" in set_cookie_headers[0].lower()


async def test_login_cookie_expiry_is_seven_days(client: AsyncClient) -> None:
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})

    response = await client.post("/api/v1/auth/login", data={"email": email, "password": password})

    set_cookie_header = response.headers.get_list("set-cookie")[0]
    assert "max-age=604800" in set_cookie_header.lower()


async def test_login_with_wrong_password_returns_401(client: AsyncClient) -> None:
    email = unique_email()
    await client.post(
        "/api/v1/auth/register", data={"email": email, "password": "correct-horse-battery"}
    )

    response = await client.post(
        "/api/v1/auth/login", data={"email": email, "password": "wrong-password"}
    )

    assert response.status_code == 401


async def test_login_with_unknown_email_returns_401(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        data={"email": unique_email(), "password": "whatever-password"},
    )

    assert response.status_code == 401


async def test_protected_endpoint_rejects_missing_cookie(client: AsyncClient) -> None:
    response = await client.get("/api/v1/users/me")

    assert response.status_code == 401


async def test_protected_endpoint_reachable_with_valid_cookie(client: AsyncClient) -> None:
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})

    response = await client.get("/api/v1/users/me")

    assert response.status_code == 200
    assert response.json()["email"] == email


async def test_logout_clears_the_cookie(client: AsyncClient) -> None:
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})

    response = await client.post("/api/v1/auth/logout")

    assert response.status_code in (200, 204)
    set_cookie_header = response.headers.get_list("set-cookie")[0]
    assert "max-age=0" in set_cookie_header.lower()

    follow_up = await client.get("/api/v1/users/me")
    assert follow_up.status_code == 401


async def test_register_page_renders_daisyui_form_with_expected_fields(client: AsyncClient) -> None:
    response = await client.get("/register")

    assert response.status_code == 200
    body = response.text
    assert 'name="email"' in body
    assert 'type="email"' in body
    assert 'name="password"' in body
    assert 'type="password"' in body
    assert 'action="/api/v1/auth/register"' in body
    assert "input-bordered" in body  # DaisyUI form control class


async def test_login_page_renders_daisyui_form_with_expected_fields(client: AsyncClient) -> None:
    response = await client.get("/login")

    assert response.status_code == 200
    body = response.text
    assert 'name="email"' in body
    assert 'type="email"' in body
    assert 'name="password"' in body
    assert 'type="password"' in body
    assert 'action="/api/v1/auth/login"' in body
    assert "input-bordered" in body
