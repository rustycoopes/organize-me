"""Tests for the Dropbox OAuth connect/disconnect flow (#93).

The token exchange is faked via a dependency override (mirrors tests/test_storage_google_drive.py),
so no live Dropbox credentials are touched. The credential cipher is also overridden with a
throwaway key, so the tests don't depend on a configured ENCRYPTION_KEY and can assert the tokens
are stored as ciphertext, not plaintext.
"""

import uuid
from urllib.parse import parse_qs, urlparse

import pytest
from cryptography.fernet import Fernet
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.storage_dropbox import get_cipher_factory, get_token_revoker
from app.auth.oauth import get_dropbox_oauth_client
from app.core.security import CredentialCipher
from app.models.storage_config import StorageConfig
from app.models.user import User
from app.services.user_settings import get_user_settings

_CIPHER_KEY = Fernet.generate_key()
_CIPHER = CredentialCipher(_CIPHER_KEY)


class FakeTokenRevoker:
    """Records tokens passed to it instead of calling Dropbox's revoke endpoint."""

    def __init__(self, *, raise_on_revoke: bool = False) -> None:
        self.revoked: list[str] = []
        self.raise_on_revoke = raise_on_revoke

    async def __call__(self, token: str) -> None:
        self.revoked.append(token)
        if self.raise_on_revoke:
            raise RuntimeError("simulated revoke failure")


class FakeDropboxOAuth2:
    """Stands in for the Dropbox BaseOAuth2 client - never calls Dropbox. Records the params
    get_authorization_url was built with, and returns canned tokens from get_access_token."""

    def __init__(
        self,
        *,
        refresh_token: str | None = "fake-refresh-token",
        raise_on_access_token: bool = False,
    ) -> None:
        self.refresh_token = refresh_token
        self.raise_on_access_token = raise_on_access_token
        self.authorization_args: dict[str, object] = {}

    async def get_authorization_url(
        self,
        redirect_uri: str,
        state: str | None = None,
        scope: list[str] | None = None,
        extras_params: dict[str, str] | None = None,
        **_: object,
    ) -> str:
        self.authorization_args = {
            "redirect_uri": redirect_uri,
            "scope": scope,
            "extras_params": extras_params,
        }
        return f"https://www.dropbox.com/oauth2/authorize?state={state}"

    async def get_access_token(
        self, code: str, redirect_uri: str, code_verifier: str | None = None
    ) -> dict[str, object]:
        if self.raise_on_access_token:
            from httpx_oauth.oauth2 import GetAccessTokenError

            raise GetAccessTokenError("simulated Dropbox token-exchange failure")
        token: dict[str, object] = {
            "access_token": f"fake-access-token-for-{code}",
            "token_type": "bearer",
            "expires_at": 1_900_000_000,
        }
        if self.refresh_token is not None:
            token["refresh_token"] = self.refresh_token
        return token


def unique_email() -> str:
    return f"dropbox-oauth-{uuid.uuid4().hex}@example.com"


async def _register_login_with_config(client: AsyncClient) -> uuid.UUID:
    """Register + log in a user and give them a saved storage config (Connect needs one)."""
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})
    await client.put(
        "/api/v1/storage-config",
        json={"provider": "dropbox", "folder_path": "/OrganizeMe"},
    )
    return uuid.UUID((await client.get("/api/v1/users/me")).json()["id"])


@pytest.fixture
def fake_dropbox_client() -> FakeDropboxOAuth2:
    return FakeDropboxOAuth2()


def _override(
    client_app_fake: FakeDropboxOAuth2, revoker: "FakeTokenRevoker | None" = None
) -> None:
    from app.main import app

    app.dependency_overrides[get_dropbox_oauth_client] = lambda: client_app_fake
    app.dependency_overrides[get_cipher_factory] = lambda: (lambda: _CIPHER)
    if revoker is not None:
        app.dependency_overrides[get_token_revoker] = lambda: revoker


def _clear_overrides() -> None:
    from app.main import app

    app.dependency_overrides.pop(get_dropbox_oauth_client, None)
    app.dependency_overrides.pop(get_cipher_factory, None)
    app.dependency_overrides.pop(get_token_revoker, None)


async def _dropbox_connect(
    client: AsyncClient, fake: FakeDropboxOAuth2, *, code: str = "fake-code"
) -> None:
    """Run the full POST /auth -> GET /callback happy path against the fake client."""
    _override(fake)
    try:
        auth = await client.post("/api/v1/storage-config/dropbox/auth")
        state = parse_qs(urlparse(auth.json()["authorization_url"]).query)["state"][0]
        await client.get(
            "/api/v1/storage-config/dropbox/callback",
            params={"code": code, "state": state},
            follow_redirects=False,
        )
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------------------------
# POST /auth
# ---------------------------------------------------------------------------------------------


async def test_auth_returns_dropbox_consent_url_with_correct_params(client: AsyncClient) -> None:
    from app.main import app

    await _register_login_with_config(client)

    # Uses a real BaseOAuth2 client with test-only credentials (rather than settings-derived
    # ones) - get_authorization_url only builds a URL, never calls out, but asserting against a
    # known client_id keeps this test independent of whether DROPBOX_OAUTH_CLIENT_ID is actually
    # configured in the environment it runs in (no such secret exists yet - Dropbox app
    # registration is a human-setup step, tracked separately from this issue). The cipher
    # factory is overridden so this doesn't depend on ENCRYPTION_KEY either.
    from httpx_oauth.oauth2 import BaseOAuth2

    from app.auth.oauth import DROPBOX_AUTHORIZE_ENDPOINT, DROPBOX_TOKEN_ENDPOINT

    test_client = BaseOAuth2[dict[str, str]](
        "test-dropbox-client-id",
        "test-dropbox-client-secret",
        DROPBOX_AUTHORIZE_ENDPOINT,
        DROPBOX_TOKEN_ENDPOINT,
        DROPBOX_TOKEN_ENDPOINT,
        name="dropbox",
        token_endpoint_auth_method="client_secret_post",
    )
    app.dependency_overrides[get_dropbox_oauth_client] = lambda: test_client
    app.dependency_overrides[get_cipher_factory] = lambda: (lambda: _CIPHER)
    try:
        response = await client.post("/api/v1/storage-config/dropbox/auth")
    finally:
        app.dependency_overrides.pop(get_dropbox_oauth_client, None)
        app.dependency_overrides.pop(get_cipher_factory, None)

    assert response.status_code == 200
    url = response.json()["authorization_url"]
    assert url.startswith("https://www.dropbox.com/oauth2/authorize")
    query = parse_qs(urlparse(url).query)
    assert query["client_id"][0] == "test-dropbox-client-id"
    assert query["redirect_uri"][0].endswith("/api/v1/storage-config/dropbox/callback")
    assert query["scope"][0] == "files.content.write files.content.read"
    assert query["token_access_type"][0] == "offline"
    assert any(
        c.lower().startswith("organizeme_dropbox_oauth_csrf=")
        for c in response.headers.get_list("set-cookie")
    )


async def test_auth_requires_a_saved_config_first(client: AsyncClient) -> None:
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})

    response = await client.post("/api/v1/storage-config/dropbox/auth")

    assert response.status_code == 409
    assert response.json()["detail"] == "save_folder_first"


async def test_auth_requires_authentication(client: AsyncClient) -> None:
    response = await client.post("/api/v1/storage-config/dropbox/auth")
    assert response.status_code == 401


async def test_auth_fails_fast_when_encryption_key_missing(client: AsyncClient) -> None:
    from app.main import app

    await _register_login_with_config(client)

    def _raise_missing_key() -> CredentialCipher:
        raise RuntimeError("ENCRYPTION_KEY is not set")

    app.dependency_overrides[get_cipher_factory] = lambda: _raise_missing_key
    try:
        response = await client.post("/api/v1/storage-config/dropbox/auth")
    finally:
        app.dependency_overrides.pop(get_cipher_factory, None)

    assert response.status_code == 503
    assert response.json()["detail"] == "storage_not_configured"


# ---------------------------------------------------------------------------------------------
# GET /callback
# ---------------------------------------------------------------------------------------------


async def test_callback_stores_encrypted_tokens_and_sets_onboarding_flag(
    client: AsyncClient, db_session: AsyncSession, fake_dropbox_client: FakeDropboxOAuth2
) -> None:
    user_id = await _register_login_with_config(client)

    _override(fake_dropbox_client)
    try:
        auth = await client.post("/api/v1/storage-config/dropbox/auth")
        state = parse_qs(urlparse(auth.json()["authorization_url"]).query)["state"][0]
        callback = await client.get(
            "/api/v1/storage-config/dropbox/callback",
            params={"code": "fake-code", "state": state},
            follow_redirects=False,
        )
    finally:
        _clear_overrides()

    assert callback.status_code == 302
    assert callback.headers["location"] == "/settings?connected=1"

    config = (
        await db_session.scalars(select(StorageConfig).where(StorageConfig.user_id == user_id))
    ).one()
    assert config.oauth_access_token is not None
    assert config.oauth_access_token != "fake-access-token-for-fake-code"
    assert config.oauth_refresh_token is not None
    assert config.oauth_refresh_token != "fake-refresh-token"
    assert _CIPHER.decrypt(config.oauth_access_token) == "fake-access-token-for-fake-code"
    assert _CIPHER.decrypt(config.oauth_refresh_token) == "fake-refresh-token"
    assert config.oauth_token_expires_at is not None
    assert int(config.oauth_token_expires_at.timestamp()) == 1_900_000_000

    settings = await get_user_settings(db_session, user_id)
    assert settings is not None
    assert settings.onboarding_storage_done is True


async def test_callback_marks_config_connected_for_subsequent_reads(
    client: AsyncClient, fake_dropbox_client: FakeDropboxOAuth2
) -> None:
    await _register_login_with_config(client)

    await _dropbox_connect(client, fake_dropbox_client)

    read = await client.get("/api/v1/storage-config")
    assert read.status_code == 200
    assert read.json()["is_connected"] is True


async def test_onboarding_flag_stays_true_after_disconnect(
    client: AsyncClient, db_session: AsyncSession, fake_dropbox_client: FakeDropboxOAuth2
) -> None:
    user_id = await _register_login_with_config(client)
    await _dropbox_connect(client, fake_dropbox_client)

    _override(fake_dropbox_client, FakeTokenRevoker())
    try:
        disconnect = await client.post("/api/v1/storage-config/dropbox/disconnect")
    finally:
        _clear_overrides()
    assert disconnect.status_code == 200
    assert disconnect.json()["is_connected"] is False

    settings = await get_user_settings(db_session, user_id)
    assert settings is not None
    assert settings.onboarding_storage_done is True


async def test_callback_rejects_tampered_state(
    client: AsyncClient, fake_dropbox_client: FakeDropboxOAuth2
) -> None:
    await _register_login_with_config(client)
    _override(fake_dropbox_client)
    try:
        await client.post("/api/v1/storage-config/dropbox/auth")
        response = await client.get(
            "/api/v1/storage-config/dropbox/callback",
            params={"code": "fake-code", "state": "not-a-valid-state"},
            follow_redirects=False,
        )
    finally:
        _clear_overrides()

    assert response.status_code == 302
    assert response.headers["location"] == "/settings?error=dropbox_auth_failed"


async def test_callback_handles_token_exchange_failure(client: AsyncClient) -> None:
    await _register_login_with_config(client)
    failing = FakeDropboxOAuth2(raise_on_access_token=True)
    _override(failing)
    try:
        auth = await client.post("/api/v1/storage-config/dropbox/auth")
        state = parse_qs(urlparse(auth.json()["authorization_url"]).query)["state"][0]
        response = await client.get(
            "/api/v1/storage-config/dropbox/callback",
            params={"code": "fake-code", "state": state},
            follow_redirects=False,
        )
    finally:
        _clear_overrides()

    assert response.status_code == 302
    assert response.headers["location"] == "/settings?error=dropbox_auth_failed"


async def test_callback_handles_missing_encryption_key(
    client: AsyncClient, fake_dropbox_client: FakeDropboxOAuth2
) -> None:
    from app.main import app

    await _register_login_with_config(client)
    _override(fake_dropbox_client)

    def _raise_missing_key() -> CredentialCipher:
        raise RuntimeError("ENCRYPTION_KEY is not set")

    try:
        auth = await client.post("/api/v1/storage-config/dropbox/auth")
        state = parse_qs(urlparse(auth.json()["authorization_url"]).query)["state"][0]
        app.dependency_overrides[get_cipher_factory] = lambda: _raise_missing_key
        response = await client.get(
            "/api/v1/storage-config/dropbox/callback",
            params={"code": "fake-code", "state": state},
            follow_redirects=False,
        )
    finally:
        _clear_overrides()

    assert response.status_code == 302
    assert response.headers["location"] == "/settings?error=storage_not_configured"


async def test_callback_without_auth_cookie_redirects_to_login(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/storage-config/dropbox/callback",
        params={"code": "fake-code", "state": "whatever"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/login"


# ---------------------------------------------------------------------------------------------
# POST /disconnect
# ---------------------------------------------------------------------------------------------


async def test_disconnect_clears_stored_tokens_and_revokes(
    client: AsyncClient, db_session: AsyncSession, fake_dropbox_client: FakeDropboxOAuth2
) -> None:
    user_id = await _register_login_with_config(client)
    await _dropbox_connect(client, fake_dropbox_client)

    revoker = FakeTokenRevoker()
    _override(fake_dropbox_client, revoker)
    try:
        response = await client.post("/api/v1/storage-config/dropbox/disconnect")
    finally:
        _clear_overrides()

    assert response.status_code == 200
    assert response.json()["is_connected"] is False

    # Dropbox's revoke endpoint authenticates via the token being revoked as the Bearer credential,
    # so it must always be the access token (unlike Google's, where the refresh token is preferred).
    assert revoker.revoked == ["fake-access-token-for-fake-code"]

    config = (
        await db_session.scalars(select(StorageConfig).where(StorageConfig.user_id == user_id))
    ).one()
    assert config.oauth_access_token is None
    assert config.oauth_refresh_token is None
    assert config.oauth_token_expires_at is None
    assert config.folder_path == "/OrganizeMe"


async def test_disconnect_still_clears_locally_when_revoke_fails(
    client: AsyncClient, db_session: AsyncSession, fake_dropbox_client: FakeDropboxOAuth2
) -> None:
    user_id = await _register_login_with_config(client)
    await _dropbox_connect(client, fake_dropbox_client)

    _override(fake_dropbox_client, FakeTokenRevoker(raise_on_revoke=True))
    try:
        response = await client.post("/api/v1/storage-config/dropbox/disconnect")
    finally:
        _clear_overrides()

    assert response.status_code == 200
    assert response.json()["is_connected"] is False

    config = (
        await db_session.scalars(select(StorageConfig).where(StorageConfig.user_id == user_id))
    ).one()
    assert config.oauth_access_token is None
    assert config.oauth_refresh_token is None


async def test_disconnect_requires_authentication(client: AsyncClient) -> None:
    response = await client.post("/api/v1/storage-config/dropbox/disconnect")
    assert response.status_code == 401
