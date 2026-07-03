"""Read/update/reset the current user's single extraction prompt (issue #49).

`GET`/`PUT /api/v1/llm-prompt` and `POST /api/v1/llm-prompt/reset` back the Prompt page. Stands on
the Slice 3.0 foundation (issue #48): the `llm_prompts` table and the `FACTORY_DEFAULT_PROMPT`
constant, which is the shared source of truth for both new-user seeding and the Reset button here.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.users import current_active_user
from app.core.prompts import FACTORY_DEFAULT_PROMPT
from app.db.session import get_db
from app.models.llm_prompt import LLMPrompt
from app.models.user import User
from app.schemas.llm_prompt import LLMPromptRead, LLMPromptWrite

router = APIRouter(prefix="/api/v1", tags=["llm-prompt"])


async def get_user_prompt(db: AsyncSession, user_id: uuid.UUID) -> LLMPrompt | None:
    """The user's single prompt row, or ``None`` if they have no row yet.

    New users are seeded a row at registration (#48), so this normally returns a row; it can be
    ``None`` for accounts created before that seed existed. Shared by this router and the Prompt
    page so the "one prompt per user" lookup lives in one place.
    """
    result = await db.execute(select(LLMPrompt).where(LLMPrompt.user_id == user_id))
    return result.scalar_one_or_none()


async def get_or_create_user_prompt(db: AsyncSession, user_id: uuid.UUID) -> LLMPrompt:
    """The user's prompt row, creating one seeded with the factory default if none exists.

    New users are seeded a row at registration (#48), but an account created before that seed has
    none. Rather than returning the factory default read-only every time, this self-heals such a
    legacy account on first read so the DB always holds a real row. Shared by the GET endpoint and
    the Prompt page so a legacy user is healed whichever they hit first.
    """
    prompt = await get_user_prompt(db, user_id)
    if prompt is not None:
        return prompt
    prompt = LLMPrompt(user_id=user_id, prompt_text=FACTORY_DEFAULT_PROMPT)
    db.add(prompt)
    try:
        await db.commit()
    except IntegrityError:
        # A concurrent request for the same legacy user created the row first (user_id is UNIQUE);
        # roll back our losing INSERT and use theirs. Mirrors the oauth first-login race in
        # app/api/v1/auth.py.
        await db.rollback()
        existing = await get_user_prompt(db, user_id)
        if existing is None:
            raise
        return existing
    return prompt


async def set_user_prompt(db: AsyncSession, user_id: uuid.UUID, prompt_text: str) -> LLMPrompt:
    """Create-or-update the user's single prompt row to ``prompt_text`` and commit.

    ``user_id`` is UNIQUE, so this is never an insert of a second row. Both the edit (PUT) and the
    reset paths funnel through here, so "persist a prompt for this user" is defined once. Reset is
    just this called with ``FACTORY_DEFAULT_PROMPT``.
    """
    prompt = await get_user_prompt(db, user_id)
    if prompt is None:
        prompt = LLMPrompt(user_id=user_id, prompt_text=prompt_text)
        db.add(prompt)
    else:
        prompt.prompt_text = prompt_text
    # get_db doesn't auto-commit, so persist here (savepoint-safe under the test fixture's
    # rolled-back session).
    await db.commit()
    return prompt


@router.get("/llm-prompt", response_model=LLMPromptRead)
async def read_prompt(
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
) -> LLMPromptRead:
    prompt = await get_or_create_user_prompt(db, user.id)
    return LLMPromptRead(prompt_text=prompt.prompt_text)


@router.put("/llm-prompt", response_model=LLMPromptRead)
async def update_prompt(
    payload: LLMPromptWrite,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
) -> LLMPromptRead:
    prompt = await set_user_prompt(db, user.id, payload.prompt_text)
    return LLMPromptRead(prompt_text=prompt.prompt_text)


@router.post("/llm-prompt/reset", response_model=LLMPromptRead)
async def reset_prompt(
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
) -> LLMPromptRead:
    prompt = await set_user_prompt(db, user.id, FACTORY_DEFAULT_PROMPT)
    return LLMPromptRead(prompt_text=prompt.prompt_text)
