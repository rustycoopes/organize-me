import re
import uuid
from html.parser import HTMLParser

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


async def test_register_with_malformed_email_returns_pydantic_validation_array_shape(
    client: AsyncClient,
) -> None:
    # The register page's JS reads detail[0].msg from FastAPI's own 422 validation-error
    # shape to show a specific message - see issue #26.
    response = await client.post(
        "/api/v1/auth/register", data={"email": "not-an-email", "password": "correct-horse-battery"}
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail, list)
    assert "msg" in detail[0]


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

    # 302 to /profile (issue #43) rather than a bare 204 - the endpoint navigates the browser
    # itself instead of relying on client-side JS - and still sets the auth cookie.
    assert response.status_code == 302
    set_cookie_headers = response.headers.get_list("set-cookie")
    assert len(set_cookie_headers) == 1
    assert "httponly" in set_cookie_headers[0].lower()


async def test_login_with_correct_credentials_redirects_to_profile(client: AsyncClient) -> None:
    # Regression guard for issue #43: a successful login must 302-redirect to /profile so a
    # plain full-page form POST (JS disabled / non-fetch caller) lands on a page instead of a
    # bare 204 No Content. Mirrors the Google-callback fix (#27).
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})

    response = await client.post("/api/v1/auth/login", data={"email": email, "password": password})

    assert response.status_code == 302
    assert response.headers["location"] == "/profile"
    # The redirect must itself carry the auth cookie, otherwise the browser follows it to
    # /profile with no session and gets bounced back to /login.
    assert response.headers.get_list("set-cookie"), "302 redirect did not set the auth cookie"


async def test_login_redirect_lands_on_an_authenticated_session(client: AsyncClient) -> None:
    # Following the login redirect must reach a protected resource - proves the cookie carried
    # on the 302 actually authenticates the session end-to-end (issue #43).
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})

    await client.post("/api/v1/auth/login", data={"email": email, "password": password})

    me = await client.get("/api/v1/users/me")
    assert me.status_code == 200
    assert me.json()["email"] == email


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


async def test_register_page_renders_form_with_expected_fields(client: AsyncClient) -> None:
    response = await client.get("/register")

    assert response.status_code == 200
    body = response.text
    assert 'name="email"' in body
    assert 'type="email"' in body
    assert 'name="password"' in body
    assert 'type="password"' in body
    assert 'action="/api/v1/auth/register"' in body
    assert "input-bordered" not in body  # design-refresh Slice 3: DaisyUI class retired
    assert "rounded-md border" in body  # shared input component's field class


async def test_login_page_renders_form_with_expected_fields(client: AsyncClient) -> None:
    response = await client.get("/login")

    assert response.status_code == 200
    body = response.text
    assert 'name="email"' in body
    assert 'type="email"' in body
    assert 'name="password"' in body
    assert 'type="password"' in body
    assert 'action="/api/v1/auth/login"' in body
    assert "input-bordered" not in body
    assert "rounded-md border" in body


async def test_register_page_submits_via_js_and_auto_logs_in(client: AsyncClient) -> None:
    response = await client.get("/register")

    body = response.text
    assert '@submit.prevent="register"' in body
    # After a successful POST /register, the page's own JS must call /login with the same
    # credentials (auto-login) rather than leaving the browser on the raw register JSON
    # response - see issue #26.
    assert "fetch('/api/v1/auth/register'" in body
    assert "fetch('/api/v1/auth/login'" in body
    assert "window.location.href = '/profile'" in body
    assert 'x-show="error"' in body
    # If auto-login unexpectedly fails after a successful registration, the user should land
    # on /login with an explanation rather than silently.
    assert "window.location.href = '/login?registered=1'" in body


class _XDataCollector(HTMLParser):
    """Collects every `x-data` attribute value the HTML parser sees. Because the parser honours
    HTML attribute-quote termination, a stray double-quote inside a double-quoted x-data value
    truncates the collected value exactly as a real browser would - which is how we catch it."""

    def __init__(self) -> None:
        super().__init__()
        self.x_data_values: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name == "x-data" and value is not None:
                self.x_data_values.append(value)


async def test_register_page_x_data_attribute_is_not_truncated_by_a_stray_quote(
    client: AsyncClient,
) -> None:
    # Regression guard for the Alpine x-data attribute being cut short by an embedded double
    # quote (a JS comment containing `type="email"` inside the double-quoted x-data broke the
    # whole register form - caught by the #23 Playwright suite, since pytest string-matching
    # never executes the JS). Parse the page as a browser would and assert the register
    # component's expression still contains code that lives AFTER the historical break point.
    response = await client.get("/register")
    collector = _XDataCollector()
    collector.feed(response.text)

    register_x_data = [v for v in collector.x_data_values if "register(event)" in v]
    assert register_x_data, "register page has no x-data component with a register() method"
    # This assignment sits well past the comment that used to truncate the attribute; if the
    # value were cut short at a stray quote, it wouldn't survive HTML attribute parsing.
    assert "window.location.href = '/profile'" in register_x_data[0]


async def test_register_page_shows_google_auth_failed_via_alpine_init(client: AsyncClient) -> None:
    response = await client.get("/register")

    body = response.text
    # The google_auth_failed banner is driven by Alpine's init() reading the query string
    # client-side, not a server-rendered Jinja conditional - see issue #26.
    assert "init()" in body
    assert "google_auth_failed" in body
    assert "{% if request.query_params.get" not in body


async def test_login_page_submits_via_js_and_redirects_to_profile(client: AsyncClient) -> None:
    response = await client.get("/login")

    body = response.text
    assert '@submit.prevent="login"' in body
    assert "fetch('/api/v1/auth/login'" in body
    assert "window.location.href = '/profile'" in body
    assert 'x-show="error"' in body


async def test_login_page_shows_registered_info_banner_via_alpine_init(client: AsyncClient) -> None:
    response = await client.get("/login")

    body = response.text
    assert "init()" in body
    assert "google_auth_failed" in body
    assert "registered" in body
    assert 'x-show="info"' in body
    assert "{% if request.query_params.get" not in body


async def test_register_page_trims_email_before_submit_and_alerts_are_accessible(
    client: AsyncClient,
) -> None:
    response = await client.get("/register")

    body = response.text
    # A pasted/trailing-space email shouldn't produce a confusing 422 - see issue #26.
    assert "email.trim()" in body
    assert 'aria-live="polite"' in body


async def test_login_page_trims_email_before_submit_and_alerts_are_accessible(
    client: AsyncClient,
) -> None:
    response = await client.get("/login")

    body = response.text
    assert "email.trim()" in body
    assert 'aria-live="polite"' in body


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
    assert new_password_login.status_code == 302  # success redirect to /profile (issue #43)

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


async def test_forgot_password_page_renders_form_with_expected_fields(
    client: AsyncClient,
) -> None:
    response = await client.get("/forgot-password")

    assert response.status_code == 200
    body = response.text
    assert 'name="email"' in body
    assert 'type="email"' in body
    assert 'action="/api/v1/auth/forgot-password"' in body
    assert "input-bordered" not in body  # design-refresh Slice 3: DaisyUI class retired
    assert "rounded-md border" in body  # shared input component's field class


async def test_reset_password_page_renders_form_with_expected_fields(
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
    assert "input-bordered" not in body
    assert "rounded-md border" in body
