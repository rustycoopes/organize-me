"""SSE stream for live pipeline progress (Slice 4.2, #53).

``GET /api/v1/processing-runs/{run_id}/sse`` streams a run's step-status transitions to the browser
so the progress page (app.pages.processing) can advance its 7 indicators live via the HTMX SSE
extension — no manual refresh. The heavy lifting (polling, change detection, fragment rendering,
terminal close) lives in app.services.pipeline.progress; this module only resolves + ownership-gates
the run and wraps the generator in an ``EventSourceResponse``.

A run is only ever exposed to the user who owns it (404 otherwise), matching every other user-owned
resource in the app.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.auth.users import current_active_user
from app.db.session import get_db
from app.models.processing_run import ProcessingRun
from app.models.user import User
from app.services.pipeline.progress import stream_run_progress

router = APIRouter(prefix="/api/v1", tags=["processing-runs"])


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
