"""List + delete the current user's extracted events (Slice 5.1, #54).

``GET /api/v1/events`` backs the dashboard table: the user's events, paginated 50/page, newest
``resolved_date_earliest`` first. ``DELETE /api/v1/events/{id}`` removes a single event, scoped to
the requesting user so no one can delete (or even discover the existence of) another user's event.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.users import current_active_user
from app.core.calendar_url import build_google_calendar_url, build_google_tasks_url
from app.db.session import get_db
from app.models.event import Event
from app.models.user import User
from app.schemas.event import EventListRead, EventRead

router = APIRouter(prefix="/api/v1", tags=["events"])

PAGE_SIZE = 50


def to_event_read(event: Event) -> EventRead:
    """Build the API/page representation of an event, computing its Calendar/Tasks links.

    Shared by the JSON endpoint and the dashboard page (app.pages.dashboard) so both render the
    same links from one place."""
    return EventRead(
        id=event.id,
        type=event.type,
        description=event.description,
        resolved_date=event.resolved_date,
        resolved_date_earliest=event.resolved_date_earliest,
        raw_date_text=event.raw_date_text,
        agreed_by=event.agreed_by,
        created_at=event.created_at,
        calendar_url=build_google_calendar_url(
            title=event.description,
            event_date=event.resolved_date_earliest,
            raw_date_text=event.raw_date_text,
            agreed_by=event.agreed_by,
        ),
        tasks_url=build_google_tasks_url(
            title=event.description, due_date=event.resolved_date_earliest
        ),
    )


async def list_user_events(
    db: AsyncSession, user_id: uuid.UUID, page: int = 1
) -> tuple[list[Event], int]:
    """The user's events for one page, newest ``resolved_date_earliest`` first, plus the total
    count (for pagination). Shared by the JSON endpoint and the dashboard page's server-rendered
    table.

    ``.nullslast()`` is required: Postgres treats NULL as larger than any value by default, so a
    plain ``.desc()`` would otherwise surface unresolved ("TBC") dates at the very top instead of
    the bottom.
    """
    total = await db.scalar(
        select(func.count()).select_from(Event).where(Event.user_id == user_id)
    )
    result = await db.scalars(
        select(Event)
        .where(Event.user_id == user_id)
        .order_by(Event.resolved_date_earliest.desc().nullslast(), Event.created_at.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
    )
    return list(result.all()), total or 0


@router.get("/events", response_model=EventListRead)
async def read_events(
    page: int = Query(default=1, ge=1),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
) -> EventListRead:
    events, total = await list_user_events(db, user.id, page)
    return EventListRead(
        events=[to_event_read(e) for e in events], page=page, page_size=PAGE_SIZE, total=total
    )


@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: uuid.UUID,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    event = await db.scalar(select(Event).where(Event.id == event_id, Event.user_id == user.id))
    if event is None:
        # Same 404 whether the id doesn't exist at all or belongs to another user - never confirm
        # another user's event exists.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await db.delete(event)
    await db.commit()
