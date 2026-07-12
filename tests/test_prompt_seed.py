"""Lazy-seed tests for the factory-default prompt (issue #48, revised for #158 / Slice R2).

Registering a new user (email/password OR Google OAuth) must NOT eagerly create an llm_prompts
row anymore - on_after_register is a pure Host action now. The default prompt is instead created
lazily the first time GET /api/v1/llm-prompt runs (see app/api/v1/llm_prompt.py::
get_or_create_user_prompt), and linking Google to an existing account must never double it. All run
inside the rolled-back db_session, so nothing persists to QA.
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


async def test_email_password_registration_does_not_eagerly_seed_prompt(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        data={"email": unique_email(), "password": "correct-horse-battery"},
    )
    assert response.status_code == 201
    user_id = response.json()["id"]

    prompts = await _prompts_for(db_session, user_id)
    assert prompts == []


async def test_google_registration_does_not_eagerly_seed_prompt(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await google_login(client, unique_email())
    user_id = (await client.get("/api/v1/users/me")).json()["id"]

    prompts = await _prompts_for(db_session, user_id)
    assert prompts == []


async def test_prompt_page_lazily_creates_default_prompt_on_first_visit(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    email = unique_email()
    password = "correct-horse-battery"
    response = await client.post(
        "/api/v1/auth/register", data={"email": email, "password": password}
    )
    user_id = response.json()["id"]
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})

    get_response = await client.get("/api/v1/llm-prompt")

    assert get_response.status_code == 200
    assert get_response.json() == {"prompt_text": FACTORY_DEFAULT_PROMPT}
    prompts = await _prompts_for(db_session, user_id)
    assert len(prompts) == 1
    assert prompts[0].prompt_text == FACTORY_DEFAULT_PROMPT


async def test_linking_google_to_existing_account_does_not_double_seed(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # An email/password user who later signs in with Google (same address) gets the Google
    # account linked to their existing user - on_after_register does not fire again for a link, so
    # they still end up with exactly one (lazily-created) prompt rather than getting a second.
    email = unique_email()
    password = "correct-horse-battery"
    register = await client.post(
        "/api/v1/auth/register", data={"email": email, "password": password}
    )
    user_id = register.json()["id"]
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})

    # Visit the Prompt page (lazily creates the first row) before logging out and linking Google.
    first_get = await client.get("/api/v1/llm-prompt")
    assert first_get.status_code == 200

    await client.post("/api/v1/auth/logout")
    await google_login(client, email)

    second_get = await client.get("/api/v1/llm-prompt")
    assert second_get.status_code == 200
    assert second_get.json() == {"prompt_text": FACTORY_DEFAULT_PROMPT}

    count = await db_session.scalar(
        select(func.count()).select_from(LLMPrompt).where(LLMPrompt.user_id == uuid.UUID(user_id))
    )
    assert count == 1
