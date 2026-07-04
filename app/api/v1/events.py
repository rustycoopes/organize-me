"""Events dashboard read + delete API (Slice 5.1, #54).

``GET /api/v1/events`` returns the requesting user's extracted events as an HTML table fragment,
paginated at 50 per page and sorted newest ``resolved_date_earliest`` first. It's an HTML fragment
(not JSON) because the dashboard swaps it in place via HTMX for pagination — Slice 5.2 (#55) extends
the very same endpoint with filter/sort/search query params, reusing this fragment.

``DELETE /api/v1/events/{id}`` removes a single event, owner-gated (404 for anyone else's event, so
the endpoint never confirms another user's event exists — matching every other user-owned resource).

The pagination + per-row calendar/tasks URL building lives in ``load_events_page`` so the dashboard
page (``app.pages.dashboard``) can render the identical first-page fragment server-side.
"""

import math
import uuid
from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.users import current_active_user
from app.core.calendar_url import google_calendar_url, google_tasks_url
from app.core.templating import templates
from app.db.session import get_db
from app.models.event import Event
from app.models.user import User

router = APIRouter(prefix="/api/v1", tags=["events"])

PAGE_SIZE = 50


@dataclass(frozen=True)
class EventView:
    """One event's display fields plus its pre-built Calendar/Tasks links."""

    id: uuid.UUID
    type: str
    description: str
    resolved_date: str
    raw_date_text: str
    agreed_by: list[str]
    calendar_url: str
    tasks_url: str


@dataclass(frozen=True)
class EventsPage:
    """A single page of the events table, carrying everything the fragment needs to paginate."""

    events: list[EventView]
    page: int
    total: int
    page_size: int

    @property
    def total_pages(self) -> int:
        return max(1, math.ceil(self.total / self.page_size))

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def prev_page(self) -> int:
        return self.page - 1

    @property
    def next_page(self) -> int:
        return self.page + 1


def _to_view(event: Event) -> EventView:
    agreed_by = list(event.agreed_by)
    return EventView(
        id=event.id,
        type=event.type,
        description=event.description,
        resolved_date=event.resolved_date,
        raw_date_text=event.raw_date_text,
        agreed_by=agreed_by,
        calendar_url=google_calendar_url(
            event.description, event.resolved_date_earliest, event.raw_date_text, agreed_by
        ),
        tasks_url=google_tasks_url(event.description, event.resolved_date_earliest),
    )


async def load_events_page(db: AsyncSession, user_id: uuid.UUID, page: int) -> EventsPage:
    """Load one 50-row page of a user's events, newest ``resolved_date_earliest`` first.

    Undated events (``resolved_date_earliest`` is null, e.g. a "TBC" date) sort last, then
    ``created_at`` desc breaks ties so ordering is stable across pages.
    """
    total = await db.scalar(
        select(func.count()).select_from(Event).where(Event.user_id == user_id)
    )
    total = total or 0
    # Clamp to a real page so an out-of-range request (a stale ?page= link, or a page whose events
    # were all deleted) lands on the last page instead of an empty table with a bogus "Page N of M".
    total_pages = max(1, math.ceil(total / PAGE_SIZE))
    page = min(max(1, page), total_pages)
    rows = (
        await db.scalars(
            select(Event)
            .where(Event.user_id == user_id)
            .order_by(
                Event.resolved_date_earliest.desc().nullslast(),
                Event.created_at.desc(),
            )
            .offset((page - 1) * PAGE_SIZE)
            .limit(PAGE_SIZE)
        )
    ).all()
    return EventsPage(
        events=[_to_view(event) for event in rows],
        page=page,
        total=total,
        page_size=PAGE_SIZE,
    )


@router.get("/events", response_model=None)
async def list_events(
    request: Request,
    page: int = Query(default=1, ge=1),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    events_page = await load_events_page(db, user.id, page)
    return templates.TemplateResponse(
        request, "partials/events_table.html", {"events_page": events_page}
    )


@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: uuid.UUID,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    event = await db.get(Event, event_id)
    if event is None or event.user_id != user.id:
        # 404 (not 403) so the endpoint never confirms another user's event exists.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="event_not_found")
    await db.delete(event)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
