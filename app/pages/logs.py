"""The authenticated Processing History logs page (Slice 6.1, #83).

Display a paginated table of the user's processing runs, showing run date, filename, status, and
event count for each run. Each row links to its run detail page. Anonymous visitors are redirected
to /login like the other authenticated pages.
"""

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.processing_runs import PAGE_SIZE, list_user_processing_runs, to_processing_run_read
from app.auth.users import current_active_user_optional
from app.core.templating import templates
from app.db.session import get_db
from app.models.user import User

router = APIRouter(tags=["pages"])


@router.get("/logs", response_model=None)
async def logs_page(
    request: Request,
    page: int = Query(default=1, ge=1),
    user: User | None = Depends(current_active_user_optional),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    if user is None:
        return RedirectResponse("/login", status_code=302)
    runs, total = await list_user_processing_runs(db, user.id, page)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    if total > 0 and page > total_pages:
        return RedirectResponse(f"/logs?page={total_pages}", status_code=302)
    return templates.TemplateResponse(
        request,
        "logs.html",
        {
            "user": user,
            "dark_mode": user.dark_mode,
            "runs": [to_processing_run_read(r) for r in runs],
            "page": page,
            "total_pages": total_pages,
            "total": total,
        },
    )
