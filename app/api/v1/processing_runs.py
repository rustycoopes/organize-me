"""SSE stream for live pipeline progress (Slice 4.2, #53) and list processing runs (Slice 6.1, #83).

``GET /api/v1/processing-runs`` backs the logs page: the user's processing runs, paginated 50/page,
newest ``created_at`` first. ``GET /api/v1/processing-runs/{run_id}/sse`` streams a run's step-status
transitions to the browser so the progress page (app.pages.processing) can advance its 7 indicators
live via the HTMX SSE extension — no manual refresh. The heavy lifting (polling, change detection,
fragment rendering, terminal close) lives in app.services.pipeline.progress; this module only
resolves + ownership-gates the run and wraps the generator in an ``EventSourceResponse``.

A run is only ever exposed to the user who owns it (404 otherwise), matching every other user-owned
resource in the app.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.auth.users import current_active_user
from app.db.session import get_db
from app.models.processing_run import ProcessingRun
from app.models.user import User
from app.schemas.processing_run import ProcessingRunListRead, ProcessingRunRead
from app.services.pipeline.progress import stream_run_progress

router = APIRouter(prefix="/api/v1", tags=["processing-runs"])

PAGE_SIZE = 50


def to_processing_run_read(run: ProcessingRun) -> ProcessingRunRead:
    """Build the API/page representation of a processing run."""
    return ProcessingRunRead(
        id=run.id,
        filename=run.filename,
        status=run.status,
        events_extracted_count=run.events_extracted_count,
        created_at=run.created_at,
    )


async def list_user_processing_runs(
    db: AsyncSession, user_id: uuid.UUID, page: int = 1
) -> tuple[list[ProcessingRun], int]:
    """The user's processing runs for one page, newest ``created_at`` first, plus the total count."""
    total = await db.scalar(
        select(func.count()).select_from(ProcessingRun).where(ProcessingRun.user_id == user_id)
    )
    result = await db.scalars(
        select(ProcessingRun)
        .where(ProcessingRun.user_id == user_id)
        .order_by(ProcessingRun.created_at.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
    )
    return list(result.all()), total or 0


@router.get("/processing-runs", response_model=ProcessingRunListRead)
async def read_processing_runs(
    page: int = Query(default=1, ge=1),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ProcessingRunListRead:
    runs, total = await list_user_processing_runs(db, user.id, page)
    return ProcessingRunListRead(
        runs=[to_processing_run_read(r) for r in runs],
        page=page,
        page_size=PAGE_SIZE,
        total=total,
    )


@router.get("/processing-runs/{run_id}/sse")
async def processing_run_sse(
    run_id: uuid.UUID,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
) -> EventSourceResponse:
    run = await db.get(ProcessingRun, run_id)
    if run is None or run.user_id != user.id:
        # 404 (not 403) so the endpoint never confirms another user's run exists.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run_not_found")
    return EventSourceResponse(stream_run_progress(db, run_id))
