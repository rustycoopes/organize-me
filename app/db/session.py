from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.db.url import to_asyncpg_url


def create_engine() -> AsyncEngine:
    # statement_cache_size=0 disables asyncpg's client-side prepared-statement cache: prod
    # connects via Supabase's transaction-mode pooler (PgBouncer), where a session's queries can
    # land on different backend connections between statements, breaking prepared-statement
    # reuse. Harmless for QA's session-mode pooler too, so it's set unconditionally.
    return create_async_engine(
        to_asyncpg_url(get_settings().database_url),
        connect_args={"statement_cache_size": 0},
    )


engine = create_engine()
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with async_session_maker() as session:
        yield session
