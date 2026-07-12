from datetime import datetime
from typing import TYPE_CHECKING

from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID
from sqlalchemy import DateTime, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.oauth_account import OAuthAccount


class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "users"
    __table_args__ = (
        # FastAPI-Users looks up users by case-insensitive email (func.lower(email) in
        # SQLAlchemyUserDatabase.get_by_email), so uniqueness must be enforced the same way,
        # or two accounts differing only by case could be created.
        Index("ix_users_email_lower", text("lower(email)"), unique=True),
        {"schema": "host"},
    )

    # Override the mixin's plain case-sensitive unique index; ix_users_email_lower above
    # replaces it. Typed under TYPE_CHECKING as plain `str` (matching the base mixin's own
    # convention), not `Mapped[str]`, so this class keeps satisfying fastapi_users'
    # UserProtocol structurally under mypy - re-declaring it as Mapped[str] here would shadow
    # the base class's TYPE_CHECKING-only `email: str` and fail the protocol check.
    if TYPE_CHECKING:
        email: str
    else:
        email: Mapped[str] = mapped_column(
            String(length=320), nullable=False, index=False, unique=False
        )

    name: Mapped[str | None] = mapped_column(nullable=True)
    phone_number: Mapped[str | None] = mapped_column(nullable=True)
    dark_mode: Mapped[bool] = mapped_column(default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # eager ("joined") load: SQLAlchemyUserDatabase.add_oauth_account appends to this
    # collection synchronously without an extra awaited fetch, and BaseUserManager.oauth_callback
    # reads it directly off the returned user - fastapi-users' own docs call out lazy="joined" as
    # required here for exactly this reason under async SQLAlchemy. Accepted trade-off: every User
    # load (not just the Google OAuth path) now carries a LEFT JOIN against oauth_accounts,
    # including the plain email/password login and current_active_user paths that never read this
    # collection - any query against User must call .unique() as a result (see
    # SQLAlchemyUserDatabase._get_user, and tests/test_db_session.py). "selectin" wouldn't remove
    # this cost, just turn the join into a second query fired on every load; not worth the
    # complexity of a per-call-site override at this app's scale.
    # passive_deletes="all" (not plain True): OAuthAccount.user_id is NOT NULL, so without this
    # SQLAlchemy's unit-of-work would try to NULL it out on session.delete(user) instead of
    # letting the DB's ON DELETE CASCADE handle it, raising an IntegrityError before the delete
    # ever reaches Postgres. Plain passive_deletes=True only skips *loading* an unloaded
    # collection before nulling it - useless here since lazy="joined" means oauth_accounts is
    # always already loaded, so the "already in the session" null-out still fires. "all" is the
    # value that actually suppresses the null-out for already-loaded children too.
    oauth_accounts: Mapped[list[OAuthAccount]] = relationship(lazy="joined", passive_deletes="all")
