"""Regression tests for the shared card/card-body page shell.

These tests pin the rendered structure produced by the card_page (profile) and card_shell
(auth pages, design-refresh) Jinja macros so that any future refactor of the macro or the
templates that use it is caught immediately rather than only in E2E.
"""
import uuid

import pytest
from httpx import AsyncClient


def unique_email() -> str:
    return f"card-macro-{uuid.uuid4().hex}@example.com"


# ---------------------------------------------------------------------------
# Unauthenticated auth pages (design-refresh Slice 3: rebuilt on card_shell, no card_page/DaisyUI)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path,expected_title",
    [
        ("/login", "Log in"),
        ("/register", "Create your account"),
        ("/forgot-password", "Forgot your password?"),
    ],
)
async def test_auth_page_has_card_shell_wrapper(
    client: AsyncClient, path: str, expected_title: str
) -> None:
    response = await client.get(path)

    assert response.status_code == 200
    body = response.text
    assert "card_page" not in body
    assert "card-body" not in body
    assert f">{expected_title}</h1>" in body


async def test_reset_password_page_has_card_shell_wrapper(client: AsyncClient) -> None:
    response = await client.get("/reset-password?token=dummy")

    assert response.status_code == 200
    body = response.text
    assert "card_page" not in body
    assert "card-body" not in body
    assert ">Reset your password</h1>" in body


async def test_auth_pages_card_title_is_h1(client: AsyncClient) -> None:
    """The card title must be an h1 for accessibility/semantics."""
    for path, title in [("/login", "Log in"), ("/register", "Create your account")]:
        response = await client.get(path)
        body = response.text
        assert f">{title}</h1>" in body


async def test_auth_pages_have_no_daisyui_classes(client: AsyncClient) -> None:
    daisyui_tokens = ["card-body", "card-title", "btn-primary", "input-bordered", "alert-error", "alert-info"]
    for path in ["/login", "/register", "/forgot-password"]:
        response = await client.get(path)
        body = response.text
        for token in daisyui_tokens:
            assert token not in body, f"{path} still contains DaisyUI class {token!r}"

    reset_response = await client.get("/reset-password?token=dummy")
    for token in daisyui_tokens:
        assert token not in reset_response.text, f"/reset-password still contains DaisyUI class {token!r}"


async def test_auth_pages_use_marketing_density_card_padding(client: AsyncClient) -> None:
    """Auth pages use the marketing/first-impression density variant, not product's tighter one."""
    for path in ["/login", "/register", "/forgot-password"]:
        response = await client.get(path)
        assert "p-6" in response.text  # DENSITY_CARD_PADDING["marketing"]


# ---------------------------------------------------------------------------
# Profile page (requires authentication)
# ---------------------------------------------------------------------------


async def test_profile_page_has_card_wrapper(client: AsyncClient) -> None:
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})

    response = await client.get("/profile")

    assert response.status_code == 200
    body = response.text
    assert "card-body" in body
    assert ">Your profile</h1>" in body


async def test_profile_page_card_has_wide_max_width(client: AsyncClient) -> None:
    """Profile card uses max-w-lg (wider than the auth pages' max-w-sm)."""
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})

    response = await client.get("/profile")

    assert response.status_code == 200
    assert "max-w-lg" in response.text


async def test_login_page_card_uses_standard_max_width(client: AsyncClient) -> None:
    """Auth card pages use max-w-sm by default."""
    response = await client.get("/login")

    assert response.status_code == 200
    assert "max-w-sm" in response.text
