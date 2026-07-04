"""The authenticated Processing progress page (Slice 4.2, #53) and run detail page (Slice 6.2, #84).

Shows the 7 pipeline-step indicators for a processing run and streams live updates from
``/api/v1/processing-runs/{id}/sse`` via the HTMX SSE extension. The Upload page (#52) sends the
user here as ``/processing?run=<id>`` right after an upload; opening ``/processing`` with no run
(e.g. the sidebar link) falls back to the user's most recent run, or an empty state if they have
none. Served here (off the app.pages.app_shell placeholder) now that it has real content.

The progress page paints the run's current step states server-side first, then the SSE stream takes
over — so a run that already finished before the page loaded still renders correctly, and a running
one advances live.

The detail page (``/processing-runs/{id}``) shows a historical run with final step statuses and
structured log lines for each step (paginated, searchable via HTMX).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.users import current_active_user, current_active_user_optional
from app.core.templating import templates
from app.db.session import get_db
from app.models.processing_run import ProcessingRun
from app.models.user import User
from app.services.pipeline.progress import (
    TERMINAL_RUN_STATUSES,
    build_step_views,
    load_step_statuses,
)

router = APIRouter(tags=["pages"])


async def _latest_run(db: AsyncSession, user_id: uuid.UUID) -> ProcessingRun | None:
    run: ProcessingRun | None = await db.scalar(
        select(ProcessingRun)
        .where(ProcessingRun.user_id == user_id)
        .order_by(ProcessingRun.created_at.desc())
        .limit(1)
    )
    return run


async def _owned_run(
    db: AsyncSession, user_id: uuid.UUID, run_id: uuid.UUID
) -> ProcessingRun | None:
    run = await db.get(ProcessingRun, run_id)
    return run if run is not None and run.user_id == user_id else None


def _parse_run_id(run: str | None) -> uuid.UUID | None:
    """Parse the ?run= query value to a UUID, tolerating a missing/malformed value (→ None).

    Kept lenient (rather than a typed UUID query param that would 422) so a stale or hand-edited
    link falls through to the latest-run fallback instead of erroring."""
    if not run:
        return None
    try:
        return uuid.UUID(run)
    except ValueError:
        return None


@router.get("/processing", response_model=None)
async def processing_page(
    request: Request,
    run: str | None = Query(default=None),
    user: User | None = Depends(current_active_user_optional),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    if user is None:
        return RedirectResponse("/login", status_code=302)

    # A ?run= that's malformed, isn't the user's, or doesn't exist falls back to their latest run
    # rather than leaking a 404 or a 422 — the page never exposes another user's run.
    run_id = _parse_run_id(run)
    processing_run = (
        await _owned_run(db, user.id, run_id) if run_id is not None else None
    ) or await _latest_run(db, user.id)

    steps = []
    if processing_run is not None:
        steps = build_step_views(await load_step_statuses(db, processing_run.id))

    run_status = processing_run.status.value if processing_run is not None else None
    # Only stream when there's something left to watch: a run that already finished renders its
    # final state statically (no wasted SSE connection just to receive one update and close).
    live = processing_run is not None and run_status not in TERMINAL_RUN_STATUSES

    return templates.TemplateResponse(
        request,
        "processing.html",
        {
            "user": user,
            "dark_mode": user.dark_mode,
            "run": processing_run,
            "run_id": str(processing_run.id) if processing_run is not None else None,
            "run_status": run_status,
            "filename": processing_run.filename if processing_run is not None else None,
            "steps": steps,
            "live": live,
        },
    )


@router.get("/processing-runs/{run_id}", response_model=None)
async def processing_run_detail_page(
    request: Request,
    run_id: uuid.UUID,
    user: User | None = Depends(current_active_user_optional),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    """Detail page for a historical processing run (Slice 6.2, #84).

    Displays the run's metadata, step statuses, and provides HTMX-driven log viewing for each step.
    """
    if user is None:
        return RedirectResponse("/login", status_code=302)

    run = await db.get(ProcessingRun, run_id)
    if run is None or run.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    steps = build_step_views(await load_step_statuses(db, run.id))

    return templates.TemplateResponse(
        request,
        "processing_run_detail.html",
        {
            "user": user,
            "dark_mode": user.dark_mode,
            "run": run,
            "run_id": str(run.id),
            "steps": steps,
        },
    )


@router.get("/api/html/processing-runs/{run_id}/logs", response_model=None)
async def processing_run_logs_partial(
    request: Request,
    run_id: uuid.UUID,
    step_number: int = Query(..., ge=1, le=7),
    page: int = Query(default=1, ge=1),
    search: str | None = Query(default=None),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Log lines for one step as HTML partial, paginated and searchable (Slice 6.2, #84).

    Used by HTMX to swap logs into the detail page. Returns HTML (not JSON) for direct insertion.
    """
    from app.models.processing_step import ProcessingStep
    from sqlalchemy import and_

    run = await db.get(ProcessingRun, run_id)
    if run is None or run.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    step = await db.scalar(
        select(ProcessingStep).where(
            and_(ProcessingStep.run_id == run_id, ProcessingStep.step_number == step_number)
        )
    )
    if step is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    log_lines = step.log_lines or []
    if search:
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        log_lines = [line for line in log_lines if escaped.lower() in line.lower()]

    total = len(log_lines)
    page_size = 50
    start = (page - 1) * page_size
    end = start + page_size
    paginated = log_lines[start:end]

    return templates.TemplateResponse(
        request,
        "partials/processing_logs.html",
        {
            "run_id": str(run_id),
            "logs": type("Logs", (), {
                "step_number": step.step_number,
                "step_name": step.step_name,
                "log_lines": paginated,
                "page": page,
                "page_size": page_size,
                "total": total,
            })(),
            "search": search,
        },
    )
