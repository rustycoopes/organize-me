"""HTTP fetch + cache client for the registry-decoupling feature (organize-me#218).

Leaf module: imported by nothing else in this package, so `nav_groups.py`, `templating.py`,
`jwt_verify.py` (and `generate_url_map.py`'s direct import of `organizeme_chrome.registry`) stay
free of `httpx`/`asyncio`/`google.auth`. See docs/adr/registry-decoupling-client-boundary.md.

This module intentionally does not schedule itself - it exposes a pure, awaitable
`fetch_registry_once()` only. Each consumer's own `lifespan` owns the refresh loop (spawn on
startup, cancel on shutdown) and decides what happens on a failed fetch (this module raises;
callers are expected to log and keep serving the existing cache - see
docs/features/registry-decoupling/TDD.md "Background refresh loop").
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import httpx

from organizeme_chrome.registry import AppEntry, AppNavItem, RegistrySource, SettingsTab

TokenProvider = Callable[[], Awaitable[str]]


def _parse_apps(payload: object) -> list[AppEntry]:
    if not isinstance(payload, list):
        raise ValueError(f"expected a JSON array of app entries, got {type(payload).__name__}")
    apps = []
    for item in payload:
        apps.append(
            AppEntry(
                service_name=item["service_name"],
                nav=[AppNavItem(path=nav["path"], label=nav["label"]) for nav in item["nav"]],
                settings_tabs=[
                    SettingsTab(id=tab["id"], label=tab["label"]) for tab in item["settings_tabs"]
                ],
                api_prefixes=list(item.get("api_prefixes", [])),
            )
        )
    return apps


async def fetch_registry_once(
    client: httpx.AsyncClient,
    host_url: str,
    token_provider: TokenProvider,
) -> list[AppEntry]:
    """Fetch the Host's current registry once. Raises on any failure (network error, non-2xx
    response, malformed JSON) - it never returns a partial or stale result; callers decide what
    to do with a failure (see module docstring)."""
    token = await token_provider()
    response = await client.get(
        f"{host_url.rstrip('/')}/internal/app-registry.json",
        headers={"Authorization": f"Bearer {token}"},
    )
    response.raise_for_status()
    return _parse_apps(response.json())


class FetchedRegistrySource:
    """A `RegistrySource` backed by a background-refreshed in-memory cache.

    Starts out serving `self_only_default` (the consumer's own `AppEntry` - the one thing it can
    vouch for about itself, per PRD "Cold-start fallback") until the owning consumer's refresh
    loop calls `update()` after its first successful fetch. A single reference reassignment is
    atomic under CPython's GIL, so no lock is needed for `get_apps()`/`update()` to be called
    concurrently from different tasks.
    """

    def __init__(self, self_only_default: AppEntry) -> None:
        self._apps: list[AppEntry] = [self_only_default]

    def get_apps(self) -> list[AppEntry]:
        return self._apps

    def update(self, apps: list[AppEntry]) -> None:
        self._apps = apps


# Confirms FetchedRegistrySource actually satisfies the protocol it's documented against.
_: type[RegistrySource] = FetchedRegistrySource


def _fetch_id_token_blocking(audience: str) -> str:
    # Imported here, not at module level, so a consumer that injects its own token_provider (every
    # test in this package's own suite, per docs/features/registry-decoupling/TDD.md) never needs
    # google-auth's metadata-server client actually reachable.
    from google.auth.transport import requests as google_auth_requests
    from google.oauth2 import id_token

    request = google_auth_requests.Request()
    token: str = id_token.fetch_id_token(request, audience)  # type: ignore[no-untyped-call]
    return token


def build_default_token_provider(audience: str) -> TokenProvider:
    """The default `token_provider`: mints a Google-signed OIDC identity token for this service's
    own runtime service account via the metadata server, audienced to `audience` (the Host's own
    URL). `fetch_id_token` is blocking, so it's run in a thread."""

    async def _provider() -> str:
        return await asyncio.to_thread(_fetch_id_token_blocking, audience)

    return _provider
