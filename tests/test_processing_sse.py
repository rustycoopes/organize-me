"""Tests for the live-progress SSE stream (Slice 4.2, #53).

Covers the ``stream_run_progress`` generator directly (terminal run -> step events + done) and the
``GET /api/v1/processing-runs/{id}/sse`` endpoint's auth + ownership gating.
"""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.processing_run import ProcessingRun, ProcessingRunStatus
from app.models.processing_step import ProcessingStep, ProcessingStepStatus
from app.services.pipeline.progress import stream_run_progress


def unique_email() -> str:
    return f"sse-{uuid.uuid4().hex}@example.com"


async def _register_and_login(client: AsyncClient) -> uuid.UUID:
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})
    me = await client.get("/api/v1/users/me")
    return uuid.UUID(me.json()["id"])


async def _seed_run(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    status: ProcessingRunStatus,
    step_statuses: dict[int, ProcessingStepStatus],
) -> ProcessingRun:
    run = ProcessingRun(user_id=user_id, filename="chat.txt", status=status)
    db.add(run)
    await db.flush()
    for number, step_status in step_statuses.items():
        db.add(
            ProcessingStep(
                run_id=run.id,
                step_number=number,
                step_name=f"Step {number}",
                status=step_status,
            )
        )
    await db.flush()
    return run


async def test_stream_emits_step_events_and_closes_for_a_terminal_run(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _seed_run(
        db_session,
        user_id,
        status=ProcessingRunStatus.SUCCESS,
        step_statuses={n: ProcessingStepStatus.SUCCESS for n in range(1, 8)},
    )

    events = [
        event
        async for event in stream_run_progress(
            db_session, run.id, poll_interval=0.01, max_seconds=1.0
        )
    ]

    kinds = [e["event"] for e in events]
    # One event per step, a run-status event, and a terminal done that closes the stream.
    assert kinds.count("done") == 1
    assert kinds[-1] == "done"
    for n in range(1, 8):
        assert f"step-{n}" in kinds
    assert "run-status" in kinds
    # The step fragments carry the live status the browser will read.
    step_event = next(e for e in events if e["event"] == "step-1")
    assert 'data-status="success"' in step_event["data"]


async def test_stream_reports_a_failed_run_as_terminal(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _seed_run(
        db_session,
        user_id,
        status=ProcessingRunStatus.FAILED,
        step_statuses={1: ProcessingStepStatus.SUCCESS, 4: ProcessingStepStatus.FAILED},
    )

    events = [
        event
        async for event in stream_run_progress(
            db_session, run.id, poll_interval=0.01, max_seconds=1.0
        )
    ]

    status_event = next(e for e in events if e["event"] == "run-status")
    assert 'data-run-status="failed"' in status_event["data"]
    assert events[-1]["event"] == "done"
    # Step 4 surfaces as failed for the highlighted indicator.
    step4 = next(e for e in events if e["event"] == "step-4")
    assert 'data-status="failed"' in step4["data"]


async def test_sse_endpoint_requires_authentication(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/processing-runs/{uuid.uuid4()}/sse")
    assert response.status_code == 401


async def test_sse_endpoint_hides_another_users_run(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    other_user_id = await _register_and_login(client)  # user B
    run = await _seed_run(
        db_session,
        other_user_id,
        status=ProcessingRunStatus.SUCCESS,
        step_statuses={1: ProcessingStepStatus.SUCCESS},
    )
    await _register_and_login(client)  # now logged in as user A

    response = await client.get(f"/api/v1/processing-runs/{run.id}/sse")

    assert response.status_code == 404


async def test_sse_endpoint_streams_owned_terminal_run(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _seed_run(
        db_session,
        user_id,
        status=ProcessingRunStatus.SUCCESS,
        step_statuses={n: ProcessingStepStatus.SUCCESS for n in range(1, 8)},
    )

    response = await client.get(f"/api/v1/processing-runs/{run.id}/sse")

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    body = response.text
    assert "event: done" in body
    assert 'data-status="success"' in body
