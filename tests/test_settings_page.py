"""Tests for the Settings > Storage page (issue #46)."""

import uuid
from html.parser import HTMLParser

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.storage_config import StorageConfig, StorageProviderType


def unique_email() -> str:
    return f"settings-page-{uuid.uuid4().hex}@example.com"


async def _register_and_login(client: AsyncClient) -> str:
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})
    return email


async def test_settings_page_redirects_anonymous_visitor_to_login(client: AsyncClient) -> None:
    response = await client.get("/settings")

    assert response.status_code in (302, 303, 307)
    assert response.headers["location"] == "/login"


async def test_settings_page_renders_storage_tab_and_provider_options(client: AsyncClient) -> None:
    await _register_and_login(client)

    response = await client.get("/settings")

    assert response.status_code == 200
    body = response.text
    assert "Storage" in body
    assert 'id="provider"' in body
    # All three enum providers appear as options; only Google Drive is wired up but the column
    # reserves the others.
    assert 'value="google_drive"' in body
    assert 'value="dropbox"' in body
    assert 'value="s3"' in body
    assert 'id="folder_path"' in body


async def test_settings_page_hides_dropbox_and_s3_by_default(client: AsyncClient) -> None:
    await _register_and_login(client)

    response = await client.get("/settings")

    body = response.text
    # The Dropbox/S3 stubs are gated behind x-show on the selected provider, so they aren't shown
    # until picked. Drive is the default-visible section.
    assert "x-show=\"provider === 'dropbox'\"" in body
    assert "x-show=\"provider === 's3'\"" in body
    assert "x-show=\"provider === 'google_drive'\"" in body


async def test_settings_page_shows_connect_controls_for_disconnected_drive(
    client: AsyncClient,
) -> None:
    await _register_and_login(client)

    response = await client.get("/settings")

    assert response.status_code == 200
    body = response.text
    # A fresh user has no stored OAuth token: the tab offers a Connect control and gates it behind
    # saving a folder path first.
    assert 'id="connect-drive"' in body
    assert "Connect Google Drive" in body
    assert "Save your folder path first" in body
    assert 'x-show="!is_connected"' in body


async def test_settings_page_shows_disconnect_control_when_drive_connected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _register_and_login(client)
    me = await client.get("/api/v1/users/me")
    user_id = uuid.UUID(me.json()["id"])
    # Simulate a connected config (a stored, encrypted-at-rest token) directly in the DB.
    db_session.add(
        StorageConfig(
            user_id=user_id,
            provider=StorageProviderType.GOOGLE_DRIVE,
            folder_path="/OrganizeMe",
            oauth_access_token="ciphertext-token",
        )
    )
    await db_session.flush()

    response = await client.get("/settings")

    assert response.status_code == 200
    body = response.text
    assert 'id="disconnect-drive"' in body
    assert "Disconnect Google Drive" in body
    # is_connected is seeded true into the x-data, so the tab renders the connected branch
    # (tolerant of tojson's spacing).
    assert '"is_connected":true' in body.replace(" ", "")


async def test_settings_page_prefills_saved_folder_path(client: AsyncClient) -> None:
    await _register_and_login(client)
    await client.put(
        "/api/v1/storage-config",
        json={"provider": "google_drive", "folder_path": "/OrganizeMe/reports"},
    )

    response = await client.get("/settings")

    assert response.status_code == 200
    assert 'value="/OrganizeMe/reports"' in response.text


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


async def test_settings_page_x_data_attribute_is_not_truncated_by_a_stray_quote(
    client: AsyncClient,
) -> None:
    # Same class of regression guard as the register page: parse as a browser would and assert the
    # storage component's x-data survives intact past where an embedded quote could cut it short.
    await _register_and_login(client)
    response = await client.get("/settings")

    collector = _XDataCollector()
    collector.feed(response.text)

    storage_x_data = [v for v in collector.x_data_values if "async save()" in v]
    assert storage_x_data, "settings page has no x-data component with a save() method"
    # This fetch call lives well past the start of the attribute; if the value were truncated at a
    # stray quote it wouldn't survive HTML attribute parsing.
    assert '/api/v1/storage-config' in storage_x_data[0]
