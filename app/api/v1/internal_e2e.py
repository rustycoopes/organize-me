"""Test-only endpoints that exist purely to support the Playwright E2E suite (issue #23).

Every route here is gated behind the ``E2E_TEST_MODE`` setting, which must **only** ever be
set true on QA's Cloud Run service - never prod. When the flag is off (the default), the gate
dependency raises 404 rather than 401/403 so the endpoints' very existence stays hidden, and
the router is excluded from the OpenAPI schema. The router is always mounted (rather than
conditionally at startup) so its behaviour is deterministic and unit-testable; the flag alone
controls reachability.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi_users import exceptions
from fastapi_users.jwt import generate_jwt
from pydantic import EmailStr

from app.auth.users import UserManager, get_user_manager
from app.core.config import Settings, get_settings

router = APIRouter(prefix="/api/v1/internal/e2e", tags=["e2e-internal"], include_in_schema=False)


def require_e2e_mode(settings: Settings = Depends(get_settings)) -> None:
    """Gate for every route in this module. Returns 404 (indistinguishable from a route that
    doesn't exist) when E2E_TEST_MODE is off, so these test hooks leak nothing in prod."""
    if not settings.e2e_test_mode:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@router.get("/last-reset-token", dependencies=[Depends(require_e2e_mode)])
async def last_reset_token(
    email: EmailStr = Query(...),
    user_manager: UserManager = Depends(get_user_manager),
) -> dict[str, str]:
    """Mint a currently-valid password-reset token for a registered email.

    fastapi-users reset tokens are stateless, signed JWTs (nothing is stored server-side), so
    "the most recent unexpired token" is simply a freshly-signed one built exactly as
    ``BaseUserManager.forgot_password`` builds it. This lets the E2E test complete the
    forgot -> reset flow without reading a real inbox. Unknown emails 404 (same as the gate)
    rather than confirming which addresses aren't registered.
    """
    try:
        user = await user_manager.get_by_email(email)
    except exceptions.UserNotExists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    token = generate_jwt(
        {
            "sub": str(user.id),
            "password_fgpt": user_manager.password_helper.hash(user.hashed_password),
            "aud": user_manager.reset_password_token_audience,
        },
        user_manager.reset_password_token_secret,
        user_manager.reset_password_token_lifetime_seconds,
    )
    return {"token": token}
