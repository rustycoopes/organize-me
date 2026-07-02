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

import os

# Must run before any app module (in particular app.auth.backend) is imported by a test module,
# so the cookie transport is built with cookie_secure=False. httpx isn't a browser and doesn't
# get the localhost-is-a-secure-context exception, so a Secure cookie set by /auth/login would
# never be resent by the test client on the next request.
os.environ.setdefault("COOKIE_SECURE", "false")

from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
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


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """httpx client for endpoint tests, wired to the same rolled-back db_session.

    Overrides the app's get_db dependency rather than letting request handlers
    build sessions off app.db.session's process-wide singleton engine: that engine
    binds asyncpg connections to the event loop that first created it, which breaks
    across pytest-asyncio's per-test event loops (see tests/conftest.py::db_session's
    own dedicated-engine-per-test docstring for the same underlying issue).
    """
    from app.db.session import get_db
    from app.main import app

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.clear()
