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
from app.core.config import Settings
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


def config_is_connected(config: StorageConfig | None) -> bool:
    """Whether a fetched config row represents a usable, connected Google Drive.

    Split out from `is_drive_connected` so a caller that already fetched the config for another
    reason (e.g. to build a StorageProvider from it) can reuse this same definition of "connected"
    without an extra query - see app.api.v1.import_pending_files.get_import_storage.
    """
    return config is not None and config.oauth_access_token is not None


async def is_drive_connected(db: AsyncSession, user_id: uuid.UUID, settings: Settings) -> bool:
    """Whether the user has a usable, connected Google Drive (or E2E is faking one).

    Shared by the Upload and Dashboard pages so both gate their "requires real storage" UI
    (ephemeral-upload warning, the Import pending files button) on the same definition of
    "connected" rather than each re-deriving it from the config row.
    """
    if settings.e2e_test_mode:
        return True
    config = await get_user_storage_config(db, user_id)
    return config_is_connected(config)


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
        if config.provider != payload.provider:
            # Switching providers leaves any previously-connected credentials meaningless for the
            # new one (a Google Drive OAuth token doesn't authenticate Dropbox calls, etc.) - clear
            # them so `is_connected`/build_storage_provider don't act on stale, wrong-provider
            # credentials. Without this, a config that's still "connected" by an old provider's
            # token but now points `provider` at a not-yet-implemented backend (S3, until #94
            # lands) would reach build_storage_provider's ValueError instead of the "please
            # connect" state a genuinely-disconnected config gets.
            config.oauth_access_token = None
            config.oauth_refresh_token = None
            config.oauth_token_expires_at = None
            config.s3_access_key = None
            config.s3_secret_key = None
            config.s3_bucket_name = None
            config.s3_region = None
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
