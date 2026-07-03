"""Integration tests for the 7-step processing pipeline (#52).

Drives ``run_pipeline`` directly (awaited) with a ``FakeStorageProvider`` + fake Gemini + fake
notifier, against the rolled-back QA ``db_session`` fixture, and asserts events land in the DB and
the run/steps/file-movement/notification all reflect the outcome. This is the stubbed integration
test the Slice 4 spec calls for (replacing the original "Celery ALWAYS_EAGER" wording); the
real-Gemini end-to-end path is in test_pipeline_e2e_gemini.py and is skipped without a key.
"""

import io
import json
import uuid
import zipfile
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event
from app.models.processing_run import ProcessingRun, ProcessingRunStatus
from app.models.processing_step import ProcessingStep, ProcessingStepStatus
from app.models.user import User
from app.services.llm.gemini import FakeGeminiClient, GeminiError
from app.services.notifications.pipeline import FakeNotificationSender, NotificationOutcome
from app.services.pipeline.runner import run_pipeline
from app.services.storage.base import FileDestination, RemoteFile
from app.services.storage.fake import FakeStorageProvider

_EXAMPLE_OUTPUT = (
    Path(__file__).resolve().parents[1] / "examples" / "example.lmmoutput.txt"
).read_text(encoding="utf-8")

# The count of distinct (description, resolved_date) pairs in the example payload - what the
# deduplicating save should land on a first, empty-DB run.
_EXPECTED_NEW_EVENTS = len(
    {(e["description"], e["resolved_date"]) for e in json.loads(_EXAMPLE_OUTPUT)}
)


async def _make_user(session: AsyncSession) -> User:
    user = User(email=f"pipeline-{uuid.uuid4().hex}@example.com", hashed_password="x")
    session.add(user)
    await session.flush()
    return user


async def _make_run(session: AsyncSession, user: User, filename: str) -> ProcessingRun:
    run = ProcessingRun(
        user_id=user.id, filename=filename, status=ProcessingRunStatus.PENDING
    )
    session.add(run)
    await session.flush()
    return run


async def _steps(session: AsyncSession, run_id: uuid.UUID) -> list[ProcessingStep]:
    result = await session.scalars(
        select(ProcessingStep)
        .where(ProcessingStep.run_id == run_id)
        .order_by(ProcessingStep.step_number)
    )
    return list(result.all())


async def _events(session: AsyncSession, user_id: uuid.UUID) -> list[Event]:
    result = await session.scalars(select(Event).where(Event.user_id == user_id))
    return list(result.all())


async def test_txt_upload_runs_all_steps_and_events_land_in_db(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    run = await _make_run(db_session, user, "chat.txt")
    storage = FakeStorageProvider()
    remote_file = await storage.upload_file("chat.txt", b"5/30/26, 10:00 - Russ: hi")
    notifier = FakeNotificationSender()

    await run_pipeline(
        db_session,
        run=run,
        user_id=user.id,
        remote_file=remote_file,
        storage=storage,
        gemini=FakeGeminiClient(_EXAMPLE_OUTPUT),
        notifier=notifier,
        prompt_text="extract events",
    )

    assert run.status == ProcessingRunStatus.SUCCESS
    assert run.events_extracted_count == _EXPECTED_NEW_EVENTS
    assert len(await _events(db_session, user.id)) == _EXPECTED_NEW_EVENTS

    steps = await _steps(db_session, run.id)
    assert [s.step_number for s in steps] == [1, 2, 3, 4, 5, 6, 7]
    # Extract is skipped for a .txt; every other step succeeds.
    assert steps[1].status == ProcessingStepStatus.SKIPPED
    assert all(
        s.status == ProcessingStepStatus.SUCCESS for i, s in enumerate(steps) if i != 1
    )

    # File moved to processed/, and a single success notification fired.
    assert storage.moved[remote_file.id] == FileDestination.PROCESSED
    assert len(notifier.sent) == 1
    assert notifier.sent[0].outcome == NotificationOutcome.SUCCESS
    assert notifier.sent[0].new_event_count == _EXPECTED_NEW_EVENTS


async def test_multi_date_event_stores_earliest_date(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    run = await _make_run(db_session, user, "chat.txt")
    storage = FakeStorageProvider()
    remote_file = await storage.upload_file("chat.txt", b"data")

    await run_pipeline(
        db_session,
        run=run,
        user_id=user.id,
        remote_file=remote_file,
        storage=storage,
        gemini=FakeGeminiClient(_EXAMPLE_OUTPUT),
        notifier=FakeNotificationSender(),
        prompt_text="extract events",
    )

    # "Sunday 7 June 2026, Monday 8 June 2026" -> earliest is 2026-06-07.
    multi = await db_session.scalar(
        select(Event).where(
            Event.user_id == user.id,
            Event.resolved_date == "Sunday 7 June 2026, Monday 8 June 2026",
        )
    )
    assert multi is not None
    assert multi.resolved_date_earliest == date(2026, 6, 7)


async def test_zip_upload_is_unzipped_at_extract_step(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    run = await _make_run(db_session, user, "export.zip")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("_chat.txt", "5/30/26, 10:00 - Russ: hi")
    storage = FakeStorageProvider()
    remote_file = await storage.upload_file("export.zip", buffer.getvalue())

    await run_pipeline(
        db_session,
        run=run,
        user_id=user.id,
        remote_file=remote_file,
        storage=storage,
        gemini=FakeGeminiClient(_EXAMPLE_OUTPUT),
        notifier=FakeNotificationSender(),
        prompt_text="extract events",
    )

    steps = await _steps(db_session, run.id)
    assert steps[1].status == ProcessingStepStatus.SUCCESS  # Extract ran (not skipped) for a .zip
    assert run.status == ProcessingRunStatus.SUCCESS
    assert len(await _events(db_session, user.id)) == _EXPECTED_NEW_EVENTS


async def test_csv_upload_skips_extract(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    run = await _make_run(db_session, user, "chat.csv")
    storage = FakeStorageProvider()
    remote_file = await storage.upload_file("chat.csv", b"5/30/26, 10:00 - Russ: hi")

    await run_pipeline(
        db_session,
        run=run,
        user_id=user.id,
        remote_file=remote_file,
        storage=storage,
        gemini=FakeGeminiClient(_EXAMPLE_OUTPUT),
        notifier=FakeNotificationSender(),
        prompt_text="extract events",
    )

    steps = await _steps(db_session, run.id)
    assert steps[1].status == ProcessingStepStatus.SKIPPED
    assert run.status == ProcessingRunStatus.SUCCESS


async def test_duplicate_events_are_skipped(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    run = await _make_run(db_session, user, "chat.txt")
    # Pre-insert one event that also appears in the payload, so it should be skipped as a duplicate.
    first = json.loads(_EXAMPLE_OUTPUT)[0]
    db_session.add(
        Event(
            user_id=user.id,
            run_id=run.id,
            type=first["type"],
            description=first["description"],
            resolved_date=first["resolved_date"],
            raw_date_text=first.get("raw_date_text", ""),
            agreed_by=first.get("agreed_by", []),
        )
    )
    await db_session.flush()
    storage = FakeStorageProvider()
    remote_file = await storage.upload_file("chat.txt", b"data")

    await run_pipeline(
        db_session,
        run=run,
        user_id=user.id,
        remote_file=remote_file,
        storage=storage,
        gemini=FakeGeminiClient(_EXAMPLE_OUTPUT),
        notifier=FakeNotificationSender(),
        prompt_text="extract events",
    )

    assert run.status == ProcessingRunStatus.SUCCESS
    assert run.events_extracted_count == _EXPECTED_NEW_EVENTS - 1
    # Total rows = the pre-seeded one + the newly saved ones, with no UNIQUE violation.
    assert len(await _events(db_session, user.id)) == _EXPECTED_NEW_EVENTS


async def test_zero_new_events_is_a_success_with_no_new_events_notice(
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session)
    run = await _make_run(db_session, user, "chat.txt")
    payload = json.dumps(
        [
            {
                "type": "Medical",
                "description": "Dentist for Oliver.",
                "resolved_date": "Saturday 6 June 2026",
                "raw_date_text": "Saturday",
                "agreed_by": ["Russ"],
            }
        ]
    )
    # Pre-seed the only event the LLM will "return", so the run finds nothing new.
    db_session.add(
        Event(
            user_id=user.id,
            run_id=run.id,
            type="Medical",
            description="Dentist for Oliver.",
            resolved_date="Saturday 6 June 2026",
            raw_date_text="Saturday",
            agreed_by=["Russ"],
        )
    )
    await db_session.flush()
    storage = FakeStorageProvider()
    remote_file = await storage.upload_file("chat.txt", b"data")
    notifier = FakeNotificationSender()

    await run_pipeline(
        db_session,
        run=run,
        user_id=user.id,
        remote_file=remote_file,
        storage=storage,
        gemini=FakeGeminiClient(payload),
        notifier=notifier,
        prompt_text="extract events",
    )

    assert run.status == ProcessingRunStatus.SUCCESS
    assert run.events_extracted_count == 0
    assert storage.moved[remote_file.id] == FileDestination.PROCESSED
    assert notifier.sent[0].outcome == NotificationOutcome.NO_NEW_EVENTS


class _RaisingGemini:
    """A Gemini client that always fails, to exercise the fatal-error path."""

    async def extract(self, *, prompt: str, conversation: str) -> str:
        raise GeminiError("simulated Gemini outage")


async def test_gemini_failure_fails_run_and_moves_file_to_failed(
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session)
    run = await _make_run(db_session, user, "chat.txt")
    storage = FakeStorageProvider()
    remote_file = await storage.upload_file("chat.txt", b"data")
    notifier = FakeNotificationSender()

    await run_pipeline(
        db_session,
        run=run,
        user_id=user.id,
        remote_file=remote_file,
        storage=storage,
        gemini=_RaisingGemini(),
        notifier=notifier,
        prompt_text="extract events",
    )

    assert run.status == ProcessingRunStatus.FAILED
    assert len(await _events(db_session, user.id)) == 0
    steps = await _steps(db_session, run.id)
    gemini_step = next(s for s in steps if s.step_number == 4)
    assert gemini_step.status == ProcessingStepStatus.FAILED
    assert any("failed" in line.lower() for line in gemini_step.log_lines)
    # File went to failed/, and the user still got a failure notification (step 7).
    assert storage.moved[remote_file.id] == FileDestination.FAILED
    assert notifier.sent[-1].outcome == NotificationOutcome.FAILED


async def test_unparseable_llm_response_fails_run(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    run = await _make_run(db_session, user, "chat.txt")
    storage = FakeStorageProvider()
    remote_file = await storage.upload_file("chat.txt", b"data")
    notifier = FakeNotificationSender()

    await run_pipeline(
        db_session,
        run=run,
        user_id=user.id,
        remote_file=remote_file,
        storage=storage,
        gemini=FakeGeminiClient("this is not JSON at all"),
        notifier=notifier,
        prompt_text="extract events",
    )

    assert run.status == ProcessingRunStatus.FAILED
    steps = await _steps(db_session, run.id)
    parse_step = next(s for s in steps if s.step_number == 5)
    assert parse_step.status == ProcessingStepStatus.FAILED
    assert storage.moved[remote_file.id] == FileDestination.FAILED
    assert notifier.sent[-1].outcome == NotificationOutcome.FAILED


async def test_markdown_fenced_json_is_parsed(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    run = await _make_run(db_session, user, "chat.txt")
    storage = FakeStorageProvider()
    remote_file = await storage.upload_file("chat.txt", b"data")
    fenced = f"```json\n{_EXAMPLE_OUTPUT}\n```"

    await run_pipeline(
        db_session,
        run=run,
        user_id=user.id,
        remote_file=remote_file,
        storage=storage,
        gemini=FakeGeminiClient(fenced),
        notifier=FakeNotificationSender(),
        prompt_text="extract events",
    )

    assert run.status == ProcessingRunStatus.SUCCESS
    assert run.events_extracted_count == _EXPECTED_NEW_EVENTS
