"""Shared pytest fixtures.

Tests run against the real Supabase QA database (no local Docker Postgres, per
the project's local-dev convention). Each test's writes are made inside a
SAVEPOINT nested in an outer transaction that is rolled back on teardown, so
nothing a test does is ever actually persisted to QA.

The fixture builds its own dedicated engine per test (rather than reusing
app.db.session's process-wide singleton) because asyncpg connections are bound
to the event loop that created them, and pytest-asyncio gives each test
function its own loop by default.
"""

from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.url import to_asyncpg_url


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        to_asyncpg_url(get_settings().database_url),
        connect_args={"statement_cache_size": 0},
    )
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            session_factory = async_sessionmaker(
                bind=connection,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            )
            async with session_factory() as session:
                yield session
            await transaction.rollback()
    finally:
        await engine.dispose()
