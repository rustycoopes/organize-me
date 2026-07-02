import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def test_insert_and_read_back_user(db_session: AsyncSession) -> None:
    user = User(
        email="smoke-test@example.com",
        hashed_password="not-a-real-hash",
        name="Smoke Test",
    )
    db_session.add(user)
    await db_session.flush()

    # User.email is typed as plain `str` (not Mapped[str]) under TYPE_CHECKING so User satisfies
    # fastapi_users' UserProtocol (see app/models/user.py) - harmless at runtime, but it means
    # mypy sees this comparison as str.__eq__ -> bool instead of a SQLAlchemy ColumnElement.
    result = await db_session.execute(
        select(User).where(User.email == "smoke-test@example.com")  # type: ignore[arg-type]
    )
    # .unique() is required whenever the query touches a joined-eager-loaded collection -
    # User.oauth_accounts uses lazy="joined" (see app/models/user.py) so SQLAlchemy can dedupe
    # the row multiplication a LEFT OUTER JOIN against that collection would otherwise produce.
    fetched = result.unique().scalar_one()

    assert fetched.id == user.id
    assert fetched.name == "Smoke Test"
    assert fetched.is_active is True
    assert fetched.dark_mode is False
    assert fetched.notification_sms is True


async def test_email_uniqueness_is_case_insensitive(db_session: AsyncSession) -> None:
    db_session.add(User(email="dupe@example.com", hashed_password="hash-one"))
    await db_session.flush()

    db_session.add(User(email="DUPE@example.com", hashed_password="hash-two"))
    with pytest.raises(IntegrityError):
        await db_session.flush()
