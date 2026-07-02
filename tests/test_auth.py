import re
import uuid

from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.notifications.email import FakeEmailSender


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


def extract_reset_token(html: str) -> str:
    match = re.search(r"reset-password\?token=([^\"&\s]+)", html)
    assert match is not None, f"no reset token found in email html: {html!r}"
    return match.group(1)


async def test_forgot_password_with_known_email_emails_a_reset_link(
    client: AsyncClient, fake_email_sender: FakeEmailSender
) -> None:
    email = unique_email()
    await client.post(
        "/api/v1/auth/register", data={"email": email, "password": "correct-horse-battery"}
    )

    response = await client.post("/api/v1/auth/forgot-password", data={"email": email})

    assert response.status_code == 200
    assert len(fake_email_sender.sent) == 1
    message = fake_email_sender.sent[0]
    assert message["to"] == email
    assert "reset-password?token=" in message["html"]


async def test_forgot_password_with_unknown_email_returns_same_response_shape(
    client: AsyncClient, fake_email_sender: FakeEmailSender
) -> None:
    known_email = unique_email()
    await client.post(
        "/api/v1/auth/register", data={"email": known_email, "password": "correct-horse-battery"}
    )
    known_response = await client.post(
        "/api/v1/auth/forgot-password", data={"email": known_email}
    )
    fake_email_sender.sent.clear()

    unknown_response = await client.post(
        "/api/v1/auth/forgot-password", data={"email": unique_email()}
    )

    assert unknown_response.status_code == known_response.status_code
    assert unknown_response.json() == known_response.json()
    assert fake_email_sender.sent == []


async def test_reset_password_with_valid_token_updates_password_and_token_is_single_use(
    client: AsyncClient, fake_email_sender: FakeEmailSender
) -> None:
    email = unique_email()
    old_password = "correct-horse-battery"
    new_password = "new-correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": old_password})
    await client.post("/api/v1/auth/forgot-password", data={"email": email})
    token = extract_reset_token(fake_email_sender.sent[0]["html"])

    reset_response = await client.post(
        "/api/v1/auth/reset-password",
        data={"token": token, "password": new_password, "confirm_password": new_password},
    )
    assert reset_response.status_code == 200

    old_password_login = await client.post(
        "/api/v1/auth/login", data={"email": email, "password": old_password}
    )
    assert old_password_login.status_code == 401

    new_password_login = await client.post(
        "/api/v1/auth/login", data={"email": email, "password": new_password}
    )
    assert new_password_login.status_code in (200, 204)

    reused_token_response = await client.post(
        "/api/v1/auth/reset-password",
        data={
            "token": token,
            "password": "another-password-123",
            "confirm_password": "another-password-123",
        },
    )
    assert reused_token_response.status_code == 400


async def test_reset_password_with_invalid_token_returns_400(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/reset-password",
        data={
            "token": "not-a-real-token",
            "password": "correct-horse-battery",
            "confirm_password": "correct-horse-battery",
        },
    )

    assert response.status_code == 400


async def test_reset_password_with_mismatched_confirmation_returns_400(
    client: AsyncClient, fake_email_sender: FakeEmailSender
) -> None:
    email = unique_email()
    await client.post(
        "/api/v1/auth/register", data={"email": email, "password": "correct-horse-battery"}
    )
    await client.post("/api/v1/auth/forgot-password", data={"email": email})
    token = extract_reset_token(fake_email_sender.sent[0]["html"])

    response = await client.post(
        "/api/v1/auth/reset-password",
        data={"token": token, "password": "new-password-123", "confirm_password": "typo-password-123"},
    )

    assert response.status_code == 400


async def test_reset_password_below_minimum_length_returns_400(
    client: AsyncClient, fake_email_sender: FakeEmailSender
) -> None:
    email = unique_email()
    await client.post(
        "/api/v1/auth/register", data={"email": email, "password": "correct-horse-battery"}
    )
    await client.post("/api/v1/auth/forgot-password", data={"email": email})
    token = extract_reset_token(fake_email_sender.sent[0]["html"])

    response = await client.post(
        "/api/v1/auth/reset-password",
        data={"token": token, "password": "short", "confirm_password": "short"},
    )

    assert response.status_code == 400


async def test_reset_password_with_deleted_user_returns_400(
    client: AsyncClient, db_session: AsyncSession, fake_email_sender: FakeEmailSender
) -> None:
    email = unique_email()
    await client.post(
        "/api/v1/auth/register", data={"email": email, "password": "correct-horse-battery"}
    )
    await client.post("/api/v1/auth/forgot-password", data={"email": email})
    token = extract_reset_token(fake_email_sender.sent[0]["html"])

    await db_session.execute(delete(User).where(User.email == email))  # type: ignore[arg-type]
    await db_session.flush()

    response = await client.post(
        "/api/v1/auth/reset-password",
        data={
            "token": token,
            "password": "new-password-123",
            "confirm_password": "new-password-123",
        },
    )

    assert response.status_code == 400


async def test_forgot_password_survives_email_delivery_failure(client: AsyncClient) -> None:
    class FailingEmailSender:
        async def send(self, *, to: str, subject: str, html: str) -> None:
            raise RuntimeError("Resend is down")

    from app.auth.users import get_email_sender
    from app.main import app

    email = unique_email()
    await client.post(
        "/api/v1/auth/register", data={"email": email, "password": "correct-horse-battery"}
    )
    app.dependency_overrides[get_email_sender] = FailingEmailSender

    response = await client.post("/api/v1/auth/forgot-password", data={"email": email})

    assert response.status_code == 200
    assert response.json() == {
        "detail": "If that email address is registered, a password reset link has been sent."
    }


async def test_forgot_password_email_lookup_is_case_insensitive(
    client: AsyncClient, fake_email_sender: FakeEmailSender
) -> None:
    email = unique_email()
    await client.post(
        "/api/v1/auth/register", data={"email": email, "password": "correct-horse-battery"}
    )

    response = await client.post("/api/v1/auth/forgot-password", data={"email": email.upper()})

    assert response.status_code == 200
    assert len(fake_email_sender.sent) == 1
    assert fake_email_sender.sent[0]["to"] == email


async def test_forgot_password_page_renders_daisyui_form_with_expected_fields(
    client: AsyncClient,
) -> None:
    response = await client.get("/forgot-password")

    assert response.status_code == 200
    body = response.text
    assert 'name="email"' in body
    assert 'type="email"' in body
    assert 'action="/api/v1/auth/forgot-password"' in body
    assert "input-bordered" in body


async def test_reset_password_page_renders_daisyui_form_with_expected_fields(
    client: AsyncClient,
) -> None:
    response = await client.get("/reset-password?token=some-token-value")

    assert response.status_code == 200
    body = response.text
    assert 'name="token"' in body
    assert 'value="some-token-value"' in body
    assert 'name="password"' in body
    assert 'type="password"' in body
    assert 'name="confirm_password"' in body
    assert 'action="/api/v1/auth/reset-password"' in body
    assert "input-bordered" in body
