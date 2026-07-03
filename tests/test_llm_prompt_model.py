"""Tests for the llm_prompts model + migration (issue #48).

These exercise the real table on the QA database (created by the Alembic migration that CI runs
before pytest), inside the rolled-back db_session fixture - so nothing persists.
"""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.prompts import FACTORY_DEFAULT_PROMPT
from app.models.llm_prompt import LLMPrompt
from app.models.user import User


def test_factory_default_prompt_matches_canonical_wording() -> None:
    """Guard the issue #48 requirement that the factory default is stored *verbatim*.

    The seed tests only assert the seeded row equals FACTORY_DEFAULT_PROMPT, so both sides move
    together - a stray edit to the constant would slip through unnoticed. This pins the canonical
    wording (opening/closing lines + the five JSON output fields) independently.
    """
    assert FACTORY_DEFAULT_PROMPT.startswith(
        "You are an assistant that extracts agreed plans and commitments from a WhatsApp "
        "conversation between co-parents or family members."
    )
    assert FACTORY_DEFAULT_PROMPT.rstrip().endswith("Return only the JSON array, no commentary.")
    # No accidental leading/trailing whitespace on the stored constant.
    assert FACTORY_DEFAULT_PROMPT == FACTORY_DEFAULT_PROMPT.strip()
    # The five JSON output fields the pipeline (Slice 4) relies on must all be named.
    for field in ("type", "description", "resolved_date", "raw_date_text", "agreed_by"):
        assert f'"{field}"' in FACTORY_DEFAULT_PROMPT


async def _make_user(session: AsyncSession) -> User:
    user = User(email=f"prompt-{uuid.uuid4().hex}@example.com", hashed_password="not-a-real-hash")
    session.add(user)
    await session.flush()
    return user


async def test_llm_prompt_persists_and_round_trips(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    prompt = LLMPrompt(user_id=user.id, prompt_text="extract the events please")
    db_session.add(prompt)
    await db_session.flush()

    await db_session.refresh(prompt)
    stored = await db_session.scalar(select(LLMPrompt).where(LLMPrompt.user_id == user.id))
    assert stored is not None
    assert stored.prompt_text == "extract the events please"
    # server-default timestamps are populated on insert
    assert stored.created_at is not None
    assert stored.updated_at is not None


async def test_llm_prompt_is_unique_per_user(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    db_session.add(LLMPrompt(user_id=user.id, prompt_text="first"))
    await db_session.flush()

    db_session.add(LLMPrompt(user_id=user.id, prompt_text="second"))
    with pytest.raises(IntegrityError):
        await db_session.flush()
