"""Tests for the Processing progress page (Slice 4.2, #53)."""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.processing_run import ProcessingRun, ProcessingRunStatus
from app.models.processing_step import ProcessingStep, ProcessingStepStatus


def unique_email() -> str:
    return f"proc-page-{uuid.uuid4().hex}@example.com"


async def _register_and_login(client: AsyncClient) -> uuid.UUID:
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})
    me = await client.get("/api/v1/users/me")
    return uuid.UUID(me.json()["id"])


async def test_processing_page_redirects_anonymous_visitor_to_login(client: AsyncClient) -> None:
    response = await client.get("/processing")

    assert response.status_code in (302, 303, 307)
    assert response.headers["location"] == "/login"


async def test_processing_page_shows_empty_state_when_no_runs(client: AsyncClient) -> None:
    await _register_and_login(client)

    response = await client.get("/processing")

    assert response.status_code == 200
    body = response.text
    assert "No processing runs yet" in body
    assert "/upload" in body
    # No SSE connection is opened when there's nothing to watch.
    assert "sse-connect" not in body


async def test_processing_page_renders_steps_and_sse_connection_for_a_run(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = ProcessingRun(
        user_id=user_id, filename="whatsapp.txt", status=ProcessingRunStatus.IN_PROGRESS
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

    response = await client.get(f"/processing?run={run.id}")

    assert response.status_code == 200
    body = response.text
    # HTMX + the SSE extension are loaded, and the page connects to this run's stream.
    assert "htmx.org@1.9.12" in body
    assert "ext/sse.js" in body
    assert f'sse-connect="/api/v1/processing-runs/{run.id}/sse"' in body
    assert 'sse-close="done"' in body
    # All 7 step indicators render, each a swap target.
    for n in range(1, 8):
        assert f'sse-swap="step-{n}"' in body
    assert "File Received" in body
    assert "Deduplicate &amp; Save" in body or "Deduplicate & Save" in body
    assert "whatsapp.txt" in body


async def test_processing_page_falls_back_to_latest_run_without_run_param(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = ProcessingRun(
        user_id=user_id, filename="latest.txt", status=ProcessingRunStatus.IN_PROGRESS
    )
    db_session.add(run)
    await db_session.flush()

    response = await client.get("/processing")

    assert response.status_code == 200
    assert "latest.txt" in response.text
    # A running run streams live, so its SSE connection is wired even without a ?run= param.
    assert f"/api/v1/processing-runs/{run.id}/sse" in response.text


async def test_processing_page_renders_a_finished_run_statically_without_sse(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = ProcessingRun(
        user_id=user_id, filename="done.txt", status=ProcessingRunStatus.SUCCESS
    )
    db_session.add(run)
    await db_session.flush()

    response = await client.get(f"/processing?run={run.id}")

    assert response.status_code == 200
    body = response.text
    # A terminal run shows its final state but opens no live stream (nothing left to watch).
    assert "done.txt" in body
    assert 'data-run-status="success"' in body
    assert "sse-connect" not in body
    assert "htmx.org" not in body


async def test_processing_page_tolerates_a_malformed_run_param(client: AsyncClient) -> None:
    await _register_and_login(client)

    # A malformed ?run= must not 422; it falls through to the latest-run fallback (here, none).
    response = await client.get("/processing?run=not-a-uuid")

    assert response.status_code == 200
    assert "No processing runs yet" in response.text


async def test_processing_page_ignores_a_run_owned_by_another_user(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    other_user_id = await _register_and_login(client)  # user B
    other_run = ProcessingRun(
        user_id=other_user_id, filename="secret.txt", status=ProcessingRunStatus.SUCCESS
    )
    db_session.add(other_run)
    await db_session.flush()
    await _register_and_login(client)  # now user A, who has no runs

    response = await client.get(f"/processing?run={other_run.id}")

    assert response.status_code == 200
    # A must not see B's run; with no runs of their own they get the empty state.
    assert "secret.txt" not in response.text
    assert "No processing runs yet" in response.text
