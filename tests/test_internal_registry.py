"""Tests for GET /internal/app-registry.json (registry-decoupling, organize-me#218). Covers the
OIDC read-token gate (`_verify_registry_read_token`) and the response shape - mirrors
event-creator's tests/test_internal_pipeline_api.py for the equivalent `_verify_push_token` gate.
"""

from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient, Response

import app.api.internal.registry as internal_registry_module
from app.core.config import get_settings
from app.core.registry import APPS


@pytest.fixture(autouse=True)
def _configure_oidc_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    # This module's tests never touch the DB or any of the OAuth/email settings - route through
    # placeholder values (mirrors event-creator's tests/conftest.py::_env for the same reason) so
    # Settings() construction succeeds without a real Postgres/Google/Resend credential.
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/testdb")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("GOOGLE_OAUTH_REDIRECT_URI", "http://localhost/api/v1/auth/google/callback")
    monkeypatch.setenv("REGISTRY_ENDPOINT_URL", "https://organize-me-test.a.run.app")
    monkeypatch.setenv(
        "REGISTRY_INVOKER_SERVICE_ACCOUNT", "invoker@test-project.iam.gserviceaccount.com"
    )
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """A DB-free httpx client for this module's tests - GET /internal/app-registry.json never
    touches the DB, so this deliberately doesn't use conftest.py's `client` fixture (which
    requires a real, reachable Postgres via its db_session dependency)."""
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


def _accept_valid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        internal_registry_module.id_token,
        "verify_oauth2_token",
        lambda *a, **kw: {"email": "invoker@test-project.iam.gserviceaccount.com"},
    )


async def _get(client: AsyncClient, *, token: str | None) -> Response:
    headers = {"authorization": f"Bearer {token}"} if token is not None else {}
    return await client.get("/internal/app-registry.json", headers=headers)


async def test_rejects_missing_token(client: AsyncClient) -> None:
    response = await _get(client, token=None)
    assert response.status_code == 401
    assert response.json()["detail"] == "missing_token"


async def test_rejects_token_that_fails_verification(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _raise(*args: object, **kwargs: object) -> None:
        raise ValueError("bad token")

    monkeypatch.setattr(internal_registry_module.id_token, "verify_oauth2_token", _raise)

    response = await _get(client, token="not-a-real-token")
    assert response.status_code == 401
    assert response.json()["detail"] == "invalid_token"


async def test_rejects_token_for_the_wrong_service_account(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        internal_registry_module.id_token,
        "verify_oauth2_token",
        lambda *a, **kw: {"email": "someone-else@evil.example.com"},
    )

    response = await _get(client, token="valid-signature-wrong-identity")
    assert response.status_code == 403
    assert response.json()["detail"] == "wrong_identity"


async def test_returns_503_when_settings_unconfigured(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("REGISTRY_ENDPOINT_URL", "")
    monkeypatch.setenv("REGISTRY_INVOKER_SERVICE_ACCOUNT", "")
    get_settings.cache_clear()

    response = await _get(client, token="anything")
    assert response.status_code == 503
    assert response.json()["detail"] == "not_configured"


async def test_local_dev_bypass_short_circuits_when_oidc_settings_unset(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("REGISTRY_ENDPOINT_URL", "")
    monkeypatch.setenv("REGISTRY_INVOKER_SERVICE_ACCOUNT", "")
    monkeypatch.setenv("REGISTRY_LOCAL_DEV_BYPASS", "true")
    get_settings.cache_clear()

    response = await _get(client, token=None)

    assert response.status_code == 200
    body = response.json()
    assert [entry["service_name"] for entry in body] == [app.service_name for app in APPS]


async def test_local_dev_bypass_is_inert_when_oidc_settings_are_populated(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # _configure_oidc_settings already populates REGISTRY_ENDPOINT_URL/
    # REGISTRY_INVOKER_SERVICE_ACCOUNT - turning the bypass on here must not change the outcome:
    # the real OIDC check still runs and still rejects a missing token.
    monkeypatch.setenv("REGISTRY_LOCAL_DEV_BYPASS", "true")
    get_settings.cache_clear()

    response = await _get(client, token=None)

    assert response.status_code == 401
    assert response.json()["detail"] == "missing_token"


async def test_local_dev_bypass_does_not_affect_a_valid_token_when_oidc_settings_are_populated(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Proves inertness end-to-end, not just that a missing token is still rejected: with the
    # bypass on but real OIDC settings populated, a genuinely valid token must still succeed via
    # the real check, exactly as if the bypass were off.
    monkeypatch.setenv("REGISTRY_LOCAL_DEV_BYPASS", "true")
    get_settings.cache_clear()
    _accept_valid_token(monkeypatch)

    response = await _get(client, token="valid-token")

    assert response.status_code == 200
    body = response.json()
    assert [entry["service_name"] for entry in body] == [app.service_name for app in APPS]


@pytest.mark.parametrize(
    "unset_env_var", ["REGISTRY_ENDPOINT_URL", "REGISTRY_INVOKER_SERVICE_ACCOUNT"]
)
async def test_local_dev_bypass_is_inert_when_only_one_oidc_setting_is_populated(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, unset_env_var: str
) -> None:
    # A half-migrated deployment (one real setting populated, the other still empty) must fail
    # closed exactly as it would with the bypass off - the bypass only ever fires while *both*
    # settings are still at their pristine empty default, never for just one of the two.
    monkeypatch.setenv(unset_env_var, "")
    monkeypatch.setenv("REGISTRY_LOCAL_DEV_BYPASS", "true")
    get_settings.cache_clear()

    response = await _get(client, token="anything")

    assert response.status_code == 503
    assert response.json()["detail"] == "not_configured"


async def test_valid_token_returns_the_current_registry(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _accept_valid_token(monkeypatch)

    response = await _get(client, token="valid-token")

    assert response.status_code == 200
    body = response.json()
    assert [entry["service_name"] for entry in body] == [app.service_name for app in APPS]


async def test_response_round_trips_through_the_client_side_dataclasses(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Exercises the real consuming-side parse path (organizeme_chrome.registry_client), not just
    # this endpoint's own JSON shape - confirms the wire format matches what a real consumer
    # (event-creator, doc-library) actually decodes.
    from organizeme_chrome.registry_client import fetch_registry_once

    _accept_valid_token(monkeypatch)

    async def _fake_token_provider() -> str:
        return "valid-token"

    apps = await fetch_registry_once(client, "http://testserver", _fake_token_provider)

    assert apps == APPS
