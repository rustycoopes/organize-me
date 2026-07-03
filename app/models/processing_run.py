import uuid
from datetime import datetime
from enum import Enum

from fastapi_users_db_sqlalchemy.generics import GUID
from sqlalchemy import DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProcessingRunStatus(str, Enum):
    """Lifecycle of a single file's processing run."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"


class ProcessingRun(Base):
    """One end-to-end processing attempt for an uploaded/detected file.

    Parent of the per-step rows (ProcessingStep) and the extracted Events. This model + its
    migration are the Slice 4.0 foundation (#51); the upload endpoint and Celery pipeline that
    create and drive runs land in #52.
    """

    __tablename__ = "processing_runs"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    # ON DELETE CASCADE so removing a user removes their runs (matches the other user-owned tables).
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="cascade"), nullable=False
    )
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    # values_callable stores the enum *values* ("in_progress"), not the member names, so the DB
    # labels match the JSON API (same approach as StorageConfig.provider).
    status: Mapped[ProcessingRunStatus] = mapped_column(
        SAEnum(
            ProcessingRunStatus,
            name="processing_run_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
        default=ProcessingRunStatus.PENDING,
    )
    events_extracted_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # Set when the run starts/finishes; null until then.
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
