import uuid
from datetime import datetime
from enum import Enum

from fastapi_users_db_sqlalchemy.generics import GUID
from sqlalchemy import DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProcessingStepStatus(str, Enum):
    """State of one of the 7 pipeline steps within a run. ``skipped`` covers steps that don't
    apply to a given file (e.g. Extract on a non-zip)."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class ProcessingStep(Base):
    """One of the 7 steps of a ProcessingRun, with its own status and captured log lines.

    Rows are created and updated by the in-process pipeline (#52); the SSE progress page (#53)
    streams their status changes. This model + its migration are the Slice 4.0 foundation (#51).
    """

    __tablename__ = "processing_steps"
    __table_args__ = {"schema": "event_creator"}

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("event_creator.processing_runs.id", ondelete="cascade"),
        nullable=False,
    )
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    step_name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ProcessingStepStatus] = mapped_column(
        SAEnum(
            ProcessingStepStatus,
            name="processing_step_status",
            schema="event_creator",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
        default=ProcessingStepStatus.PENDING,
    )
    # Human-readable log lines captured for this step, shown on the logs page. JSONB array of
    # strings; defaults to an empty array so a freshly-created step is never null.
    log_lines: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
