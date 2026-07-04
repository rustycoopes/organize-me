"""The authenticated Events dashboard (Slice 5.1, #54).

The first user-visible payoff of the processing pipeline: a paginated table of the events Gemini
extracted, with per-row Google Calendar/Tasks links and delete. Served here (rather than as the
generic placeholder in app.pages.app_shell) now that it has real content. Anonymous visitors are
redirected to /login like the other authenticated pages.
"""

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.events import PAGE_SIZE, list_user_events, to_event_read
from app.auth.users import current_active_user_optional
from app.core.onboarding import build_onboarding_steps, onboarding_complete
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
    events, total = await list_user_events(db, user.id, page)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    # A page beyond the last valid one (e.g. a stale bookmark, or the last event on that page was
    # just deleted) would otherwise render the empty-state message even though the user has
    # earlier events - redirect to the last real page instead of showing a misleading "No events
    # yet". Only applies here (the browsable page); the JSON API returns an honest empty list for
    # an out-of-range page rather than redirecting a GET a client didn't ask to be redirected from.
    if total > 0 and page > total_pages:
        return RedirectResponse(f"/dashboard?page={total_pages}", status_code=302)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "user": user,
            "dark_mode": user.dark_mode,
            "events": [to_event_read(e) for e in events],
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "onboarding_steps": build_onboarding_steps(user),
            "onboarding_complete": onboarding_complete(user),
        },
    )
