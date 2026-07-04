import uuid
from urllib.parse import parse_qs, urlparse

from httpx import AsyncClient, Response

from app.auth.oauth import get_google_oauth_client
from app.core.config import get_settings


def unique_email() -> str:
    return f"google-oauth-test-{uuid.uuid4().hex}@example.com"


class FakeGoogleOAuth2:
    """Stands in for httpx_oauth's real GoogleOAuth2 client - never calls Google."""

    name = "google"

    def __init__(
        self,
        email: str | None,
        account_id: str | None = None,
        raise_on_access_token: bool = False,
    ) -> None:
        self.email = email
        self.account_id = account_id or f"fake-google-account-{uuid.uuid4().hex}"
        self.raise_on_access_token = raise_on_access_token

    async def get_authorization_url(
        self,
        redirect_uri: str,
        state: str | None = None,
        scope: list[str] | None = None,
        **_: object,
    ) -> str:
        return f"https://accounts.google.com/o/oauth2/v2/auth?redirect_uri={redirect_uri}&state={state}"

    async def get_access_token(
        self, code: str, redirect_uri: str, code_verifier: str | None = None
    ) -> dict[str, str]:
        if self.raise_on_access_token:
            from httpx_oauth.oauth2 import GetAccessTokenError

            raise GetAccessTokenError("simulated Google token-exchange failure")
        return {"access_token": f"fake-access-token-for-{code}", "token_type": "Bearer"}

    async def get_id_email(self, token: str) -> tuple[str, str | None]:
        return self.account_id, self.email


async def google_login(
    client: AsyncClient,
    email: str | None,
    account_id: str | None = None,
    raise_on_access_token: bool = False,
) -> Response:
    """Drives the full /google -> /google/callback flow against a fake OAuth client."""
    from app.main import app

    fake_client = FakeGoogleOAuth2(
        email=email, account_id=account_id, raise_on_access_token=raise_on_access_token
    )
    app.dependency_overrides[get_google_oauth_client] = lambda: fake_client
    try:
        authorize_response = await client.get("/api/v1/auth/google", follow_redirects=False)
        location = authorize_response.headers["location"]
        state = parse_qs(urlparse(location).query)["state"][0]
        return await client.get(
            "/api/v1/auth/google/callback",
            params={"code": "fake-code", "state": state},
            follow_redirects=False,
        )
    finally:
        del app.dependency_overrides[get_google_oauth_client]


async def test_google_authorize_redirects_to_google_with_client_id_and_redirect_uri(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/v1/auth/google", follow_redirects=False)

    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("https://accounts.google.com/")
    query = parse_qs(urlparse(location).query)
    settings = get_settings()
    assert query["client_id"][0] == settings.google_oauth_client_id
    assert query["redirect_uri"][0] == settings.google_oauth_redirect_uri
    assert "state" in query


async def test_google_callback_creates_new_user_on_first_login(client: AsyncClient) -> None:
    email = unique_email()

    response = await google_login(client, email)

    # The callback is reached via a full-page browser redirect from Google, so on success it
    # must 302 the browser back into the app - a bare 204 (fastapi-users' default cookie login
    # response) leaves the browser stranded on Google's consent page (issue #27).
    assert response.status_code == 302
    assert response.headers["location"] == "/profile"
    me = await client.get("/api/v1/users/me")
    assert me.status_code == 200
    assert me.json()["email"] == email


async def test_google_callback_redirects_into_app_on_success_carrying_auth_cookie(
    client: AsyncClient,
) -> None:
    """Regression test for issue #27: a successful callback must redirect the browser into the
    app AND set the auth cookie on that same redirect response. Returning fastapi-users' bare
    204 login response left the browser sitting on Google's page, appearing to hang forever."""
    response = await google_login(client, unique_email())

    assert response.status_code == 302
    assert response.headers["location"] == "/profile"
    set_cookie_headers = response.headers.get_list("set-cookie")
    assert any(h.lower().startswith("organizeme_auth=") for h in set_cookie_headers)


async def test_google_callback_reuses_existing_user_on_repeat_login(client: AsyncClient) -> None:
    email = unique_email()

    await google_login(client, email)
    first_id = (await client.get("/api/v1/users/me")).json()["id"]

    await client.post("/api/v1/auth/logout")
    await google_login(client, email)
    second_id = (await client.get("/api/v1/users/me")).json()["id"]

    assert second_id == first_id


async def test_google_callback_links_to_existing_email_password_account(
    client: AsyncClient,
) -> None:
    email = unique_email()
    await client.post(
        "/api/v1/auth/register", data={"email": email, "password": "correct-horse-battery"}
    )
    register_me = await client.post(
        "/api/v1/auth/login", data={"email": email, "password": "correct-horse-battery"}
    )
    assert register_me.status_code == 302  # success redirect to /profile (issue #43)
    password_account_id = (await client.get("/api/v1/users/me")).json()["id"]
    await client.post("/api/v1/auth/logout")

    response = await google_login(client, email)

    assert response.status_code == 302
    assert response.headers["location"] == "/profile"
    me = await client.get("/api/v1/users/me")
    assert me.json()["id"] == password_account_id


async def test_google_callback_sets_same_jwt_cookie_as_email_password_login(
    client: AsyncClient,
) -> None:
    response = await google_login(client, unique_email())

    set_cookie_headers = response.headers.get_list("set-cookie")
    auth_cookie = next(h for h in set_cookie_headers if h.lower().startswith("organizeme_auth="))
    assert "httponly" in auth_cookie.lower()
    assert "max-age=604800" in auth_cookie.lower()


async def test_google_callback_rejects_tampered_state(client: AsyncClient) -> None:
    # /google/callback is only ever reached via a full-page browser redirect from Google, so
    # failures redirect back to the originating form (with a query flag the template renders as
    # an error banner) instead of a raw 400 JSON body the user would otherwise see rendered blank.
    tampered = await client.get(
        "/api/v1/auth/google/callback",
        params={"code": "fake-code", "state": "not-a-valid-state"},
        follow_redirects=False,
    )

    assert tampered.status_code == 302
    assert tampered.headers["location"] == "/login?error=google_auth_failed"


async def test_google_callback_without_email_redirects_to_origin_with_error(
    client: AsyncClient,
) -> None:
    response = await google_login(client, email=None)

    assert response.status_code == 302
    assert response.headers["location"] == "/login?error=google_auth_failed"


async def test_google_callback_handles_token_exchange_failure_gracefully(
    client: AsyncClient,
) -> None:
    """A replayed/expired authorization code (e.g. the user reloads the callback URL) makes
    Google's token endpoint reject the exchange - this must redirect with the same friendly
    error banner as every other failure path, not surface an unhandled 500."""
    response = await google_login(client, unique_email(), raise_on_access_token=True)

    assert response.status_code == 302
    assert response.headers["location"] == "/login?error=google_auth_failed"


async def test_google_callback_rejects_non_ascii_csrf_cookie(client: AsyncClient) -> None:
    """secrets.compare_digest raises TypeError on non-ASCII input; a raw HTTP client (not a
    real browser, and not bound by httpx's own client-side header encoding) can send an
    arbitrary Cookie header directly, so this must be rejected cleanly instead of crashing."""
    from httpx import Headers

    authorize_response = await client.get("/api/v1/auth/google", follow_redirects=False)
    state = parse_qs(urlparse(authorize_response.headers["location"]).query)["state"][0]

    response = await client.get(
        "/api/v1/auth/google/callback",
        params={"code": "fake-code", "state": state},
        headers=Headers({"cookie": "organizeme_oauth_csrf=café"}, encoding="utf-8"),
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/login?error=google_auth_failed"


async def test_google_callback_google_denied_consent_redirects_to_originating_page(
    client: AsyncClient,
) -> None:
    """Covers clicking "Cancel" on Google's consent screen: Google redirects back with
    error=access_denied and no code, but does echo the original state - the register page's
    button should send the user back to /register, not always /login."""
    authorize_response = await client.get(
        "/api/v1/auth/google", params={"next": "/register"}, follow_redirects=False
    )
    state = parse_qs(urlparse(authorize_response.headers["location"]).query)["state"][0]

    response = await client.get(
        "/api/v1/auth/google/callback",
        params={"error": "access_denied", "state": state},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/register?error=google_auth_failed"


async def test_login_page_renders_google_sign_in_button(client: AsyncClient) -> None:
    response = await client.get("/login")

    assert response.status_code == 200
    assert 'href="/api/v1/auth/google?next=/login"' in response.text


async def test_login_page_renders_error_banner_when_google_auth_failed(
    client: AsyncClient,
) -> None:
    response = await client.get("/login", params={"error": "google_auth_failed"})

    assert response.status_code == 200
    assert "Google sign-in failed" in response.text


async def test_register_page_renders_google_sign_in_button(client: AsyncClient) -> None:
    response = await client.get("/register")

    assert response.status_code == 200
    assert 'href="/api/v1/auth/google?next=/register"' in response.text
