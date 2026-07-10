"""Tests for GET/DELETE /api/v1/events (#54).

Run against the QA DB inside the rolled-back db_session fixture (see conftest), so nothing
persists. Auth is a real register + cookie login through the app, matching other endpoint tests.
"""

import uuid
from datetime import date, timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event
from app.models.processing_run import ProcessingRun, ProcessingRunStatus
from app.models.user import User


def unique_email() -> str:
    return f"events-api-{uuid.uuid4().hex}@example.com"


async def _register_and_login(client: AsyncClient) -> uuid.UUID:
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})
    me = await client.get("/api/v1/users/me")
    return uuid.UUID(me.json()["id"])


async def _make_run(db: AsyncSession, user_id: uuid.UUID) -> ProcessingRun:
    run = ProcessingRun(user_id=user_id, filename="chat.txt", status=ProcessingRunStatus.SUCCESS)
    db.add(run)
    await db.flush()
    return run


def _event(user_id: uuid.UUID, run_id: uuid.UUID, **overrides: object) -> Event:
    fields: dict[str, object] = {
        "user_id": user_id,
        "run_id": run_id,
        "type": "Medical",
        "description": "Dentist appointment",
        "resolved_date": "Saturday 6 June 2026",
        "resolved_date_earliest": date(2026, 6, 6),
        "raw_date_text": "Saturday",
        "agreed_by": ["Russ"],
    }
    fields.update(overrides)
    return Event(**fields)


async def test_get_events_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/events")
    assert response.status_code == 401


async def test_get_events_returns_only_the_requesting_users_events(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    db_session.add(_event(user_id, run.id, description="Mine", resolved_date="1 Jan"))

    other_user = User(email=unique_email(), hashed_password="x")
    db_session.add(other_user)
    await db_session.flush()
    other_run = await _make_run(db_session, other_user.id)
    db_session.add(_event(other_user.id, other_run.id, description="Not mine", resolved_date="2 Jan"))
    await db_session.flush()

    response = await client.get("/api/v1/events")

    assert response.status_code == 200
    body = response.json()
    descriptions = [e["description"] for e in body["events"]]
    assert "Mine" in descriptions
    assert "Not mine" not in descriptions


async def test_get_events_default_sort_is_newest_resolved_date_first(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    db_session.add(
        _event(
            user_id, run.id, description="Earlier",
            resolved_date_earliest=date(2026, 6, 1), resolved_date="1 June",
        )
    )
    db_session.add(
        _event(
            user_id, run.id, description="Later",
            resolved_date_earliest=date(2026, 6, 20), resolved_date="20 June",
        )
    )
    await db_session.flush()

    response = await client.get("/api/v1/events")

    descriptions = [e["description"] for e in response.json()["events"]]
    assert descriptions.index("Later") < descriptions.index("Earlier")


async def test_get_events_unresolved_dates_sort_last(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    db_session.add(
        _event(
            user_id, run.id, description="Has date",
            resolved_date_earliest=date(2026, 6, 1), resolved_date="1 June",
        )
    )
    db_session.add(
        _event(
            user_id, run.id, description="TBC",
            resolved_date_earliest=None, resolved_date="TBC",
        )
    )
    await db_session.flush()

    response = await client.get("/api/v1/events")

    descriptions = [e["description"] for e in response.json()["events"]]
    assert descriptions[-1] == "TBC"


async def test_get_events_paginates_at_50_per_page(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    for i in range(60):
        db_session.add(
            _event(
                user_id, run.id,
                description=f"Event {i}",
                resolved_date=f"Date {i}",
                resolved_date_earliest=date(2026, 1, 1) + timedelta(days=i),
            )
        )
    await db_session.flush()

    first_page = await client.get("/api/v1/events")
    second_page = await client.get("/api/v1/events", params={"page": 2})

    assert first_page.status_code == 200
    body1 = first_page.json()
    assert len(body1["events"]) == 50
    assert body1["total"] == 60
    assert body1["page"] == 1

    body2 = second_page.json()
    assert len(body2["events"]) == 10
    assert body2["page"] == 2


async def test_events_include_calendar_and_tasks_urls(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    db_session.add(_event(user_id, run.id))
    await db_session.flush()

    response = await client.get("/api/v1/events")

    event = response.json()["events"][0]
    assert event["calendar_url"].startswith("https://calendar.google.com/")
    assert event["tasks_url"].startswith("https://tasks.google.com/")


async def test_events_with_no_resolved_date_have_null_links(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    db_session.add(
        _event(
            user_id, run.id, description="TBC event",
            resolved_date="TBC", resolved_date_earliest=None,
        )
    )
    await db_session.flush()

    response = await client.get("/api/v1/events")

    event = response.json()["events"][0]
    assert event["calendar_url"] is None
    assert event["tasks_url"] is None


async def test_delete_event_removes_it(client: AsyncClient, db_session: AsyncSession) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    event = _event(user_id, run.id)
    db_session.add(event)
    await db_session.flush()
    event_id = event.id

    response = await client.delete(f"/api/v1/events/{event_id}")

    assert response.status_code == 204
    remaining = await db_session.scalar(select(Event).where(Event.id == event_id))
    assert remaining is None


async def test_delete_event_requires_authentication(client: AsyncClient) -> None:
    response = await client.delete(f"/api/v1/events/{uuid.uuid4()}")
    assert response.status_code == 401


async def test_delete_nonexistent_event_returns_404(client: AsyncClient) -> None:
    await _register_and_login(client)

    response = await client.delete(f"/api/v1/events/{uuid.uuid4()}")

    assert response.status_code == 404


async def test_delete_another_users_event_returns_404_and_does_not_delete(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _register_and_login(client)  # the authenticated caller

    other_user = User(email=unique_email(), hashed_password="x")
    db_session.add(other_user)
    await db_session.flush()
    other_run = await _make_run(db_session, other_user.id)
    other_event = _event(other_user.id, other_run.id)
    db_session.add(other_event)
    await db_session.flush()
    other_event_id = other_event.id

    response = await client.delete(f"/api/v1/events/{other_event_id}")

    assert response.status_code == 404
    still_there = await db_session.scalar(select(Event).where(Event.id == other_event_id))
    assert still_there is not None


# --- Filters, sort, search (Slice 5.2, #55) ---------------------------------------------------


async def test_get_events_filters_by_type(client: AsyncClient, db_session: AsyncSession) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    db_session.add(_event(user_id, run.id, type="Medical", description="Dentist", resolved_date="1 Jan"))
    db_session.add(_event(user_id, run.id, type="School", description="Parents evening", resolved_date="2 Jan"))
    await db_session.flush()

    response = await client.get("/api/v1/events", params={"type": "School"})

    descriptions = [e["description"] for e in response.json()["events"]]
    assert descriptions == ["Parents evening"]


async def test_get_events_filters_by_date_range(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    db_session.add(
        _event(
            user_id, run.id, description="Too early",
            resolved_date_earliest=date(2026, 1, 1), resolved_date="1 Jan",
        )
    )
    db_session.add(
        _event(
            user_id, run.id, description="In range",
            resolved_date_earliest=date(2026, 6, 15), resolved_date="15 June",
        )
    )
    db_session.add(
        _event(
            user_id, run.id, description="Too late",
            resolved_date_earliest=date(2026, 12, 31), resolved_date="31 Dec",
        )
    )
    await db_session.flush()

    response = await client.get(
        "/api/v1/events", params={"date_from": "2026-06-01", "date_to": "2026-06-30"}
    )

    descriptions = [e["description"] for e in response.json()["events"]]
    assert descriptions == ["In range"]


async def test_get_events_free_text_search_matches_description(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    db_session.add(_event(user_id, run.id, description="Dentist appointment", resolved_date="1 Jan"))
    db_session.add(_event(user_id, run.id, description="School trip", resolved_date="2 Jan"))
    await db_session.flush()

    response = await client.get("/api/v1/events", params={"q": "dentist"})

    descriptions = [e["description"] for e in response.json()["events"]]
    assert descriptions == ["Dentist appointment"]


async def test_get_events_free_text_search_matches_raw_date_text(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    db_session.add(
        _event(user_id, run.id, description="Dentist", resolved_date="1 Jan", raw_date_text="Saturday morning")
    )
    db_session.add(
        _event(user_id, run.id, description="School trip", resolved_date="2 Jan", raw_date_text="next Tuesday")
    )
    await db_session.flush()

    response = await client.get("/api/v1/events", params={"q": "Saturday"})

    descriptions = [e["description"] for e in response.json()["events"]]
    assert descriptions == ["Dentist"]


async def test_get_events_sort_asc_returns_oldest_first(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    db_session.add(
        _event(
            user_id, run.id, description="Earlier",
            resolved_date_earliest=date(2026, 6, 1), resolved_date="1 June",
        )
    )
    db_session.add(
        _event(
            user_id, run.id, description="Later",
            resolved_date_earliest=date(2026, 6, 20), resolved_date="20 June",
        )
    )
    await db_session.flush()

    response = await client.get("/api/v1/events", params={"sort": "asc"})

    descriptions = [e["description"] for e in response.json()["events"]]
    assert descriptions.index("Earlier") < descriptions.index("Later")


async def test_get_events_sort_asc_still_sorts_unresolved_dates_last(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    db_session.add(
        _event(
            user_id, run.id, description="Has date",
            resolved_date_earliest=date(2026, 6, 1), resolved_date="1 June",
        )
    )
    db_session.add(
        _event(user_id, run.id, description="TBC", resolved_date_earliest=None, resolved_date="TBC")
    )
    await db_session.flush()

    response = await client.get("/api/v1/events", params={"sort": "asc"})

    descriptions = [e["description"] for e in response.json()["events"]]
    assert descriptions[-1] == "TBC"


async def test_get_events_filters_compose_with_pagination(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    for i in range(60):
        db_session.add(
            _event(
                user_id, run.id,
                type="Medical",
                description=f"Medical event {i}",
                resolved_date=f"Date {i}",
                resolved_date_earliest=date(2026, 1, 1) + timedelta(days=i),
            )
        )
    for i in range(5):
        db_session.add(
            _event(
                user_id, run.id,
                type="School",
                description=f"School event {i}",
                resolved_date=f"Date {i}",
                resolved_date_earliest=date(2027, 1, 1) + timedelta(days=i),
            )
        )
    await db_session.flush()

    first_page = await client.get("/api/v1/events", params={"type": "Medical"})
    second_page = await client.get("/api/v1/events", params={"type": "Medical", "page": 2})

    body1 = first_page.json()
    assert body1["total"] == 60
    assert len(body1["events"]) == 50
    assert all(e["type"] == "Medical" for e in body1["events"])

    body2 = second_page.json()
    assert len(body2["events"]) == 10
    assert all(e["type"] == "Medical" for e in body2["events"])


async def test_get_events_accepts_empty_date_filter_params(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """An untouched date picker submits "" (not an omitted param) via the HTMX-serialized filter
    form - the endpoint must treat that the same as no filter, not reject it with a 422."""
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    db_session.add(_event(user_id, run.id, description="Mine", resolved_date="1 Jan"))
    await db_session.flush()

    response = await client.get(
        "/api/v1/events", params={"date_from": "", "date_to": "", "type": "", "q": ""}
    )

    assert response.status_code == 200
    descriptions = [e["description"] for e in response.json()["events"]]
    assert "Mine" in descriptions


async def test_get_events_rejects_malformed_date_param_with_422(client: AsyncClient) -> None:
    await _register_and_login(client)

    response = await client.get("/api/v1/events", params={"date_from": "not-a-date"})

    assert response.status_code == 422


async def test_get_events_search_escapes_like_wildcards(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A literal "%" or "_" in the search box must be matched literally, not treated as a SQL
    LIKE wildcard - otherwise "%" would silently match every event regardless of description."""
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    db_session.add(_event(user_id, run.id, description="50% off tickets", resolved_date="1 Jan"))
    db_session.add(_event(user_id, run.id, description="Unrelated event", resolved_date="2 Jan"))
    await db_session.flush()

    response = await client.get("/api/v1/events", params={"q": "50%"})

    descriptions = [e["description"] for e in response.json()["events"]]
    assert descriptions == ["50% off tickets"]


async def test_get_events_free_text_search_matches_event_type(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Search should match the event type field."""
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    db_session.add(_event(user_id, run.id, type="Medical", description="Dentist", resolved_date="1 Jan"))
    db_session.add(_event(user_id, run.id, type="School", description="Class", resolved_date="2 Jan"))
    await db_session.flush()

    response = await client.get("/api/v1/events", params={"q": "medical"})

    descriptions = [e["description"] for e in response.json()["events"]]
    assert descriptions == ["Dentist"]


async def test_get_events_free_text_search_matches_agreed_by(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Search should match names in the agreed_by array."""
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    db_session.add(
        _event(
            user_id, run.id,
            description="Meeting with Alice",
            resolved_date="1 Jan",
            agreed_by=["Alice", "Bob"],
        )
    )
    db_session.add(
        _event(
            user_id, run.id,
            description="Meeting with Charlie",
            resolved_date="2 Jan",
            agreed_by=["Charlie"],
        )
    )
    await db_session.flush()

    response = await client.get("/api/v1/events", params={"q": "alice"})

    descriptions = [e["description"] for e in response.json()["events"]]
    assert descriptions == ["Meeting with Alice"]


# --- Reviewed flag + filter (#113) ------------------------------------------------------------


async def test_new_events_default_to_unreviewed(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    db_session.add(_event(user_id, run.id))
    await db_session.flush()

    response = await client.get("/api/v1/events")

    assert response.json()["events"][0]["reviewed"] is False


async def test_get_events_hides_reviewed_events_by_default(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    db_session.add(_event(user_id, run.id, description="Unreviewed", resolved_date="1 Jan"))
    db_session.add(
        _event(user_id, run.id, description="Reviewed", resolved_date="2 Jan", reviewed=True)
    )
    await db_session.flush()

    response = await client.get("/api/v1/events")

    descriptions = [e["description"] for e in response.json()["events"]]
    assert descriptions == ["Unreviewed"]


async def test_get_events_show_reviewed_true_returns_all(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    db_session.add(_event(user_id, run.id, description="Unreviewed", resolved_date="1 Jan"))
    db_session.add(
        _event(user_id, run.id, description="Reviewed", resolved_date="2 Jan", reviewed=True)
    )
    await db_session.flush()

    response = await client.get("/api/v1/events", params={"show_reviewed": "true"})

    descriptions = {e["description"] for e in response.json()["events"]}
    assert descriptions == {"Unreviewed", "Reviewed"}


async def test_get_events_reviewed_filter_composes_with_type_filter(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    db_session.add(
        _event(user_id, run.id, type="Medical", description="Reviewed medical", reviewed=True)
    )
    db_session.add(_event(user_id, run.id, type="Medical", description="Unreviewed medical"))
    db_session.add(_event(user_id, run.id, type="School", description="Unreviewed school"))
    await db_session.flush()

    response = await client.get("/api/v1/events", params={"type": "Medical"})

    descriptions = [e["description"] for e in response.json()["events"]]
    assert descriptions == ["Unreviewed medical"]


async def test_patch_event_marks_it_reviewed(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    event = _event(user_id, run.id)
    db_session.add(event)
    await db_session.flush()
    event_id = event.id

    response = await client.patch(f"/api/v1/events/{event_id}", json={"reviewed": True})

    assert response.status_code == 200
    assert response.json()["reviewed"] is True
    await db_session.refresh(event)
    assert event.reviewed is True


async def test_patch_event_can_unmark_reviewed(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    event = _event(user_id, run.id, reviewed=True)
    db_session.add(event)
    await db_session.flush()
    event_id = event.id

    response = await client.patch(f"/api/v1/events/{event_id}", json={"reviewed": False})

    assert response.status_code == 200
    assert response.json()["reviewed"] is False


async def test_patch_event_requires_authentication(client: AsyncClient) -> None:
    response = await client.patch(f"/api/v1/events/{uuid.uuid4()}", json={"reviewed": True})

    assert response.status_code == 401


async def test_patch_nonexistent_event_returns_404(client: AsyncClient) -> None:
    await _register_and_login(client)

    response = await client.patch(f"/api/v1/events/{uuid.uuid4()}", json={"reviewed": True})

    assert response.status_code == 404


async def test_patch_another_users_event_returns_404_and_does_not_update(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _register_and_login(client)

    other_user = User(email=unique_email(), hashed_password="x")
    db_session.add(other_user)
    await db_session.flush()
    other_run = await _make_run(db_session, other_user.id)
    other_event = _event(other_user.id, other_run.id)
    db_session.add(other_event)
    await db_session.flush()
    other_event_id = other_event.id

    response = await client.patch(f"/api/v1/events/{other_event_id}", json={"reviewed": True})

    assert response.status_code == 404
    await db_session.refresh(other_event)
    assert other_event.reviewed is False


async def test_get_events_multiple_filters_compose_with_and_logic(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """All filters should combine with AND logic - an event must match type AND date range AND search."""
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    # Matches type and date but not search
    db_session.add(
        _event(
            user_id, run.id, type="Medical", description="Dentist",
            resolved_date_earliest=date(2026, 6, 15), resolved_date="15 June",
        )
    )
    # Matches type and search but not date
    db_session.add(
        _event(
            user_id, run.id, type="Medical", description="Medical checkup",
            resolved_date_earliest=date(2026, 12, 15), resolved_date="15 Dec",
        )
    )
    # Matches date and search but not type
    db_session.add(
        _event(
            user_id, run.id, type="School", description="Medical lecture",
            resolved_date_earliest=date(2026, 6, 20), resolved_date="20 June",
        )
    )
    # Matches all: type=Medical, date in June, and search matches "checkup" in description
    db_session.add(
        _event(
            user_id, run.id, type="Medical", description="Checkup appointment",
            resolved_date_earliest=date(2026, 6, 10), resolved_date="10 June",
        )
    )
    await db_session.flush()

    response = await client.get(
        "/api/v1/events",
        params={
            "type": "Medical",
            "date_from": "2026-06-01",
            "date_to": "2026-06-30",
            "q": "checkup",
        },
    )

    descriptions = [e["description"] for e in response.json()["events"]]
    assert descriptions == ["Checkup appointment"]
