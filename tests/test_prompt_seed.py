"""Seed-on-registration tests for the factory-default prompt (issue #48).

Registering a new user must create exactly one llm_prompts row whose text is the factory default,
for both the email/password and Google-OAuth registration paths - and linking Google to an
existing account must NOT create a second prompt. All run inside the rolled-back db_session, so
nothing persists to QA.
"""

import uuid

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.prompts import FACTORY_DEFAULT_PROMPT
from app.models.llm_prompt import LLMPrompt
from tests.test_auth_google import google_login


def unique_email() -> str:
    return f"prompt-seed-{uuid.uuid4().hex}@example.com"


async def _prompts_for(session: AsyncSession, user_id: str) -> list[LLMPrompt]:
    return list(
        (await session.scalars(select(LLMPrompt).where(LLMPrompt.user_id == uuid.UUID(user_id)))).all()
    )


async def test_email_password_registration_seeds_factory_default_prompt(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        data={"email": unique_email(), "password": "correct-horse-battery"},
    )
    assert response.status_code == 201
    user_id = response.json()["id"]

    prompts = await _prompts_for(db_session, user_id)
    assert len(prompts) == 1
    assert prompts[0].prompt_text == FACTORY_DEFAULT_PROMPT


async def test_google_registration_seeds_factory_default_prompt(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await google_login(client, unique_email())
    user_id = (await client.get("/api/v1/users/me")).json()["id"]

    prompts = await _prompts_for(db_session, user_id)
    assert len(prompts) == 1
    assert prompts[0].prompt_text == FACTORY_DEFAULT_PROMPT


async def test_linking_google_to_existing_account_does_not_double_seed(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # An email/password user who later signs in with Google (same address) gets the Google
    # account linked to their existing user - on_after_register does not fire again, so they keep
    # exactly one prompt rather than getting a second.
    email = unique_email()
    register = await client.post(
        "/api/v1/auth/register", data={"email": email, "password": "correct-horse-battery"}
    )
    user_id = register.json()["id"]
    await client.post("/api/v1/auth/logout")

    await google_login(client, email)

    count = await db_session.scalar(
        select(func.count()).select_from(LLMPrompt).where(LLMPrompt.user_id == uuid.UUID(user_id))
    )
    assert count == 1
