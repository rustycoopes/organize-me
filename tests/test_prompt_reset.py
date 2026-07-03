"""Unit test for the prompt-reset logic (issue #49 AC: "Prompt-reset logic has a unit test").

Exercises app.api.v1.llm_prompt.set_user_prompt directly - the single create-or-update seam that
both the edit (PUT) and reset paths funnel through - rather than going over HTTP. Runs inside the
rolled-back db_session, so nothing persists.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.llm_prompt import set_user_prompt
from app.core.prompts import FACTORY_DEFAULT_PROMPT
from app.models.llm_prompt import LLMPrompt
from app.models.user import User


async def _make_user(session: AsyncSession) -> User:
    user = User(email=f"reset-{uuid.uuid4().hex}@example.com", hashed_password="not-a-real-hash")
    session.add(user)
    await session.flush()
    return user


async def test_reset_overwrites_an_edited_prompt_with_the_factory_default(
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session)
    # Simulate a user who has edited their prompt.
    await set_user_prompt(db_session, user.id, "my heavily customised prompt")

    # Reset is set_user_prompt called with the factory default.
    reset = await set_user_prompt(db_session, user.id, FACTORY_DEFAULT_PROMPT)

    assert reset.prompt_text == FACTORY_DEFAULT_PROMPT
    # ...and it updated the existing row rather than creating a second one.
    count = await db_session.scalar(
        select(func.count()).select_from(LLMPrompt).where(LLMPrompt.user_id == user.id)
    )
    assert count == 1


async def test_reset_creates_the_row_for_a_legacy_user_with_none(db_session: AsyncSession) -> None:
    # An account created before the #48 seed has no prompt row; resetting must create one.
    user = await _make_user(db_session)

    reset = await set_user_prompt(db_session, user.id, FACTORY_DEFAULT_PROMPT)

    assert reset.prompt_text == FACTORY_DEFAULT_PROMPT
    stored = await db_session.scalar(select(LLMPrompt).where(LLMPrompt.user_id == user.id))
    assert stored is not None
    assert stored.prompt_text == FACTORY_DEFAULT_PROMPT
