"""Tests for GET/PUT /api/v1/storage-config (issue #46).

Run against the QA DB inside the rolled-back db_session fixture (see conftest), so nothing
persists. Auth is a real register + cookie login through the app, matching tests/test_users.py.
"""

import uuid

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.storage_config import StorageConfig, StorageProviderType


def unique_email() -> str:
    return f"storage-cfg-{uuid.uuid4().hex}@example.com"


async def _register_and_login(client: AsyncClient) -> str:
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})
    return email


async def test_get_returns_unset_state_when_no_config(client: AsyncClient) -> None:
    await _register_and_login(client)

    response = await client.get("/api/v1/storage-config")

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] is None
    assert body["folder_path"] is None
    assert body["is_connected"] is False


async def test_put_creates_config_and_get_returns_it(client: AsyncClient) -> None:
    await _register_and_login(client)

    put = await client.put(
        "/api/v1/storage-config",
        json={"provider": "google_drive", "folder_path": "/OrganizeMe/exports"},
    )

    assert put.status_code == 200
    assert put.json() == {
        "provider": "google_drive",
        "folder_path": "/OrganizeMe/exports",
        "is_connected": False,
    }

    follow_up = await client.get("/api/v1/storage-config")
    assert follow_up.status_code == 200
    assert follow_up.json() == {
        "provider": "google_drive",
        "folder_path": "/OrganizeMe/exports",
        "is_connected": False,
    }


async def test_put_is_an_upsert_and_updates_existing_config(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _register_and_login(client)

    await client.put(
        "/api/v1/storage-config",
        json={"provider": "google_drive", "folder_path": "/first"},
    )
    second = await client.put(
        "/api/v1/storage-config",
        json={"provider": "s3", "folder_path": "/second"},
    )

    assert second.status_code == 200
    assert second.json() == {"provider": "s3", "folder_path": "/second", "is_connected": False}

    # The second PUT must have updated the same row, not inserted a second one (user_id is UNIQUE,
    # so a duplicate insert would have raised instead of returning 200 anyway - assert it directly).
    me = await client.get("/api/v1/users/me")
    user_id = uuid.UUID(me.json()["id"])
    row_count = await db_session.scalar(
        select(func.count()).select_from(StorageConfig).where(StorageConfig.user_id == user_id)
    )
    assert row_count == 1


async def test_put_rejects_empty_folder_path(client: AsyncClient) -> None:
    await _register_and_login(client)

    response = await client.put(
        "/api/v1/storage-config",
        json={"provider": "google_drive", "folder_path": ""},
    )

    assert response.status_code == 422


async def test_put_rejects_whitespace_only_folder_path(client: AsyncClient) -> None:
    await _register_and_login(client)

    response = await client.put(
        "/api/v1/storage-config",
        json={"provider": "google_drive", "folder_path": "   "},
    )

    assert response.status_code == 422


async def test_put_trims_surrounding_whitespace_from_folder_path(client: AsyncClient) -> None:
    await _register_and_login(client)

    response = await client.put(
        "/api/v1/storage-config",
        json={"provider": "google_drive", "folder_path": "  /OrganizeMe/exports  "},
    )

    assert response.status_code == 200
    assert response.json()["folder_path"] == "/OrganizeMe/exports"

    follow_up = await client.get("/api/v1/storage-config")
    assert follow_up.json()["folder_path"] == "/OrganizeMe/exports"


async def test_put_rejects_unknown_provider(client: AsyncClient) -> None:
    await _register_and_login(client)

    response = await client.put(
        "/api/v1/storage-config",
        json={"provider": "onedrive", "folder_path": "/x"},
    )

    assert response.status_code == 422


async def test_read_never_leaks_stored_credentials(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # A config with a (fake) encrypted OAuth token stored. The read schema must expose only
    # provider + folder_path and never echo the secret columns back.
    await _register_and_login(client)
    me = await client.get("/api/v1/users/me")
    user_id = uuid.UUID(me.json()["id"])

    secret = "super-secret-encrypted-token-value"
    db_session.add(
        StorageConfig(
            user_id=user_id,
            provider=StorageProviderType.GOOGLE_DRIVE,
            folder_path="/OrganizeMe",
            oauth_access_token=secret,
            oauth_refresh_token=secret,
        )
    )
    await db_session.flush()

    response = await client.get("/api/v1/storage-config")

    assert response.status_code == 200
    body = response.json()
    # Only the safe fields are exposed - never the raw token columns themselves.
    assert set(body.keys()) == {"provider", "folder_path", "is_connected"}
    assert secret not in response.text
    # is_connected reflects that a token is present, without revealing the token.
    assert body["is_connected"] is True


async def test_get_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/storage-config")
    assert response.status_code == 401


async def test_put_requires_authentication(client: AsyncClient) -> None:
    response = await client.put(
        "/api/v1/storage-config",
        json={"provider": "google_drive", "folder_path": "/x"},
    )
    assert response.status_code == 401
