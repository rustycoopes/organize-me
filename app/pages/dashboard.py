"""The authenticated events Dashboard page (Slice 5.1, #54).

Renders the events table — the first user-visible payoff of the whole pipeline: after a run, the
user comes here to see what was extracted. The first page is painted server-side (reusing the same
``partials/events_table.html`` fragment the ``/api/v1/events`` endpoint returns) so the table is
present without JavaScript; HTMX then swaps the panel for pagination. Anonymous visitors are sent to
/login, matching every other authenticated page. Served here now that ``/dashboard`` has real
content (previously an app_shell placeholder).
"""

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.events import load_events_page
from app.auth.users import current_active_user_optional
from app.core.templating import templates
from app.db.session import get_db
from app.models.user import User

router = APIRouter(tags=["pages"])


@router.get("/dashboard", response_model=None)
async def dashboard_page(
    request: Request,
    page: int = Query(default=1, ge=1),
    user: User | None = Depends(current_active_user_optional),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    if user is None:
        return RedirectResponse("/login", status_code=302)
    events_page = await load_events_page(db, user.id, page)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {"user": user, "dark_mode": user.dark_mode, "events_page": events_page},
    )
