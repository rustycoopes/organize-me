"""SSE stream for live pipeline progress (Slice 4.2, #53), list processing runs (Slice 6.1, #83),
and run detail + logs (Slice 6.2, #84).

``GET /api/v1/processing-runs`` backs the logs page: the user's processing runs, paginated 50/page,
newest ``created_at`` first. ``GET /api/v1/processing-runs/{run_id}`` returns a single run with its
step statuses and detail. ``GET /api/v1/processing-runs/{run_id}/logs`` returns structured log lines
for one step (paginated, searchable). ``GET /api/v1/processing-runs/{run_id}/sse`` streams a run's
step-status transitions to the browser so the progress page can advance its 7 indicators live via
HTMX SSE — no manual refresh. The heavy lifting (polling, change detection, fragment rendering,
terminal close) lives in app.services.pipeline.progress; this module only resolves + ownership-gates
the run and wraps the generator in an ``EventSourceResponse``.

A run is only ever exposed to the user who owns it (404 otherwise), matching every other user-owned
resource in the app.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.auth.users import current_active_user
from app.db.session import get_db
from app.models.processing_run import ProcessingRun
from app.models.processing_step import ProcessingStep
from app.models.user import User
from app.schemas.processing_run import (
    ProcessingLogLineRead,
    ProcessingRunDetailRead,
    ProcessingRunListRead,
    ProcessingRunLogsDownloadRead,
    ProcessingRunRead,
    ProcessingStepLogsRead,
    ProcessingStepRead,
)
from app.services.pipeline.progress import stream_run_progress
from app.services.processing_logs import LOG_PAGE_SIZE, filter_log_lines, paginate_log_lines

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


@router.get("/processing-runs/{run_id}")
async def read_processing_run(
    run_id: uuid.UUID,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ProcessingRunDetailRead:
    """Run detail with all steps and their statuses (Slice 6.2, #84)."""
    run = await db.get(ProcessingRun, run_id)
    if run is None or run.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run_not_found")

    steps_result = await db.scalars(
        select(ProcessingStep).where(ProcessingStep.run_id == run_id).order_by(ProcessingStep.step_number)
    )
    steps = [
        ProcessingStepRead(
            step_number=s.step_number,
            step_name=s.step_name,
            status=s.status,
            started_at=s.started_at,
            completed_at=s.completed_at,
        )
        for s in steps_result.all()
    ]

    return ProcessingRunDetailRead(
        id=run.id,
        filename=run.filename,
        status=run.status,
        events_extracted_count=run.events_extracted_count,
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
        steps=steps,
    )


@router.get("/processing-runs/{run_id}/logs")
async def read_processing_run_logs(
    run_id: uuid.UUID,
    step_number: int = Query(..., ge=1, le=7),
    page: int = Query(default=1, ge=1),
    search: str | None = Query(default=None),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ProcessingLogLineRead:
    """Structured log lines for one step, paginated and searchable (Slice 6.2, #84)."""
    run = await db.get(ProcessingRun, run_id)
    if run is None or run.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run_not_found")

    step = await db.scalar(
        select(ProcessingStep).where(
            and_(ProcessingStep.run_id == run_id, ProcessingStep.step_number == step_number)
        )
    )
    if step is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="step_not_found")

    log_lines = filter_log_lines(step.log_lines or [], search)
    paginated, total = paginate_log_lines(log_lines, page)

    return ProcessingLogLineRead(
        step_number=step.step_number,
        step_name=step.step_name,
        log_lines=paginated,
        page=page,
        page_size=LOG_PAGE_SIZE,
        total=total,
    )


@router.get("/processing-runs/{run_id}/logs/download")
async def download_processing_run_logs(
    run_id: uuid.UUID,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """The run's full structured logs across all steps, as a downloadable JSON file (Slice 6.3, #85)."""
    run = await db.get(ProcessingRun, run_id)
    if run is None or run.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run_not_found")

    steps_result = await db.scalars(
        select(ProcessingStep).where(ProcessingStep.run_id == run_id).order_by(ProcessingStep.step_number)
    )
    payload = ProcessingRunLogsDownloadRead(
        run_id=run.id,
        filename=run.filename,
        steps=[
            ProcessingStepLogsRead(
                step_number=s.step_number,
                step_name=s.step_name,
                status=s.status,
                log_lines=s.log_lines or [],
            )
            for s in steps_result.all()
        ],
    )

    return Response(
        content=payload.model_dump_json(),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="processing-run-{run.id}-logs.json"'
        },
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
