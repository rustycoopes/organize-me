"""The authenticated Processing progress page (Slice 4.2, #53).

Shows the 7 pipeline-step indicators for a processing run and streams live updates from
``/api/v1/processing-runs/{id}/sse`` via the HTMX SSE extension. The Upload page (#52) sends the
user here as ``/processing?run=<id>`` right after an upload; opening ``/processing`` with no run
(e.g. the sidebar link) falls back to the user's most recent run, or an empty state if they have
none. Served here (off the app.pages.app_shell placeholder) now that it has real content.

The page paints the run's current step states server-side first, then the SSE stream takes over —
so a run that already finished before the page loaded still renders correctly, and a running one
advances live.
"""

import uuid

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.users import current_active_user_optional
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
