from datetime import datetime

from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID
from sqlalchemy import DateTime, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "users"
    __table_args__ = (
        # FastAPI-Users looks up users by case-insensitive email (func.lower(email) in
        # SQLAlchemyUserDatabase.get_by_email), so uniqueness must be enforced the same way,
        # or two accounts differing only by case could be created.
        Index("ix_users_email_lower", text("lower(email)"), unique=True),
    )

    # Override the mixin's plain case-sensitive unique index; ix_users_email_lower above
    # replaces it.
    email: Mapped[str] = mapped_column(String(length=320), nullable=False, index=False, unique=False)

    name: Mapped[str | None] = mapped_column(nullable=True)
    phone_number: Mapped[str | None] = mapped_column(nullable=True)
    dark_mode: Mapped[bool] = mapped_column(default=False, server_default="false")
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
