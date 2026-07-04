"""Tests for the events Dashboard page (Slice 5.1, #54)."""

import uuid
from datetime import date, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event
from app.models.processing_run import ProcessingRun, ProcessingRunStatus


def unique_email() -> str:
    return f"dashboard-{uuid.uuid4().hex}@example.com"


async def _register_and_login(client: AsyncClient) -> uuid.UUID:
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})
    me = await client.get("/api/v1/users/me")
    return uuid.UUID(me.json()["id"])


async def _make_run(db: AsyncSession, user_id: uuid.UUID) -> uuid.UUID:
    run = ProcessingRun(
        user_id=user_id, filename="chat.txt", status=ProcessingRunStatus.SUCCESS
    )
    db.add(run)
    await db.flush()
    return run.id


async def _make_event(
    db: AsyncSession,
    user_id: uuid.UUID,
    run_id: uuid.UUID,
    description: str,
    *,
    type: str = "School",
    resolved_date: str = "6 June 2026",
    earliest: date | None = date(2026, 6, 6),
    raw_date_text: str = "6 June",
    agreed_by: list[str] | None = None,
) -> Event:
    event = Event(
        user_id=user_id,
        run_id=run_id,
        type=type,
        description=description,
        resolved_date=resolved_date,
        resolved_date_earliest=earliest,
        raw_date_text=raw_date_text,
        agreed_by=agreed_by or [],
    )
    db.add(event)
    await db.flush()
    return event


async def test_dashboard_redirects_anonymous_visitor_to_login(client: AsyncClient) -> None:
    response = await client.get("/dashboard")
    assert response.status_code in (302, 303, 307)
    assert response.headers["location"] == "/login"


async def test_dashboard_shows_empty_state_when_no_events(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _register_and_login(client)
    response = await client.get("/dashboard")
    assert response.status_code == 200
    body = response.text
    assert "No events yet" in body
    assert "/upload" in body
    # HTMX is loaded so pagination works once there are events.
    assert "htmx.org@1.9.12" in body


async def test_dashboard_renders_events_table_with_all_columns(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    await _make_event(
        db_session,
        user_id,
        run,
        "School fees due",
        type="School",
        raw_date_text="end of term",
        agreed_by=["Carol Danvers"],
    )

    response = await client.get("/dashboard")
    body = response.text
    assert "School fees due" in body
    assert "School" in body
    assert "end of term" in body
    # agreed_by chip: initials shown, full name on hover
    assert "CD" in body and "Carol Danvers" in body
    # per-row calendar/tasks links + delete affordance + confirm modal
    assert "calendar.google.com/calendar/render" in body
    assert "tasks.google.com" in body
    assert "Delete this event?" in body


async def test_dashboard_shows_only_the_current_users_events(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    other_id = await _register_and_login(client)  # user B
    other_run = await _make_run(db_session, other_id)
    await _make_event(db_session, other_id, other_run, "B secret event")

    user_id = await _register_and_login(client)  # user A
    run = await _make_run(db_session, user_id)
    await _make_event(db_session, user_id, run, "A own event")

    response = await client.get("/dashboard")
    body = response.text
    assert "A own event" in body
    assert "B secret event" not in body


async def test_dashboard_shows_pagination_controls_beyond_one_page(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    for i in range(51):
        await _make_event(
            db_session,
            user_id,
            run,
            f"Event {i:02d}",
            resolved_date=f"2026-06-{(i % 28) + 1:02d} #{i}",
            earliest=date(2026, 1, 1) + timedelta(days=i),
        )

    response = await client.get("/dashboard")
    body = response.text
    assert "Page 1 of 2" in body
    assert "/api/v1/events?page=2" in body
