from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.db.url import to_asyncpg_url


@lru_cache
def get_engine() -> AsyncEngine:
    # Built lazily (not at module import time) so importing app.db.session - or anything
    # that imports it, e.g. auth routes wired into app.main - never forces DATABASE_URL/
    # Settings to be resolved just by importing the module; only handling a request that
    # actually needs the DB does. Keeps tests like test_health.py free of DB config.
    #
    # statement_cache_size=0 disables asyncpg's client-side prepared-statement cache: prod
    # connects via Supabase's transaction-mode pooler (PgBouncer), where a session's queries can
    # land on different backend connections between statements, breaking prepared-statement
    # reuse. Harmless for QA's session-mode pooler too, so it's set unconditionally.
    return create_async_engine(
        to_asyncpg_url(get_settings().database_url),
        connect_args={"statement_cache_size": 0},
    )


async def get_db() -> AsyncIterator[AsyncSession]:
    session_maker = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with session_maker() as session:
        yield session
