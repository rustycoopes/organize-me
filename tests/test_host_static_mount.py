"""Regression coverage for a bug caught live on QA while shipping static-asset-routing Slice 3
(organize-me#255): organizeme_chrome's shared chrome_base.html (chrome-v0.18.0+) unconditionally
links its stylesheet via CHROME_STATIC_PREFIX, which register_chrome(app_service_name="organizeme")
(app/core/templating.py) sets to static_mount_path("organizeme") - the Host's own authenticated
pages request that prefixed path even though the Host was never meant to migrate off bare
/static/*. Without a matching mount, every authenticated page's CSS 404s (see app/main.py's
dual-mount comment).
"""

import re
import uuid

from httpx import AsyncClient
from organizeme_chrome.static_paths import static_mount_path


def unique_email() -> str:
    return f"host-static-mount-test-{uuid.uuid4().hex}@example.com"


async def test_authenticated_page_stylesheet_link_resolves_to_a_mounted_path(
    client: AsyncClient,
) -> None:
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})

    response = await client.get("/profile")
    assert response.status_code == 200

    match = re.search(r'href="([^"]+/css/app\.css[^"]*)"', response.text)
    assert match is not None, "expected chrome_base.html's stylesheet <link> in the response"
    stylesheet_href = match.group(1)

    css_response = await client.get(stylesheet_href)
    assert css_response.status_code == 200


async def test_host_serves_static_assets_at_both_the_bare_and_prefixed_mount() -> None:
    # Not just "chrome_base.html happens to work" above - lock in that both mounts exist
    # independently, since the bare one is permanent (organize-me's own direct requests, and the
    # LB's defaultService fallback) while the prefixed one exists only to satisfy chrome_base.html.
    from app.main import app

    mounted_paths = {route.path for route in app.routes if hasattr(route, "path")}
    assert any(path.startswith("/static") for path in mounted_paths)
    assert any(path.startswith(static_mount_path("organizeme")) for path in mounted_paths)
