"""Tests for the event_creator.user_settings model, migration, and lazy get-or-create (#158).

These exercise the real table on the QA database (created by the Alembic migration that CI runs
before pytest), inside the rolled-back db_session fixture - so nothing persists.
"""

import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.user_settings import UserSettings
from app.services.user_settings import get_or_create_user_settings, get_user_settings


async def _make_user(session: AsyncSession) -> User:
    user = User(
        email=f"user-settings-{uuid.uuid4().hex}@example.com", hashed_password="not-a-real-hash"
    )
    session.add(user)
    await session.flush()
    return user


async def test_user_settings_lives_in_event_creator_schema(db_session: AsyncSession) -> None:
    result = await db_session.execute(
        text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'event_creator' AND table_name = 'user_settings'"
        )
    )
    assert result.first() is not None


async def test_host_users_no_longer_has_moved_columns(db_session: AsyncSession) -> None:
    result = await db_session.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'host' AND table_name = 'users'"
        )
    )
    columns = {row[0] for row in result.all()}
    assert columns.isdisjoint(
        {
            "notification_sms",
            "notification_email",
            "onboarding_storage_done",
            "onboarding_notifications_done",
            "onboarding_first_upload_done",
        }
    )


async def test_user_settings_persists_with_defaults_and_round_trips(
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session)
    settings = UserSettings(user_id=user.id)
    db_session.add(settings)
    await db_session.flush()

    await db_session.refresh(settings)
    stored = await db_session.scalar(select(UserSettings).where(UserSettings.user_id == user.id))
    assert stored is not None
    assert stored.notification_email is True
    assert stored.notification_sms is True
    assert stored.onboarding_storage_done is False
    assert stored.onboarding_notifications_done is False
    assert stored.onboarding_first_upload_done is False
    assert stored.created_at is not None
    assert stored.updated_at is not None


async def test_user_settings_is_unique_per_user(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    db_session.add(UserSettings(user_id=user.id))
    await db_session.flush()

    db_session.add(UserSettings(user_id=user.id))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_deleting_user_cascades_to_settings_row(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    settings = UserSettings(user_id=user.id)
    db_session.add(settings)
    await db_session.flush()

    await db_session.delete(user)
    await db_session.flush()

    result = await db_session.execute(
        text("SELECT 1 FROM event_creator.user_settings WHERE user_id = :uid").bindparams(
            uid=user.id
        )
    )
    assert result.first() is None


async def test_get_user_settings_returns_none_when_no_row_exists(
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session)
    assert await get_user_settings(db_session, user.id) is None


async def test_get_or_create_user_settings_creates_row_with_defaults_on_first_call(
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session)

    settings = await get_or_create_user_settings(db_session, user.id)

    assert settings.user_id == user.id
    assert settings.notification_email is True
    assert settings.notification_sms is True
    assert settings.onboarding_storage_done is False
    stored = await get_user_settings(db_session, user.id)
    assert stored is not None
    assert stored.id == settings.id


async def test_get_or_create_user_settings_returns_existing_row_on_second_call(
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session)
    first = await get_or_create_user_settings(db_session, user.id)
    first.notification_sms = False
    await db_session.commit()

    second = await get_or_create_user_settings(db_session, user.id)

    assert second.id == first.id
    assert second.notification_sms is False
