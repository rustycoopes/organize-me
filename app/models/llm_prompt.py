import uuid
from datetime import datetime

from fastapi_users_db_sqlalchemy.generics import GUID
from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LLMPrompt(Base):
    """A user's single extraction prompt (one row per user — unique on user_id).

    Seeded with app.core.prompts.FACTORY_DEFAULT_PROMPT on new-user creation; the view/edit/reset
    endpoints and page that sit on top of it land in Slice 3.1 (#49). This model + its migration
    are the Slice 3.0 foundation.
    """

    __tablename__ = "llm_prompts"
    __table_args__ = {"schema": "event_creator"}

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    # UNIQUE: one prompt per user. ON DELETE CASCADE so removing a user removes their prompt
    # (matches storage_configs / oauth_accounts).
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("host.users.id", ondelete="cascade"), nullable=False, unique=True
    )
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
