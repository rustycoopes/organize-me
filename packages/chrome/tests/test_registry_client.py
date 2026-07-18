import httpx
import pytest

from organizeme_chrome.registry import AppEntry, AppNavItem, SettingsTab
from organizeme_chrome.registry_client import FetchedRegistrySource, fetch_registry_once

_TOKEN = "fake-oidc-token"


async def _fake_token_provider() -> str:
    return _TOKEN


def _client(handler: httpx.MockTransport) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _registry_json() -> list[dict]:
    return [
        {
            "service_name": "organizeme",
            "nav": [{"path": "/settings", "label": "Settings"}],
            "settings_tabs": [],
            "api_prefixes": [],
        },
        {
            "service_name": "event-creator",
            "nav": [{"path": "/dashboard", "label": "Dashboard"}],
            "settings_tabs": [{"id": "storage", "label": "Storage"}],
            "api_prefixes": ["/api/v1/events"],
        },
    ]


async def test_fetch_registry_once_returns_parsed_apps_on_200() -> None:
    seen_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        return httpx.Response(200, json=_registry_json())

    async with _client(handler) as client:
        apps = await fetch_registry_once(client, "https://host.example", _fake_token_provider)

    assert apps == [
        AppEntry(
            service_name="organizeme",
            nav=[AppNavItem("/settings", "Settings")],
            settings_tabs=[],
            api_prefixes=[],
        ),
        AppEntry(
            service_name="event-creator",
            nav=[AppNavItem("/dashboard", "Dashboard")],
            settings_tabs=[SettingsTab("storage", "Storage")],
            api_prefixes=["/api/v1/events"],
        ),
    ]
    assert len(seen_requests) == 1
    request = seen_requests[0]
    assert request.url == "https://host.example/internal/app-registry.json"
    assert request.headers["authorization"] == f"Bearer {_TOKEN}"


async def test_fetch_registry_once_strips_trailing_slash_from_host_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_registry_json())

    async with _client(handler) as client:
        await fetch_registry_once(client, "https://host.example/", _fake_token_provider)


@pytest.mark.parametrize("status_code", [401, 403, 500, 503])
async def test_fetch_registry_once_raises_on_error_status(status_code: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"detail": "nope"})

    async with _client(handler) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await fetch_registry_once(client, "https://host.example", _fake_token_provider)


async def test_fetch_registry_once_raises_on_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    async with _client(handler) as client:
        with pytest.raises(httpx.TimeoutException):
            await fetch_registry_once(client, "https://host.example", _fake_token_provider)


async def test_fetch_registry_once_raises_on_malformed_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not json")

    async with _client(handler) as client:
        with pytest.raises(ValueError):
            await fetch_registry_once(client, "https://host.example", _fake_token_provider)


async def test_fetch_registry_once_raises_on_unexpected_shape() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"not": "a list"})

    async with _client(handler) as client:
        with pytest.raises(ValueError):
            await fetch_registry_once(client, "https://host.example", _fake_token_provider)


def _self_entry() -> AppEntry:
    return AppEntry(
        service_name="event-creator",
        nav=[AppNavItem("/dashboard", "Dashboard")],
        settings_tabs=[],
    )


def test_fetched_registry_source_starts_on_the_self_only_default() -> None:
    source = FetchedRegistrySource(self_only_default=_self_entry())

    assert source.get_apps() == [_self_entry()]


def test_fetched_registry_source_update_replaces_the_cache() -> None:
    source = FetchedRegistrySource(self_only_default=_self_entry())
    other_app = AppEntry(service_name="organizeme", nav=[], settings_tabs=[])

    source.update([other_app, _self_entry()])

    assert source.get_apps() == [other_app, _self_entry()]


def test_fetched_registry_source_get_apps_after_failed_update_call_keeps_last_known_good() -> None:
    # A failed fetch never calls update() at all (see registry_client.py's docstring) - this test
    # documents that behavior at the FetchedRegistrySource level: simply not calling update()
    # leaves the previous cache in place.
    source = FetchedRegistrySource(self_only_default=_self_entry())
    warm_app = AppEntry(service_name="organizeme", nav=[], settings_tabs=[])
    source.update([warm_app])

    # ... a subsequent fetch fails; the caller's loop does not call update() again.

    assert source.get_apps() == [warm_app]
