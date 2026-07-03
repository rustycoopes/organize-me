"""Tests for the Upload page (#52)."""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.storage_config import StorageConfig, StorageProviderType


def unique_email() -> str:
    return f"upload-page-{uuid.uuid4().hex}@example.com"


async def _register_and_login(client: AsyncClient) -> uuid.UUID:
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})
    me = await client.get("/api/v1/users/me")
    return uuid.UUID(me.json()["id"])


async def test_upload_page_redirects_anonymous_visitor_to_login(client: AsyncClient) -> None:
    response = await client.get("/upload")

    assert response.status_code in (302, 303, 307)
    assert response.headers["location"] == "/login"


async def test_upload_page_renders_dropzone_and_file_picker(client: AsyncClient) -> None:
    await _register_and_login(client)

    response = await client.get("/upload")

    assert response.status_code == 200
    body = response.text
    assert 'id="upload-dropzone"' in body
    assert 'id="file-input"' in body
    # Accepts the three supported types via the picker.
    assert 'accept=".txt,.zip,.csv"' in body
    # Posts to the upload endpoint.
    assert "/api/v1/upload" in body


async def test_upload_page_warns_when_drive_not_connected(client: AsyncClient) -> None:
    await _register_and_login(client)

    response = await client.get("/upload")

    body = response.text
    # A fresh user has no Drive connection: seed drive_connected=false and show the Settings steer.
    assert "driveConnected:false" in body.replace(" ", "")
    assert "/settings" in body


async def test_upload_page_marks_drive_connected_when_token_present(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    db_session.add(
        StorageConfig(
            user_id=user_id,
            provider=StorageProviderType.GOOGLE_DRIVE,
            folder_path="/OrganizeMe",
            oauth_access_token="ciphertext-token",
        )
    )
    await db_session.flush()

    response = await client.get("/upload")

    assert response.status_code == 200
    assert "driveConnected:true" in response.text.replace(" ", "")
