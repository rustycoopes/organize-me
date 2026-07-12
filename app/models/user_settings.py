import uuid
from datetime import datetime

from fastapi_users_db_sqlalchemy.generics import GUID
from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserSettings(Base):
    """Event-Creator-owned per-user settings: notification preferences + onboarding progress.

    One row per user (unique on user_id, cascade-deleted with the Host user) - these columns used
    to sit on `host.users` even though they're written and read entirely by Event-Creator flows.
    Created lazily via `get_or_create_user_settings` on first read/write (mirrors `LLMPrompt`'s
    lazy-seed pattern - see app/services/user_settings.py), rather than eagerly at registration,
    so `on_after_register` stays a pure Host action that never writes Event-Creator data (#158 /
    Slice R2).
    """

    __tablename__ = "user_settings"
    __table_args__ = {"schema": "event_creator"}

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    # UNIQUE: one settings row per user. ON DELETE CASCADE so removing a user removes their
    # settings (matches llm_prompts / storage_configs).
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("host.users.id", ondelete="cascade"), nullable=False, unique=True
    )
    notification_sms: Mapped[bool] = mapped_column(default=True, server_default="true")
    notification_email: Mapped[bool] = mapped_column(default=True, server_default="true")
    onboarding_storage_done: Mapped[bool] = mapped_column(default=False, server_default="false")
    onboarding_notifications_done: Mapped[bool] = mapped_column(
        default=False, server_default="false"
    )
    onboarding_first_upload_done: Mapped[bool] = mapped_column(
        default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
