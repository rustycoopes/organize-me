"""``GET /internal/app-registry.json`` - registry-decoupling (organize-me#218).

Serves the Host's own in-process app-registry (`app/core/registry.py`'s `APPS`) as JSON so every
other hosted-app consumer (event-creator, doc-library, ...) can fetch it into a background-
refreshed cache instead of carrying a build-time pin of the data - see
docs/features/registry-decoupling/PRD.md.

Not registered under the versioned `/api/v1` prefix - this isn't a public API surface for any
client, versioned or not, matching `app/api/v1/internal_e2e.py`'s and event-creator's
`app/api/v1/internal_pipeline.py`'s existing internal-route convention.

Auth mirrors `internal_pipeline.py`'s `_verify_push_token`: the service stays
`--allow-unauthenticated` overall, and this one route verifies a Google-signed OIDC token's `aud`
+`email` claims in application code rather than relying on Cloud Run's IAM invoker gate - see
docs/adr/registry-decoupling-endpoint-auth.md for the full rationale.
"""

import logging

import cachecontrol
import requests
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from google.auth.transport import requests as google_auth_requests

# Explicit self-referential re-export (`as id_token`, not a plain `import`) so mypy's strict
# no-implicit-reexport check allows tests to monkeypatch
# `registry_module.id_token.verify_oauth2_token` rather than reaching into google.oauth2 directly
# - mirrors event-creator's app/api/v1/internal_pipeline.py.
from google.oauth2 import id_token as id_token
from pydantic import TypeAdapter

from app.core.config import Settings, get_settings
from app.core.registry import APPS
from organizeme_chrome.registry import AppEntry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["internal"])

# Built once at import, not per-request - the registry only changes when this service redeploys.
_APPS_ADAPTER: TypeAdapter[list[AppEntry]] = TypeAdapter(list[AppEntry])

# See internal_pipeline.py's identical comment: caches Google's public certs per their own
# Cache-Control headers instead of an extra network round trip on every single request.
_google_auth_request = google_auth_requests.Request(
    session=cachecontrol.CacheControl(requests.Session())
)


def _verify_registry_read_token(request: Request, settings: Settings = Depends(get_settings)) -> None:
    """Reject anything but a Google-signed OIDC token minted for exactly this deployment's own
    audience URL, by exactly the platform's shared runtime service account.

    Checks both the token's signature/expiry (verified against Google's public certs by
    `id_token.verify_oauth2_token`) and that its `aud`/`email` claims match what this deployment
    expects; a token that's validly signed but minted for a different audience or service account
    must not be accepted here."""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing_token")
    token = auth_header.removeprefix("Bearer ")

    if not settings.registry_endpoint_url or not settings.registry_invoker_service_account:
        # Not wired yet in this environment (e.g. local dev) - fail closed rather than silently
        # accepting unauthenticated reads.
        logger.error("registry endpoint: OIDC verification not configured")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="not_configured")

    try:
        claims = id_token.verify_oauth2_token(  # type: ignore[no-untyped-call]
            token, _google_auth_request, audience=settings.registry_endpoint_url
        )
    except Exception:
        logger.exception("registry endpoint: OIDC token verification failed")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token") from None

    if claims.get("email") != settings.registry_invoker_service_account:
        logger.error(
            "registry endpoint: token email %r does not match expected invoker",
            claims.get("email"),
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="wrong_identity")


@router.get(
    "/app-registry.json",
    dependencies=[Depends(_verify_registry_read_token)],
)
async def get_app_registry() -> Response:
    # Pydantic v2's native dataclass support serializes AppEntry (and its nested AppNavItem/
    # SettingsTab) directly, so the wire shape matches organizeme_chrome's own dataclasses with
    # no hand-maintained duplicate schema on either side.
    return Response(content=_APPS_ADAPTER.dump_json(APPS), media_type="application/json")
