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

cookie_transport = CookieTransport(
    cookie_name="organizeme_auth",
    cookie_max_age=COOKIE_MAX_AGE_SECONDS,
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
