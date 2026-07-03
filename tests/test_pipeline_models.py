"""Model tests for the Slice 4.0 pipeline tables (issue #51).

Run inside the rolled-back db_session fixture against the QA DB, so nothing persists. Cover the
column defaults, JSONB round-trips, and the events duplicate-detection UNIQUE constraint (including
that it is scoped per user).
"""

import uuid
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Event,
    ProcessingRun,
    ProcessingRunStatus,
    ProcessingStep,
    ProcessingStepStatus,
    User,
)


async def _make_user(session: AsyncSession) -> User:
    user = User(email=f"pipeline-{uuid.uuid4().hex}@example.com", hashed_password="not-a-real-hash")
    session.add(user)
    await session.flush()
    return user


async def _make_run(session: AsyncSession, user: User) -> ProcessingRun:
    run = ProcessingRun(
        user_id=user.id, filename="chat.txt", status=ProcessingRunStatus.PENDING
    )
    session.add(run)
    await session.flush()
    return run


def _event(user: User, run: ProcessingRun, **overrides: object) -> Event:
    fields: dict[str, object] = {
        "user_id": user.id,
        "run_id": run.id,
        "type": "Medical",
        "description": "Christine to take Oliver to the dentist.",
        "resolved_date": "Saturday 6 June 2026",
        "raw_date_text": "Saturday",
        "agreed_by": [],
    }
    fields.update(overrides)
    return Event(**fields)


async def test_processing_run_persists_with_defaults(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    run = ProcessingRun(
        user_id=user.id, filename="export.zip", status=ProcessingRunStatus.IN_PROGRESS
    )
    db_session.add(run)
    await db_session.flush()

    stored = await db_session.scalar(select(ProcessingRun).where(ProcessingRun.id == run.id))
    assert stored is not None
    assert stored.status == ProcessingRunStatus.IN_PROGRESS
    assert stored.events_extracted_count == 0  # server default
    assert stored.started_at is None
    assert stored.created_at is not None


async def test_processing_step_defaults_log_lines_to_empty_list(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    run = await _make_run(db_session, user)
    step = ProcessingStep(
        run_id=run.id,
        step_number=1,
        step_name="File Received",
        status=ProcessingStepStatus.SUCCESS,
    )
    db_session.add(step)
    await db_session.flush()

    stored = await db_session.scalar(select(ProcessingStep).where(ProcessingStep.id == step.id))
    assert stored is not None
    assert stored.log_lines == []
    assert stored.status == ProcessingStepStatus.SUCCESS


async def test_event_round_trips_earliest_date_and_agreed_by(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    run = await _make_run(db_session, user)
    event = _event(
        user,
        run,
        resolved_date_earliest=date(2026, 6, 6),
        agreed_by=["Russ Cooper", "Christine Cooper"],
    )
    db_session.add(event)
    await db_session.flush()

    stored = await db_session.scalar(select(Event).where(Event.id == event.id))
    assert stored is not None
    assert stored.resolved_date_earliest == date(2026, 6, 6)
    assert stored.agreed_by == ["Russ Cooper", "Christine Cooper"]


async def test_duplicate_event_for_a_user_violates_the_unique_constraint(
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session)
    run = await _make_run(db_session, user)
    db_session.add(_event(user, run))
    await db_session.flush()

    # Same user + description + resolved_date -> duplicate, rejected by the UNIQUE constraint.
    db_session.add(_event(user, run))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_same_event_for_two_different_users_is_allowed(db_session: AsyncSession) -> None:
    user_a = await _make_user(db_session)
    user_b = await _make_user(db_session)
    run_a = await _make_run(db_session, user_a)
    run_b = await _make_run(db_session, user_b)

    db_session.add(_event(user_a, run_a))
    await db_session.flush()
    # Identical wording/date but a different user -> allowed (uniqueness is scoped per user).
    db_session.add(_event(user_b, run_b))
    await db_session.flush()

    count = len(
        (await db_session.scalars(select(Event).where(Event.run_id.in_([run_a.id, run_b.id])))).all()
    )
    assert count == 2
