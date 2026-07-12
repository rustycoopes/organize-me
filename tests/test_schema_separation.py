"""Slice R1 (#156): host/event_creator schema separation.

Assertions run against information_schema/pg_catalog rather than by connecting as host_app /
event_creator_app - those roles are NOLOGIN in this slice (not wired into the running app yet),
so a real connect-as-role test isn't possible. Privilege functions (has_table_privilege etc.)
report the same grants regardless of whether the role can log in.
"""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event
from app.models.processing_run import ProcessingRun, ProcessingRunStatus
from app.models.user import User

_HOST_TABLES = {"users", "oauth_accounts"}
_EVENT_CREATOR_TABLES = {
    "storage_configs",
    "llm_prompts",
    "processing_runs",
    "processing_steps",
    "events",
}


async def test_host_tables_live_in_host_schema(db_session: AsyncSession) -> None:
    result = await db_session.execute(
        text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'host'"
        )
    )
    assert _HOST_TABLES.issubset({row[0] for row in result.all()})


async def test_event_creator_tables_live_in_event_creator_schema(
    db_session: AsyncSession,
) -> None:
    result = await db_session.execute(
        text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'event_creator'"
        )
    )
    assert _EVENT_CREATOR_TABLES.issubset({row[0] for row in result.all()})


async def test_host_app_has_no_privileges_on_event_creator(db_session: AsyncSession) -> None:
    result = await db_session.execute(
        text("SELECT has_schema_privilege('host_app', 'event_creator', 'USAGE')")
    )
    assert result.scalar_one() is False

    for table in _EVENT_CREATOR_TABLES:
        result = await db_session.execute(
            text(
                "SELECT has_table_privilege('host_app', :table, 'SELECT')"
            ).bindparams(table=f"event_creator.{table}")
        )
        assert result.scalar_one() is False, table


async def test_event_creator_app_cannot_select_host_users(db_session: AsyncSession) -> None:
    result = await db_session.execute(
        text("SELECT has_table_privilege('event_creator_app', 'host.users', 'SELECT')")
    )
    assert result.scalar_one() is False


async def test_event_creator_app_has_references_only_on_host_users(
    db_session: AsyncSession,
) -> None:
    result = await db_session.execute(
        text(
            "SELECT has_table_privilege('event_creator_app', 'host.users', 'REFERENCES')"
        )
    )
    assert result.scalar_one() is True


async def test_event_creator_app_has_no_other_host_table_access(db_session: AsyncSession) -> None:
    result = await db_session.execute(
        text(
            "SELECT has_table_privilege('event_creator_app', 'host.oauth_accounts', 'SELECT')"
        )
    )
    assert result.scalar_one() is False


@pytest.mark.parametrize("role", ["host_app", "event_creator_app"])
async def test_roles_are_nologin(db_session: AsyncSession, role: str) -> None:
    result = await db_session.execute(
        text("SELECT rolcanlogin FROM pg_roles WHERE rolname = :role").bindparams(role=role)
    )
    assert result.scalar_one() is False


async def test_deleting_host_user_cascades_to_event_creator_rows(
    db_session: AsyncSession,
) -> None:
    user = User(
        email=f"cascade-{uuid.uuid4()}@example.com",
        hashed_password="not-a-real-hash",
    )
    db_session.add(user)
    await db_session.flush()

    run = ProcessingRun(
        user_id=user.id, filename="test.zip", status=ProcessingRunStatus.SUCCESS
    )
    db_session.add(run)
    await db_session.flush()

    event = Event(
        user_id=user.id,
        run_id=run.id,
        type="Medical",
        description="Cascade test event",
        resolved_date="tomorrow",
        raw_date_text="tomorrow",
    )
    db_session.add(event)
    await db_session.flush()

    await db_session.delete(user)
    await db_session.flush()

    result = await db_session.execute(
        text("SELECT 1 FROM event_creator.processing_runs WHERE id = :id").bindparams(id=run.id)
    )
    assert result.first() is None

    result = await db_session.execute(
        text("SELECT 1 FROM event_creator.events WHERE id = :id").bindparams(id=event.id)
    )
    assert result.first() is None
