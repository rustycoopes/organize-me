import uuid
from typing import TYPE_CHECKING

from fastapi_users_db_sqlalchemy import SQLAlchemyBaseOAuthAccountTableUUID
from fastapi_users_db_sqlalchemy.generics import GUID
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OAuthAccount(SQLAlchemyBaseOAuthAccountTableUUID, Base):
    __tablename__ = "oauth_accounts"
    __table_args__ = {"schema": "host"}

    # The mixin's user_id column hardcodes ForeignKey("user.id", ...), but this app's users
    # table is named "users" (see User.__tablename__), not the fastapi-users default "user".
    # Schema-qualified ("host.users.id") since an unqualified target isn't guaranteed to resolve
    # against this table's own schema (Slice R1 - Database Schema Separation, #156).
    if TYPE_CHECKING:
        user_id: uuid.UUID
    else:
        user_id: Mapped[uuid.UUID] = mapped_column(
            GUID, ForeignKey("host.users.id", ondelete="cascade"), nullable=False
        )
