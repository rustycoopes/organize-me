"""Tests for the storage_configs model + migration (issue #45).

These exercise the real table on the QA database (created by the Alembic migration that CI runs
before pytest), inside the rolled-back db_session fixture - so nothing persists.
"""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.storage_config import StorageConfig, StorageProviderType
from app.models.user import User


async def _make_user(session: AsyncSession) -> User:
    user = User(email=f"storage-{uuid.uuid4().hex}@example.com", hashed_password="not-a-real-hash")
    session.add(user)
    await session.flush()
    return user


async def test_storage_config_persists_and_provider_enum_round_trips(
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session)
    config = StorageConfig(
        user_id=user.id,
        provider=StorageProviderType.GOOGLE_DRIVE,
        folder_path="/OrganizeMe/exports",
    )
    db_session.add(config)
    await db_session.flush()

    # The raw stored enum label must be the value ("google_drive"), not SQLAlchemy's default
    # member name ("GOOGLE_DRIVE"). (A mismatch would in fact fail the INSERT above, since the
    # migration's enum type only defines the lowercase labels - this asserts it explicitly.)
    stored_provider = await db_session.scalar(
        text("SELECT provider::text FROM event_creator.storage_configs WHERE user_id = :uid"),
        {"uid": user.id},
    )
    assert stored_provider == "google_drive"

    # An async refresh repopulates from the DB (incl. the server-default timestamps) and maps the
    # label back to the enum member.
    await db_session.refresh(config)
    assert config.provider is StorageProviderType.GOOGLE_DRIVE
    assert config.folder_path == "/OrganizeMe/exports"
    assert config.oauth_access_token is None
    assert config.created_at is not None


async def test_storage_config_is_unique_per_user(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    db_session.add(
        StorageConfig(user_id=user.id, provider=StorageProviderType.S3, folder_path="/first")
    )
    await db_session.flush()

    db_session.add(
        StorageConfig(user_id=user.id, provider=StorageProviderType.DROPBOX, folder_path="/second")
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_storage_provider_enum_has_exactly_the_spec_labels(db_session: AsyncSession) -> None:
    # The DB enum type must carry exactly the three lowercase labels from the Slice 2 spec - this
    # guards both the spec contract and the model's values_callable (member value vs member name).
    labels = (
        await db_session.scalars(
            text(
                "SELECT unnest(enum_range(NULL::event_creator.storage_provider))::text ORDER BY 1"
            )
        )
    ).all()

    assert set(labels) == {"google_drive", "dropbox", "s3"}
    assert set(labels) == {member.value for member in StorageProviderType}
