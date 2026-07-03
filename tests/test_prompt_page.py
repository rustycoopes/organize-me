"""Tests for the Prompt page (issue #49)."""

import uuid
from html.parser import HTMLParser

from httpx import AsyncClient

from app.core.prompts import FACTORY_DEFAULT_PROMPT


def unique_email() -> str:
    return f"prompt-page-{uuid.uuid4().hex}@example.com"


async def _register_and_login(client: AsyncClient) -> None:
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})


async def test_prompt_page_redirects_anonymous_visitor_to_login(client: AsyncClient) -> None:
    response = await client.get("/prompt")

    assert response.status_code in (302, 303, 307)
    assert response.headers["location"] == "/login"


async def test_prompt_page_renders_current_prompt_in_a_textarea(client: AsyncClient) -> None:
    await _register_and_login(client)

    response = await client.get("/prompt")

    assert response.status_code == 200
    body = response.text
    assert 'id="prompt_text"' in body
    assert "<textarea" in body
    assert 'id="reset-prompt"' in body
    # A fresh user's textarea shows the seeded factory default. Assert on a distinctive line of it
    # (the opening sentence), robust to HTML escaping of the surrounding markup.
    assert "extracts agreed plans and commitments from a WhatsApp conversation" in body


async def test_prompt_page_reflects_a_saved_edit(client: AsyncClient) -> None:
    await _register_and_login(client)
    await client.put("/api/v1/llm-prompt", json={"prompt_text": "my bespoke extraction prompt"})

    response = await client.get("/prompt")

    assert response.status_code == 200
    assert "my bespoke extraction prompt" in response.text
    # The default's distinctive opening sentence should no longer appear (no special chars, so a
    # reliable substring check regardless of HTML escaping elsewhere).
    assert "extracts agreed plans and commitments from a WhatsApp conversation" not in response.text


class _XDataCollector(HTMLParser):
    """Collects every `x-data` attribute value, honouring HTML attribute-quote termination - so a
    stray quote that truncates the attribute (the register.html bug from #23) is caught here too."""

    def __init__(self) -> None:
        super().__init__()
        self.x_data_values: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name == "x-data" and value is not None:
                self.x_data_values.append(value)


async def test_prompt_page_x_data_attribute_is_not_truncated_by_a_stray_quote(
    client: AsyncClient,
) -> None:
    # Same regression guard as the settings/register pages: parse as a browser would and assert the
    # prompt component's x-data survives intact past where an embedded quote could cut it short.
    await _register_and_login(client)
    response = await client.get("/prompt")

    collector = _XDataCollector()
    collector.feed(response.text)

    prompt_x_data = [v for v in collector.x_data_values if "async save()" in v]
    assert prompt_x_data, "prompt page has no x-data component with a save() method"
    # The reset() method lives well past the start of the attribute; if the value were truncated at
    # a stray quote it wouldn't survive HTML attribute parsing.
    assert "async reset()" in prompt_x_data[0]
    assert "/api/v1/llm-prompt/reset" in prompt_x_data[0]
