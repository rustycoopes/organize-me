import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.oauth_account import OAuthAccount
from app.models.user import User


def unique_email() -> str:
    return f"users-test-{uuid.uuid4().hex}@example.com"


async def test_get_current_user_returns_profile_fields(client: AsyncClient) -> None:
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})

    response = await client.get("/api/v1/users/me")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] is None
    assert body["phone_number"] is None
    assert body["dark_mode"] is False
    assert body["notification_email"] is True
    assert body["notification_sms"] is True


async def test_patch_updates_name_email_phone_and_persists(client: AsyncClient) -> None:
    email = unique_email()
    password = "correct-horse-battery"
    new_email = unique_email()
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})

    response = await client.patch(
        "/api/v1/users/me",
        json={"name": "Ada Lovelace", "email": new_email, "phone_number": "+15551234567"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Ada Lovelace"
    assert body["email"] == new_email
    assert body["phone_number"] == "+15551234567"

    follow_up = await client.get("/api/v1/users/me")
    follow_up_body = follow_up.json()
    assert follow_up_body["name"] == "Ada Lovelace"
    assert follow_up_body["email"] == new_email
    assert follow_up_body["phone_number"] == "+15551234567"


async def test_patch_dark_mode_persists(client: AsyncClient) -> None:
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})

    response = await client.patch("/api/v1/users/me", json={"dark_mode": True})

    assert response.status_code == 200
    assert response.json()["dark_mode"] is True

    follow_up = await client.get("/api/v1/users/me")
    assert follow_up.json()["dark_mode"] is True


async def test_patch_partial_update_leaves_other_fields_unchanged(client: AsyncClient) -> None:
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})

    response = await client.patch("/api/v1/users/me", json={"name": "New Name"})

    assert response.status_code == 200
    assert response.json()["name"] == "New Name"
    assert response.json()["email"] == email


async def test_patch_with_duplicate_email_returns_4xx(client: AsyncClient) -> None:
    email_a = unique_email()
    email_b = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email_a, "password": password})
    await client.post("/api/v1/auth/register", data={"email": email_b, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email_a, "password": password})

    response = await client.patch("/api/v1/users/me", json={"email": email_b})

    assert 400 <= response.status_code < 500


async def test_patch_with_explicit_null_email_returns_422(client: AsyncClient) -> None:
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})

    response = await client.patch("/api/v1/users/me", json={"email": None})

    assert response.status_code == 422


async def test_patch_with_explicit_null_dark_mode_returns_422(client: AsyncClient) -> None:
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})

    response = await client.patch("/api/v1/users/me", json={"dark_mode": None})

    assert response.status_code == 422


async def test_patch_notification_toggles_persist(client: AsyncClient) -> None:
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})

    response = await client.patch(
        "/api/v1/users/me", json={"notification_email": False, "notification_sms": False}
    )

    assert response.status_code == 200
    assert response.json()["notification_email"] is False
    assert response.json()["notification_sms"] is False

    follow_up = await client.get("/api/v1/users/me")
    assert follow_up.json()["notification_email"] is False
    assert follow_up.json()["notification_sms"] is False


async def test_patch_with_explicit_null_notification_fields_returns_422(
    client: AsyncClient,
) -> None:
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})

    response = await client.patch("/api/v1/users/me", json={"notification_email": None})

    assert response.status_code == 422

    sms_response = await client.patch("/api/v1/users/me", json={"notification_sms": None})

    assert sms_response.status_code == 422


async def test_patch_notification_field_sets_onboarding_flag_on_first_save(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})

    response = await client.patch("/api/v1/users/me", json={"notification_sms": False})

    assert response.status_code == 200
    result = await db_session.execute(select(User).where(User.email == email))  # type: ignore[arg-type]
    user = result.unique().scalar_one()
    assert user.onboarding_notifications_done is True


async def test_patch_unrelated_field_does_not_set_onboarding_flag(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})

    response = await client.patch("/api/v1/users/me", json={"name": "New Name"})

    assert response.status_code == 200
    result = await db_session.execute(select(User).where(User.email == email))  # type: ignore[arg-type]
    user = result.unique().scalar_one()
    assert user.onboarding_notifications_done is False


async def test_patch_notification_field_on_second_save_keeps_flag_and_updates_toggle(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})

    await client.patch("/api/v1/users/me", json={"notification_sms": False})
    response = await client.patch(
        "/api/v1/users/me",
        json={"phone_number": "+15551234567", "notification_sms": True},
    )

    assert response.status_code == 200
    assert response.json()["notification_sms"] is True
    result = await db_session.execute(select(User).where(User.email == email))  # type: ignore[arg-type]
    user = result.unique().scalar_one()
    assert user.onboarding_notifications_done is True
    assert user.notification_sms is True


async def test_patch_allows_enabling_sms_without_a_phone_number(client: AsyncClient) -> None:
    # No server-side guard here by design (#87): RealNotificationSender silently skips the SMS
    # send when the toggle is on but no phone number is on file, rather than treating it as an
    # error - so the PATCH endpoint doesn't reject this combination either.
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})

    response = await client.patch("/api/v1/users/me", json={"notification_sms": True})

    assert response.status_code == 200
    assert response.json()["notification_sms"] is True


async def test_patch_with_case_different_duplicate_email_returns_4xx(
    client: AsyncClient,
) -> None:
    email_a = unique_email()
    email_b = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email_a, "password": password})
    await client.post("/api/v1/auth/register", data={"email": email_b, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email_a, "password": password})

    response = await client.patch("/api/v1/users/me", json={"email": email_b.upper()})

    assert 400 <= response.status_code < 500


async def test_patch_email_change_resets_is_verified(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    email = unique_email()
    new_email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})

    response = await client.patch("/api/v1/users/me", json={"email": new_email})

    assert response.status_code == 200
    result = await db_session.execute(select(User).where(User.email == new_email))  # type: ignore[arg-type]
    user = result.unique().scalar_one()
    assert user.is_verified is False


async def test_patch_rejects_missing_cookie(client: AsyncClient) -> None:
    response = await client.patch("/api/v1/users/me", json={"name": "New Name"})

    assert response.status_code == 401


async def test_patch_ignores_privileged_fields(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})

    response = await client.patch(
        "/api/v1/users/me",
        json={"is_superuser": True, "password": "should-not-apply", "name": "x"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "x"

    result = await db_session.execute(select(User).where(User.email == email))  # type: ignore[arg-type]
    user = result.unique().scalar_one()
    assert user.is_superuser is False

    original_password_login = await client.post(
        "/api/v1/auth/login", data={"email": email, "password": password}
    )
    assert original_password_login.status_code == 302  # success redirect to /profile (issue #43)


async def test_delete_removes_user_and_invalidates_cookie(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})

    response = await client.delete("/api/v1/users/me")

    assert response.status_code in (200, 204)

    follow_up = await client.get("/api/v1/users/me")
    assert follow_up.status_code == 401

    result = await db_session.execute(select(User).where(User.email == email))  # type: ignore[arg-type]
    assert result.unique().scalars().all() == []


async def test_delete_removes_linked_oauth_account(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})

    me_response = await client.get("/api/v1/users/me")
    user_id = uuid.UUID(me_response.json()["id"])

    db_session.add(
        OAuthAccount(
            user_id=user_id,
            oauth_name="google",
            access_token="fake-access-token",
            account_id="google-account-123",
            account_email=email,
        )
    )
    await db_session.flush()

    response = await client.delete("/api/v1/users/me")
    assert response.status_code in (200, 204)

    result = await db_session.execute(
        select(OAuthAccount).where(OAuthAccount.user_id == user_id)  # type: ignore[arg-type]
    )
    assert result.unique().scalars().all() == []


async def test_delete_rejects_missing_cookie(client: AsyncClient) -> None:
    response = await client.delete("/api/v1/users/me")

    assert response.status_code == 401
