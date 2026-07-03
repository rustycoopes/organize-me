import uuid
from datetime import datetime
from enum import Enum

from fastapi_users_db_sqlalchemy.generics import GUID
from sqlalchemy import DateTime, ForeignKey
from sqlalchemy import Enum as SAEnum
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StorageProviderType(str, Enum):
    """The cloud storage backends a user can connect. Only Google Drive is implemented in
    Slice 2; Dropbox and S3 are reserved here so the column/enum don't need a later migration."""

    GOOGLE_DRIVE = "google_drive"
    DROPBOX = "dropbox"
    S3 = "s3"


class StorageConfig(Base):
    """A user's single active storage connection (one row per user - unique on user_id).

    Credential columns (OAuth tokens, S3 keys) hold values encrypted at rest via
    app.core.security.CredentialCipher - they are never stored in plaintext. The read/write
    endpoints that populate them land in issues #46/#47; this model + its migration are the
    Slice 2.0 foundation.
    """

    __tablename__ = "storage_configs"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    # UNIQUE: one active storage config per user. ON DELETE CASCADE so removing a user removes
    # their config (matches oauth_accounts).
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="cascade"), nullable=False, unique=True
    )
    # values_callable stores the enum *values* ("google_drive"), not SQLAlchemy's default of the
    # member *names* ("GOOGLE_DRIVE"), so the DB labels match the spec and the JSON API.
    provider: Mapped[StorageProviderType] = mapped_column(
        SAEnum(
            StorageProviderType,
            name="storage_provider",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    # NOT NULL, per the Slice 2 spec: a config is created with its provider + watch folder set
    # together (the PUT /storage-config write path in #46), so a row always has a folder_path.
    folder_path: Mapped[str] = mapped_column(nullable=False)
    # All credential columns are encrypted at rest (see class docstring) and nullable - which
    # ones are populated depends on the provider.
    oauth_access_token: Mapped[str | None] = mapped_column(nullable=True)
    oauth_refresh_token: Mapped[str | None] = mapped_column(nullable=True)
    s3_access_key: Mapped[str | None] = mapped_column(nullable=True)
    s3_secret_key: Mapped[str | None] = mapped_column(nullable=True)
    s3_bucket_name: Mapped[str | None] = mapped_column(nullable=True)
    s3_region: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
