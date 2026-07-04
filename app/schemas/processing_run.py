import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.processing_run import ProcessingRunStatus


class ProcessingRunRead(BaseModel):
    """A single processing run as returned by ``GET /api/v1/processing-runs``."""

    id: uuid.UUID
    filename: str
    status: ProcessingRunStatus
    events_extracted_count: int
    created_at: datetime


class ProcessingRunListRead(BaseModel):
    """One page of the current user's processing runs, plus enough to render pagination controls."""

    runs: list[ProcessingRunRead]
    page: int
    page_size: int
    total: int
