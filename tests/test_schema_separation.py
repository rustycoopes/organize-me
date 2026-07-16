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
    """R13 (#168) removed the Host's own ORM models for event_creator's tables (ProcessingRun,
    Event, etc. now live only in event-creator's codebase), so this boundary regression - a Host
    user delete must still cascade into event_creator's rows via the DB's own FK constraints - is
    exercised with raw SQL against those tables rather than the (now-removed) ORM classes."""
    user = User(
        email=f"cascade-{uuid.uuid4()}@example.com",
        hashed_password="not-a-real-hash",
    )
    db_session.add(user)
    await db_session.flush()

    run_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO event_creator.processing_runs (id, user_id, filename, status) "
            "VALUES (:id, :user_id, :filename, :status)"
        ).bindparams(id=run_id, user_id=user.id, filename="test.zip", status="success")
    )

    event_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO event_creator.events "
            "(id, user_id, run_id, type, description, resolved_date, raw_date_text) "
            "VALUES (:id, :user_id, :run_id, :type, :description, :resolved_date, :raw_date_text)"
        ).bindparams(
            id=event_id,
            user_id=user.id,
            run_id=run_id,
            type="Medical",
            description="Cascade test event",
            resolved_date="tomorrow",
            raw_date_text="tomorrow",
        )
    )
    await db_session.flush()

    await db_session.delete(user)
    await db_session.flush()

    result = await db_session.execute(
        text("SELECT 1 FROM event_creator.processing_runs WHERE id = :id").bindparams(id=run_id)
    )
    assert result.first() is None

    result = await db_session.execute(
        text("SELECT 1 FROM event_creator.events WHERE id = :id").bindparams(id=event_id)
    )
    assert result.first() is None


async def test_host_users_no_longer_has_moved_columns(db_session: AsyncSession) -> None:
    """Regression test (moved here from the now-deleted test_user_settings_model.py in R13 /
    #168): asserts `host.users` still doesn't have the notification/onboarding columns that were
    moved onto `event_creator.user_settings` back in #158 / Slice R2. This is a pure Host-schema
    assertion - it never imports the (event-creator-owned, now Host-removed) UserSettings model -
    so it belongs among the Host's own DB-schema regression tests rather than disappearing along
    with the rest of that file's now-redundant UserSettings model coverage."""
    result = await db_session.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'host' AND table_name = 'users'"
        )
    )
    columns = {row[0] for row in result.all()}
    assert columns.isdisjoint(
        {
            "notification_sms",
            "notification_email",
            "onboarding_storage_done",
            "onboarding_notifications_done",
            "onboarding_first_upload_done",
        }
    )
