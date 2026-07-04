"""Tests for the events dashboard read + delete API (Slice 5.1, #54)."""

import uuid
from datetime import date, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event
from app.models.processing_run import ProcessingRun, ProcessingRunStatus


def unique_email() -> str:
    return f"events-api-{uuid.uuid4().hex}@example.com"


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
    *,
    description: str,
    type: str = "Medical",
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


async def test_list_events_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/events")
    assert response.status_code == 401


async def test_list_events_returns_only_the_requesters_events(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    other_id = await _register_and_login(client)  # user B
    other_run = await _make_run(db_session, other_id)
    await _make_event(db_session, other_id, other_run, description="B private event")

    user_id = await _register_and_login(client)  # now user A
    run = await _make_run(db_session, user_id)
    await _make_event(db_session, user_id, run, description="A visible event")

    response = await client.get("/api/v1/events")
    assert response.status_code == 200
    body = response.text
    assert "A visible event" in body
    assert "B private event" not in body


async def test_list_events_shows_columns_calendar_tasks_and_delete(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    event = await _make_event(
        db_session,
        user_id,
        run,
        description="Dentist appointment",
        type="Medical",
        raw_date_text="next Saturday",
        agreed_by=["Alice Smith", "Bob Jones"],
    )

    response = await client.get("/api/v1/events")
    body = response.text
    assert "Dentist appointment" in body
    assert "Medical" in body
    assert "next Saturday" in body
    # agreed_by rendered as initials chips, full name available on hover
    assert "AS" in body and "Alice Smith" in body
    # calendar + tasks links and the delete hook for this row
    assert "calendar.google.com/calendar/render" in body
    assert "tasks.google.com" in body
    assert f"event-{event.id}" in body
    assert "confirmDelete" in body


async def test_list_events_empty_state_when_no_events(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _register_and_login(client)
    response = await client.get("/api/v1/events")
    assert response.status_code == 200
    assert "No events yet" in response.text


async def test_list_events_paginates_at_50_per_page(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    # 51 events, each with a distinct earliest date so ordering is deterministic and the unique
    # (user, description, resolved_date) constraint is never hit.
    for i in range(51):
        await _make_event(
            db_session,
            user_id,
            run,
            description=f"Event {i:02d}",
            resolved_date=f"2026-06-{(i % 28) + 1:02d} #{i}",
            earliest=date(2026, 1, 1) + timedelta(days=i),
        )

    page1 = await client.get("/api/v1/events?page=1")
    assert page1.status_code == 200
    assert page1.text.count('<tr id="event-') == 50
    assert "Page 1 of 2" in page1.text

    page2 = await client.get("/api/v1/events?page=2")
    assert page2.status_code == 200
    assert page2.text.count('<tr id="event-') == 1
    assert "Page 2 of 2" in page2.text


async def test_list_events_clamps_out_of_range_page_to_the_last_page(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    await _make_event(db_session, user_id, run, description="Only event")

    # Way past the last page → clamp to page 1 (the last page) rather than an empty table.
    response = await client.get("/api/v1/events?page=99")
    assert response.status_code == 200
    assert "Only event" in response.text


async def test_list_events_sorts_newest_resolved_date_earliest_first(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    await _make_event(
        db_session, user_id, run, description="Older", earliest=date(2026, 1, 1)
    )
    await _make_event(
        db_session, user_id, run, description="Newer", earliest=date(2026, 12, 31)
    )

    response = await client.get("/api/v1/events")
    body = response.text
    assert body.index("Newer") < body.index("Older")


async def test_delete_event_removes_own_event(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    event = await _make_event(db_session, user_id, run, description="Delete me")

    response = await client.delete(f"/api/v1/events/{event.id}")
    assert response.status_code == 204

    # It's gone from the list afterwards.
    listing = await client.get("/api/v1/events")
    assert "Delete me" not in listing.text
    assert await db_session.get(Event, event.id) is None


async def test_delete_event_owned_by_another_user_is_404_and_not_deleted(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    other_id = await _register_and_login(client)  # user B
    other_run = await _make_run(db_session, other_id)
    event = await _make_event(db_session, other_id, other_run, description="B's event")

    await _register_and_login(client)  # now user A
    response = await client.delete(f"/api/v1/events/{event.id}")
    assert response.status_code == 404
    # B's event is untouched.
    assert await db_session.get(Event, event.id) is not None


async def test_delete_nonexistent_event_is_404(client: AsyncClient) -> None:
    await _register_and_login(client)
    response = await client.delete(f"/api/v1/events/{uuid.uuid4()}")
    assert response.status_code == 404


async def test_delete_event_requires_authentication(client: AsyncClient) -> None:
    response = await client.delete(f"/api/v1/events/{uuid.uuid4()}")
    assert response.status_code == 401
