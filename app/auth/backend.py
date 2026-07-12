import os
import uuid

from fastapi_users.authentication import AuthenticationBackend, CookieTransport, JWTStrategy

from app.core.config import get_settings
from app.models.user import User

# 7-day cookie/token lifetime per docs/implementation-plan.md.
COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 7

# cookie_secure defaults to True: Cloud Run terminates TLS at the edge in prod, and modern
# browsers treat http://localhost as a secure context, so Secure cookies work fine in local
# browser-based dev too. It only needs to be false for non-browser HTTP clients hitting a plain
# http:// origin (e.g. httpx in the test suite - see tests/conftest.py), which don't get
# browsers' localhost exception and would silently drop the cookie on the next request.
# A plain os.environ read (not the pydantic Settings class) so importing this module never
# requires DATABASE_URL/JWT_SECRET to be resolved - this backend is built once at import time,
# before any request-scoped settings lookup would normally happen.
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "true").strip().lower() != "false"

# Unset (None) by default - the cookie stays implicitly host-scoped, exactly as it behaves today.
# Slice R4 (SSO prep): once the shared origin actually serves this app (R0 DNS cutover + R5 Load
# Balancer), set COOKIE_DOMAIN to the per-environment origin host (organizeme.russcoopersoftware.com
# in prod, organizeme.qa.russcoopersoftware.com in QA) so the auth cookie rides across the second
# hosted service (R6). Must be the exact host, never a leading-dot parent domain, so the cookie is
# never sent to the main Squarespace site. Deliberately NOT flipped on for QA/prod yet: until the
# origin host actually resolves to this service, a cookie scoped to it would never be sent back by
# the browser to the *.run.app host the service is still reachable at, breaking login.
COOKIE_DOMAIN = os.environ.get("COOKIE_DOMAIN", "").strip() or None

cookie_transport = CookieTransport(
    cookie_name="organizeme_auth",
    cookie_max_age=COOKIE_MAX_AGE_SECONDS,
    cookie_domain=COOKIE_DOMAIN,
    cookie_secure=COOKIE_SECURE,
    cookie_httponly=True,
    cookie_samesite="lax",
)


def get_jwt_strategy() -> JWTStrategy[User, uuid.UUID]:
    # A function (not a module-level value) so get_settings() - and therefore JWT_SECRET
    # resolution - is deferred until a request actually depends on it, not at import time.
    return JWTStrategy(secret=get_settings().jwt_secret, lifetime_seconds=COOKIE_MAX_AGE_SECONDS)


auth_backend: AuthenticationBackend[User, uuid.UUID] = AuthenticationBackend(
    name="jwt",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)
