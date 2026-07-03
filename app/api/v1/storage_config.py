"""Read/write the current user's single storage configuration (issue #46).

`GET`/`PUT /api/v1/storage-config` back the Settings > Storage tab. This slice only wires the
provider + watch-folder path end to end (using the FakeStorageProvider for tests); the live
Google Drive OAuth connect/disconnect flow that populates the encrypted credential columns lands
in issue #47.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.users import current_active_user
from app.db.session import get_db
from app.models.storage_config import StorageConfig
from app.models.user import User
from app.schemas.storage_config import StorageConfigRead, StorageConfigWrite

router = APIRouter(prefix="/api/v1", tags=["storage-config"])


async def get_user_storage_config(db: AsyncSession, user_id: uuid.UUID) -> StorageConfig | None:
    """The user's single storage config row, or ``None`` if they haven't configured one.

    Shared by this router and the Settings page (app.pages.settings) so the "one config per
    user" lookup lives in exactly one place.
    """
    result = await db.execute(select(StorageConfig).where(StorageConfig.user_id == user_id))
    return result.scalar_one_or_none()


@router.get("/storage-config", response_model=StorageConfigRead)
async def read_storage_config(
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
) -> StorageConfigRead:
    config = await get_user_storage_config(db, user.id)
    if config is None:
        # Unset state: an all-null read the settings page renders as an empty form.
        return StorageConfigRead()
    return StorageConfigRead(
        provider=config.provider,
        folder_path=config.folder_path,
        is_connected=config.oauth_access_token is not None,
    )


@router.put("/storage-config", response_model=StorageConfigRead)
async def upsert_storage_config(
    payload: StorageConfigWrite,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
) -> StorageConfigRead:
    config = await get_user_storage_config(db, user.id)
    if config is None:
        # One row per user (user_id is UNIQUE), so this is a create-or-update, never an insert of
        # a second row.
        config = StorageConfig(
            user_id=user.id,
            provider=payload.provider,
            folder_path=payload.folder_path,
        )
        db.add(config)
    else:
        config.provider = payload.provider
        config.folder_path = payload.folder_path
    # get_db doesn't auto-commit, so persist here (savepoint-safe under the test fixture's
    # rolled-back session).
    await db.commit()
    return StorageConfigRead(
        provider=payload.provider,
        folder_path=config.folder_path,
        is_connected=config.oauth_access_token is not None,
    )
