"""Tests for the Processing run detail page and logs endpoints (Slice 6.2, #84)."""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.processing_run import ProcessingRun, ProcessingRunStatus
from app.models.processing_step import ProcessingStep, ProcessingStepStatus


def unique_email() -> str:
    return f"proc-detail-{uuid.uuid4().hex}@example.com"


async def _register_and_login(client: AsyncClient) -> uuid.UUID:
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})
    me = await client.get("/api/v1/users/me")
    return uuid.UUID(me.json()["id"])


async def test_processing_run_detail_page_requires_login(client: AsyncClient) -> None:
    run_id = uuid.uuid4()
    response = await client.get(f"/processing-runs/{run_id}")

    assert response.status_code in (302, 303, 307)
    assert response.headers["location"] == "/login"


async def test_processing_run_detail_page_404s_for_nonexistent_run(client: AsyncClient) -> None:
    await _register_and_login(client)
    run_id = uuid.uuid4()

    response = await client.get(f"/processing-runs/{run_id}")

    assert response.status_code == 404


async def test_processing_run_detail_page_404s_for_another_users_run(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    other_user_id = await _register_and_login(client)  # user B
    other_run = ProcessingRun(
        user_id=other_user_id,
        filename="secret.txt",
        status=ProcessingRunStatus.SUCCESS,
    )
    db_session.add(other_run)
    await db_session.flush()
    await _register_and_login(client)  # user A

    response = await client.get(f"/processing-runs/{other_run.id}")

    assert response.status_code == 404


async def test_processing_run_detail_page_renders_run_metadata_and_steps(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = ProcessingRun(
        user_id=user_id,
        filename="test.txt",
        status=ProcessingRunStatus.SUCCESS,
        events_extracted_count=42,
    )
    db_session.add(run)
    await db_session.flush()
    db_session.add(
        ProcessingStep(
            run_id=run.id,
            step_number=1,
            step_name="File Received",
            status=ProcessingStepStatus.SUCCESS,
        )
    )
    await db_session.flush()

    response = await client.get(f"/processing-runs/{run.id}")

    assert response.status_code == 200
    body = response.text
    assert "Run Detail" in body
    assert "test.txt" in body
    assert "42" in body
    assert "File Received" in body
    # All 7 step indicators should render
    assert "Deduplicate" in body or "deduplicate" in body.lower()


async def test_processing_run_logs_endpoint_returns_json(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = ProcessingRun(user_id=user_id, filename="test.txt", status=ProcessingRunStatus.SUCCESS)
    db_session.add(run)
    await db_session.flush()
    step = ProcessingStep(
        run_id=run.id,
        step_number=1,
        step_name="File Received",
        status=ProcessingStepStatus.SUCCESS,
        log_lines=["Line 1", "Line 2", "Line 3"],
    )
    db_session.add(step)
    await db_session.flush()

    response = await client.get(f"/api/v1/processing-runs/{run.id}/logs?step_number=1")

    assert response.status_code == 200
    data = response.json()
    assert data["step_number"] == 1
    assert data["step_name"] == "File Received"
    assert data["log_lines"] == ["Line 1", "Line 2", "Line 3"]
    assert data["page"] == 1
    assert data["page_size"] == 50
    assert data["total"] == 3


async def test_processing_run_logs_html_endpoint_returns_html_partial(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = ProcessingRun(user_id=user_id, filename="test.txt", status=ProcessingRunStatus.SUCCESS)
    db_session.add(run)
    await db_session.flush()
    step = ProcessingStep(
        run_id=run.id,
        step_number=1,
        step_name="File Received",
        status=ProcessingStepStatus.SUCCESS,
        log_lines=["Error: something went wrong", "Then recovered", "Finally done"],
    )
    db_session.add(step)
    await db_session.flush()

    response = await client.get(f"/api/html/processing-runs/{run.id}/logs?step_number=1")

    assert response.status_code == 200
    body = response.text
    assert "Error: something went wrong" in body
    assert "Then recovered" in body
    assert "Finally done" in body
    # Should include search form and pagination info
    assert "Filter logs" in body or "filter" in body.lower()


async def test_processing_run_logs_searches_log_lines(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = ProcessingRun(user_id=user_id, filename="test.txt", status=ProcessingRunStatus.SUCCESS)
    db_session.add(run)
    await db_session.flush()
    step = ProcessingStep(
        run_id=run.id,
        step_number=1,
        step_name="File Received",
        status=ProcessingStepStatus.SUCCESS,
        log_lines=["Starting process", "Parsing file", "Error: invalid format", "Retrying"],
    )
    db_session.add(step)
    await db_session.flush()

    response = await client.get(
        f"/api/v1/processing-runs/{run.id}/logs?step_number=1&search=error"
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["log_lines"]) == 1
    assert "Error: invalid format" in data["log_lines"]
    assert data["total"] == 1


async def test_processing_run_logs_paginates(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = ProcessingRun(user_id=user_id, filename="test.txt", status=ProcessingRunStatus.SUCCESS)
    db_session.add(run)
    await db_session.flush()
    # Create 75 log lines (1.5 pages)
    log_lines = [f"Line {i}" for i in range(1, 76)]
    step = ProcessingStep(
        run_id=run.id,
        step_number=1,
        step_name="File Received",
        status=ProcessingStepStatus.SUCCESS,
        log_lines=log_lines,
    )
    db_session.add(step)
    await db_session.flush()

    response = await client.get(f"/api/v1/processing-runs/{run.id}/logs?step_number=1&page=1")
    data = response.json()
    assert len(data["log_lines"]) == 50
    assert data["page"] == 1
    assert data["total"] == 75

    response = await client.get(f"/api/v1/processing-runs/{run.id}/logs?step_number=1&page=2")
    data = response.json()
    assert len(data["log_lines"]) == 25
    assert data["page"] == 2


async def test_processing_run_logs_endpoint_requires_login(client: AsyncClient) -> None:
    run_id = uuid.uuid4()
    response = await client.get(f"/api/v1/processing-runs/{run_id}/logs?step_number=1")

    assert response.status_code in (401, 403)


async def test_processing_run_logs_endpoint_404s_for_another_users_run(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    other_user_id = await _register_and_login(client)  # user B
    other_run = ProcessingRun(user_id=other_user_id, filename="secret.txt", status="success")
    db_session.add(other_run)
    await db_session.flush()
    await _register_and_login(client)  # user A

    response = await client.get(f"/api/v1/processing-runs/{other_run.id}/logs?step_number=1")

    assert response.status_code == 404


async def test_processing_run_logs_endpoint_404s_for_nonexistent_step(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = ProcessingRun(user_id=user_id, filename="test.txt", status=ProcessingRunStatus.SUCCESS)
    db_session.add(run)
    await db_session.flush()

    # Step 7 is valid per spec but doesn't exist in DB, should 404.
    response = await client.get(f"/api/v1/processing-runs/{run.id}/logs?step_number=7")

    assert response.status_code == 404


async def test_processing_run_detail_api_endpoint_returns_run_with_steps(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = ProcessingRun(
        user_id=user_id,
        filename="test.txt",
        status=ProcessingRunStatus.SUCCESS,
        events_extracted_count=5,
    )
    db_session.add(run)
    await db_session.flush()
    step1 = ProcessingStep(
        run_id=run.id,
        step_number=1,
        step_name="File Received",
        status=ProcessingStepStatus.SUCCESS,
    )
    step2 = ProcessingStep(
        run_id=run.id,
        step_number=2,
        step_name="Extract",
        status=ProcessingStepStatus.SUCCESS,
    )
    db_session.add_all([step1, step2])
    await db_session.flush()

    response = await client.get(f"/api/v1/processing-runs/{run.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(run.id)
    assert data["filename"] == "test.txt"
    assert data["status"] == "success"
    assert data["events_extracted_count"] == 5
    assert len(data["steps"]) == 2
    assert data["steps"][0]["step_number"] == 1
    assert data["steps"][0]["step_name"] == "File Received"
    assert data["steps"][1]["step_number"] == 2


async def test_processing_run_detail_api_endpoint_requires_login(client: AsyncClient) -> None:
    run_id = uuid.uuid4()
    response = await client.get(f"/api/v1/processing-runs/{run_id}")

    assert response.status_code in (401, 403)


async def test_processing_run_detail_api_endpoint_404s_for_another_users_run(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    other_user_id = await _register_and_login(client)  # user B
    other_run = ProcessingRun(
        user_id=other_user_id, filename="secret.txt", status=ProcessingRunStatus.SUCCESS
    )
    db_session.add(other_run)
    await db_session.flush()
    await _register_and_login(client)  # user A

    response = await client.get(f"/api/v1/processing-runs/{other_run.id}")

    assert response.status_code == 404
