"""Tests for the test-only E2E helper endpoints (app.api.v1.internal_e2e, issue #23).

The route that mints a password-reset token is gated behind E2E_TEST_MODE; these tests cover
both the gated-off (404, existence hidden) and gated-on (valid token that completes a real
reset) paths. Enabling the flag is done by overriding the get_settings dependency rather than
mutating process env, so it stays scoped to a single test.
"""

import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from app.main import app

_WORKFLOWS_DIR = Path(__file__).resolve().parents[1] / ".github" / "workflows"


def unique_email() -> str:
    return f"e2e-internal-test-{uuid.uuid4().hex}@example.com"


@pytest.fixture
def e2e_mode_enabled() -> Iterator[None]:
    """Turn E2E_TEST_MODE on for the duration of a test by overriding get_settings with a
    copy of the real settings that has the flag flipped, then restore on teardown."""
    enabled = get_settings().model_copy(update={"e2e_test_mode": True})
    app.dependency_overrides[get_settings] = lambda: enabled
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_settings, None)


async def test_last_reset_token_returns_404_when_e2e_mode_disabled(client: AsyncClient) -> None:
    # Default (flag off): the endpoint must be indistinguishable from a route that doesn't
    # exist, so its presence can't be detected in prod.
    email = unique_email()
    await client.post(
        "/api/v1/auth/register", data={"email": email, "password": "correct-horse-battery"}
    )

    response = await client.get("/api/v1/internal/e2e/last-reset-token", params={"email": email})

    assert response.status_code == 404


async def test_last_reset_token_hidden_from_openapi_schema(client: AsyncClient) -> None:
    schema = (await client.get("/openapi.json")).json()
    assert not any("/internal/e2e/" in path for path in schema["paths"])


@pytest.mark.usefixtures("e2e_mode_enabled")
async def test_last_reset_token_mints_token_that_completes_reset_flow(client: AsyncClient) -> None:
    email = unique_email()
    old_password = "correct-horse-battery"
    new_password = "brand-new-password-123"
    await client.post("/api/v1/auth/register", data={"email": email, "password": old_password})

    token_response = await client.get(
        "/api/v1/internal/e2e/last-reset-token", params={"email": email}
    )
    assert token_response.status_code == 200
    token = token_response.json()["token"]
    assert token

    reset_response = await client.post(
        "/api/v1/auth/reset-password",
        data={"token": token, "password": new_password, "confirm_password": new_password},
    )
    assert reset_response.status_code == 200

    old_login = await client.post(
        "/api/v1/auth/login", data={"email": email, "password": old_password}
    )
    assert old_login.status_code == 401
    new_login = await client.post(
        "/api/v1/auth/login", data={"email": email, "password": new_password}
    )
    assert new_login.status_code in (200, 204)


@pytest.mark.usefixtures("e2e_mode_enabled")
async def test_last_reset_token_returns_404_for_unknown_email(client: AsyncClient) -> None:
    # Even with the flag on, an unregistered email must not be confirmable via this endpoint.
    response = await client.get(
        "/api/v1/internal/e2e/last-reset-token", params={"email": unique_email()}
    )

    assert response.status_code == 404


def test_e2e_test_mode_is_never_enabled_in_the_prod_deploy_workflow() -> None:
    # The test-only reset-token endpoint must be unreachable in prod. The QA deploy (ci.yml)
    # sets E2E_TEST_MODE=true on purpose; the prod deploy (deploy.yml) must never do so, or a
    # future edit could silently expose it. Guard both directions here.
    ci_yaml = (_WORKFLOWS_DIR / "ci.yml").read_text(encoding="utf-8")
    deploy_yaml = (_WORKFLOWS_DIR / "deploy.yml").read_text(encoding="utf-8")

    assert "E2E_TEST_MODE" in ci_yaml, "QA (ci.yml) is expected to enable E2E_TEST_MODE"
    assert "E2E_TEST_MODE" not in deploy_yaml, (
        "E2E_TEST_MODE must never appear in the prod deploy workflow (deploy.yml)"
    )
