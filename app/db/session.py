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
    return create_async_engine(to_asyncpg_url(get_settings().database_url))


engine = create_engine()
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with async_session_maker() as session:
        yield session
