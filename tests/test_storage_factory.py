"""Unit tests for app.services.storage.factory's provider-resolution branching (#93).

Confirms build_storage_provider picks the concrete provider class matching a config's
``provider`` column, rather than always resolving to Google Drive (the pre-Slice-8 behaviour).
"""

import uuid

import pytest
from cryptography.fernet import Fernet

from app.core.config import Settings
from app.core.security import CredentialCipher
from app.models.storage_config import StorageConfig, StorageProviderType
from app.services.storage.dropbox import DropboxStorageProvider
from app.services.storage.factory import build_storage_provider
from app.services.storage.google_drive import GoogleDriveStorageProvider

_CIPHER = CredentialCipher(Fernet.generate_key())


def _settings() -> Settings:
    return Settings(
        database_url="sqlite+aiosqlite://",
        jwt_secret="secret",
        google_oauth_client_id="g-id",
        google_oauth_client_secret="g-secret",
        google_oauth_redirect_uri="http://localhost/cb",
        dropbox_oauth_client_id="d-id",
        dropbox_oauth_client_secret="d-secret",
        e2e_test_mode=False,
    )


def _config(provider: StorageProviderType) -> StorageConfig:
    return StorageConfig(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        provider=provider,
        folder_path="/OrganizeMe",
    )


def test_dropbox_config_resolves_to_dropbox_provider() -> None:
    provider = build_storage_provider(
        config=_config(StorageProviderType.DROPBOX),
        settings=_settings(),
        cipher=_CIPHER,
    )
    assert isinstance(provider, DropboxStorageProvider)


def test_google_drive_config_resolves_to_google_drive_provider() -> None:
    provider = build_storage_provider(
        config=_config(StorageProviderType.GOOGLE_DRIVE),
        settings=_settings(),
        cipher=_CIPHER,
    )
    assert isinstance(provider, GoogleDriveStorageProvider)


def test_s3_config_is_not_yet_supported() -> None:
    with pytest.raises(ValueError, match="unsupported storage provider"):
        build_storage_provider(
            config=_config(StorageProviderType.S3),
            settings=_settings(),
            cipher=_CIPHER,
        )
