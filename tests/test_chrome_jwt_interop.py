"""Interop check for Slice R3: a real Host-issued auth cookie must verify via
organizeme_chrome.verify_token — the standalone helper a hosted app (Event Creator, R6) will
depend on instead of fastapi-users. See packages/chrome for the helper's own isolated unit tests
(signature/expiry/audience rejection); this test only proves it accepts what the Host actually
issues.
"""

import uuid

from httpx import AsyncClient
from organizeme_chrome import verify_token

from app.core.config import get_settings


def unique_email() -> str:
    return f"chrome-jwt-interop-{uuid.uuid4().hex}@example.com"


async def test_host_issued_cookie_verifies_via_the_chrome_helper(client: AsyncClient) -> None:
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})

    cookie = client.cookies.get("organizeme_auth")
    assert cookie is not None

    user_id = verify_token(cookie, get_settings().jwt_secret)
    assert user_id  # a non-empty user id was recovered from the token's `sub` claim
