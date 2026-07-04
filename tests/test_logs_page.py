"""Tests for the Processing History logs page and API endpoint (Slice 6.1, #83)."""

import uuid
from datetime import datetime, timezone

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.processing_run import ProcessingRun, ProcessingRunStatus


def unique_email() -> str:
    return f"logs-page-{uuid.uuid4().hex}@example.com"


async def _register_and_login(client: AsyncClient) -> uuid.UUID:
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})
    me = await client.get("/api/v1/users/me")
    return uuid.UUID(me.json()["id"])


async def _make_run(
    db: AsyncSession,
    user_id: uuid.UUID,
    filename: str = "chat.txt",
    status: ProcessingRunStatus = ProcessingRunStatus.SUCCESS,
    events_count: int = 0,
) -> ProcessingRun:
    run = ProcessingRun(
        user_id=user_id,
        filename=filename,
        status=status,
        events_extracted_count=events_count,
        created_at=datetime.now(timezone.utc),
    )
    db.add(run)
    await db.flush()
    return run


async def test_logs_redirects_anonymous_visitor_to_login(client: AsyncClient) -> None:
    response = await client.get("/logs")

    assert response.status_code in (302, 303, 307)
    assert response.headers["location"] == "/login"


async def test_logs_shows_empty_state_with_no_runs(client: AsyncClient) -> None:
    await _register_and_login(client)

    response = await client.get("/logs")

    assert response.status_code == 200
    assert "No processing runs yet" in response.text


async def test_logs_renders_run_row_with_all_columns(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(
        db_session,
        user_id,
        filename="test_file.txt",
        status=ProcessingRunStatus.SUCCESS,
        events_count=5,
    )

    response = await client.get("/logs")

    assert response.status_code == 200
    body = response.text
    assert "test_file.txt" in body
    assert "success" in body
    assert "5" in body
    assert f"/processing-runs/{run.id}" in body


async def test_logs_paginates_across_multiple_pages(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    for i in range(55):
        await _make_run(db_session, user_id, filename=f"file_{i}.txt")

    first_page = await client.get("/logs")
    second_page = await client.get("/logs", params={"page": 2})

    assert "Page 1 of 2" in first_page.text
    assert "Next" in first_page.text
    assert "Page 2 of 2" in second_page.text
    assert "Previous" in second_page.text


async def test_logs_shows_total_run_count(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    for i in range(3):
        await _make_run(db_session, user_id)

    response = await client.get("/logs")

    assert "3 total processing runs" in response.text


async def test_logs_redirects_out_of_range_page_to_last_valid_page(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    for i in range(3):
        await _make_run(db_session, user_id)

    # Only 1 page exists (3 runs, 50/page); page=5 is out of range.
    response = await client.get("/logs", params={"page": 5})

    assert response.status_code in (302, 303, 307)
    assert response.headers["location"] == "/logs?page=1"


async def test_logs_does_not_redirect_when_there_are_zero_runs(
    client: AsyncClient,
) -> None:
    await _register_and_login(client)

    # No runs at all: an out-of-range page must not redirect.
    response = await client.get("/logs", params={"page": 5})

    assert response.status_code == 200
    assert "No processing runs yet" in response.text


async def test_api_processing_runs_returns_authenticated_user_runs_only(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user1_id = await _register_and_login(client)
    await _make_run(db_session, user1_id, filename="user1_file.txt")

    # Check that user1 sees their own run.
    response = await client.get("/api/v1/processing-runs")
    body = response.json()
    assert response.status_code == 200
    assert body["total"] == 1
    assert len(body["runs"]) == 1
    assert body["runs"][0]["filename"] == "user1_file.txt"

    # Create a second user with a run.
    email = unique_email()
    password = "test-password"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})
    user2_id = uuid.UUID((await client.get("/api/v1/users/me")).json()["id"])
    db_session.expunge_all()
    await _make_run(db_session, user2_id, filename="user2_file.txt")

    # User2 should only see their own run (not user1's).
    response = await client.get("/api/v1/processing-runs")
    body = response.json()
    assert response.status_code == 200
    assert body["total"] == 1
    assert len(body["runs"]) == 1
    assert body["runs"][0]["filename"] == "user2_file.txt"


async def test_api_processing_runs_paginates_at_50_per_page(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    for i in range(55):
        await _make_run(db_session, user_id, filename=f"file_{i}.txt")

    first_page = await client.get("/api/v1/processing-runs", params={"page": 1})
    second_page = await client.get("/api/v1/processing-runs", params={"page": 2})

    assert first_page.status_code == 200
    assert second_page.status_code == 200

    first_body = first_page.json()
    second_body = second_page.json()

    assert len(first_body["runs"]) == 50
    assert len(second_body["runs"]) == 5
    assert first_body["total"] == 55
    assert first_body["page_size"] == 50


async def test_api_processing_runs_ordered_newest_first(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    for i in range(3):
        await _make_run(db_session, user_id, filename=f"file_{i}.txt")

    response = await client.get("/api/v1/processing-runs")
    body = response.json()

    assert response.status_code == 200
    # Runs should be newest first (reverse of creation order).
    assert body["runs"][0]["filename"] == "file_2.txt"
    assert body["runs"][1]["filename"] == "file_1.txt"
    assert body["runs"][2]["filename"] == "file_0.txt"


async def test_api_processing_runs_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/processing-runs")

    assert response.status_code in (401, 403)


async def test_logs_shows_run_status_badge_with_correct_color(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    await _make_run(db_session, user_id, status=ProcessingRunStatus.SUCCESS)
    await _make_run(db_session, user_id, status=ProcessingRunStatus.FAILED)
    await _make_run(db_session, user_id, status=ProcessingRunStatus.IN_PROGRESS)

    response = await client.get("/logs")

    body = response.text
    assert "badge-success" in body
    assert "badge-error" in body
    assert "badge-warning" in body
