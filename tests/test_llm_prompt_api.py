"""Tests for GET/PUT /api/v1/llm-prompt and POST /api/v1/llm-prompt/reset (issue #49).

Run against the QA DB inside the rolled-back db_session fixture (see conftest), so nothing
persists. Auth is a real register + cookie login through the app, matching the storage-config
tests. Registration seeds the factory-default prompt (#48), so a fresh account already has one.
"""

import uuid

from httpx import AsyncClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.prompts import FACTORY_DEFAULT_PROMPT
from app.models.llm_prompt import LLMPrompt


def unique_email() -> str:
    return f"prompt-api-{uuid.uuid4().hex}@example.com"


async def _register_and_login(client: AsyncClient) -> None:
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})


async def test_get_returns_the_seeded_factory_default_for_a_new_user(client: AsyncClient) -> None:
    await _register_and_login(client)

    response = await client.get("/api/v1/llm-prompt")

    assert response.status_code == 200
    assert response.json() == {"prompt_text": FACTORY_DEFAULT_PROMPT}


async def test_get_self_heals_a_legacy_user_with_no_row(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Simulate a legacy account created before the #48 seed by deleting the seeded row, then assert
    # GET recreates it (returns the factory default AND leaves exactly one row behind).
    await _register_and_login(client)
    user_id = uuid.UUID((await client.get("/api/v1/users/me")).json()["id"])
    await db_session.execute(delete(LLMPrompt).where(LLMPrompt.user_id == user_id))
    await db_session.commit()

    response = await client.get("/api/v1/llm-prompt")

    assert response.status_code == 200
    assert response.json() == {"prompt_text": FACTORY_DEFAULT_PROMPT}
    count = await db_session.scalar(
        select(func.count()).select_from(LLMPrompt).where(LLMPrompt.user_id == user_id)
    )
    assert count == 1


async def test_put_saves_edited_text_and_get_returns_it(client: AsyncClient) -> None:
    await _register_and_login(client)

    edited = "Only extract dentist appointments."
    put = await client.put("/api/v1/llm-prompt", json={"prompt_text": edited})

    assert put.status_code == 200
    assert put.json() == {"prompt_text": edited}

    follow_up = await client.get("/api/v1/llm-prompt")
    assert follow_up.status_code == 200
    assert follow_up.json() == {"prompt_text": edited}


async def test_put_trims_surrounding_whitespace(client: AsyncClient) -> None:
    await _register_and_login(client)

    put = await client.put("/api/v1/llm-prompt", json={"prompt_text": "  trimmed me  "})

    assert put.status_code == 200
    assert put.json() == {"prompt_text": "trimmed me"}


async def test_put_rejects_blank_prompt(client: AsyncClient) -> None:
    await _register_and_login(client)

    for blank in ("", "   "):
        response = await client.put("/api/v1/llm-prompt", json={"prompt_text": blank})
        assert response.status_code == 422


async def test_reset_restores_factory_default_after_an_edit(client: AsyncClient) -> None:
    await _register_and_login(client)

    await client.put("/api/v1/llm-prompt", json={"prompt_text": "my custom prompt"})

    reset = await client.post("/api/v1/llm-prompt/reset")
    assert reset.status_code == 200
    assert reset.json() == {"prompt_text": FACTORY_DEFAULT_PROMPT}

    # A following GET returns the restored default, proving the reset persisted.
    follow_up = await client.get("/api/v1/llm-prompt")
    assert follow_up.json() == {"prompt_text": FACTORY_DEFAULT_PROMPT}


async def test_edit_and_reset_never_create_a_second_row(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _register_and_login(client)
    user_id = uuid.UUID((await client.get("/api/v1/users/me")).json()["id"])

    await client.put("/api/v1/llm-prompt", json={"prompt_text": "custom"})
    await client.post("/api/v1/llm-prompt/reset")

    count = await db_session.scalar(
        select(func.count()).select_from(LLMPrompt).where(LLMPrompt.user_id == user_id)
    )
    assert count == 1


async def test_endpoints_require_authentication(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/llm-prompt")).status_code == 401
    assert (
        await client.put("/api/v1/llm-prompt", json={"prompt_text": "x"})
    ).status_code == 401
    assert (await client.post("/api/v1/llm-prompt/reset")).status_code == 401
