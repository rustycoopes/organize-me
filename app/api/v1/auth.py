import secrets
import uuid

import jwt as pyjwt
from fastapi import APIRouter, Cookie, Depends, Form, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from fastapi_users import exceptions
from fastapi_users.authentication import Strategy
from fastapi_users.jwt import generate_jwt, decode_jwt
from httpx_oauth.clients.google import GoogleOAuth2
from httpx_oauth.exceptions import GetIdEmailError
from httpx_oauth.oauth2 import GetAccessTokenError
from pydantic import EmailStr
from sqlalchemy.exc import IntegrityError

from app.auth.backend import COOKIE_SECURE, auth_backend, get_jwt_strategy
from app.auth.oauth import GOOGLE_OAUTH_NAME, get_google_oauth_client
from app.auth.users import UserManager, fastapi_users, get_user_manager
from app.core.config import get_settings
from app.models.user import User
from app.schemas.user import UserCreate, UserRead

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# Same response body regardless of whether the email is registered, so the endpoint
# doesn't leak account existence.
FORGOT_PASSWORD_RESPONSE = {
    "detail": "If that email address is registered, a password reset link has been sent."
}

# Anti-CSRF "state" for the Google OAuth flow: a short-lived signed JWT is embedded in the
# state param sent to Google, and the same random value is set as an HTTPOnly cookie. Only
# someone who both initiated /google (and thus received the cookie) and completed the redirect
# through Google can present both values matching at /google/callback - the same double-submit
# pattern fastapi_users' own get_oauth_router uses internally.
GOOGLE_OAUTH_STATE_AUDIENCE = "organizeme:oauth-state"
GOOGLE_OAUTH_STATE_COOKIE_NAME = "organizeme_oauth_csrf"
GOOGLE_OAUTH_STATE_LIFETIME_SECONDS = 600

# The page the "Sign in with Google" button was clicked from, so a failed/cancelled attempt
# redirects back to the same form instead of always landing on /login. Restricted to a known
# allowlist (not the raw query value) to avoid this becoming an open redirect.
GOOGLE_OAUTH_DEFAULT_NEXT = "/login"
GOOGLE_OAUTH_ALLOWED_NEXT_PATHS = {"/login", "/register"}

# Where a successful Google sign-in lands the browser. /profile is the only authenticated page
# in Slice 1 (it bounces unauthenticated visitors back to /login); repoint this to /dashboard
# once the sidebar shell (issue #17) exists. Kept in sync with the email/password login's
# client-side redirect target in templates/auth/login.html.
GOOGLE_OAUTH_SUCCESS_REDIRECT = "/profile"

# Where a successful email/password login lands the browser. Same target as the Google sign-in
# and login.html's client-side redirect - kept here so the endpoint itself navigates the browser
# (issue #43) instead of depending on that client JS. Repoint to /dashboard alongside
# GOOGLE_OAUTH_SUCCESS_REDIRECT once the dashboard exists.
LOGIN_SUCCESS_REDIRECT = "/profile"


def _sanitize_next(value: object) -> str:
    """Used at both /google (a query param) and /google/callback (a decoded JWT state
    value) - falls back to the default for anything outside the allowlist so this can never
    become an open redirect."""
    return value if isinstance(value, str) and value in GOOGLE_OAUTH_ALLOWED_NEXT_PATHS else GOOGLE_OAUTH_DEFAULT_NEXT


def _redirect_with_login_cookie(login_response: Response, target: str) -> RedirectResponse:
    """Turn fastapi-users' bare-204 cookie login response into a 302 to `target` that still
    carries the auth cookie. A browser following a full-page redirect just renders the bare 204
    as a blank page, stranding the user (email/password login #43; Google callback #27) - so both
    flows navigate the browser themselves instead. Copying the backend's Set-Cookie header(s)
    across keeps the cookie's name/max-age/secure/samesite defined in one place
    (app.auth.backend.cookie_transport)."""
    redirect = RedirectResponse(target, status_code=status.HTTP_302_FOUND)
    for header_name, header_value in login_response.raw_headers:
        if header_name.lower() == b"set-cookie":
            redirect.raw_headers.append((header_name, header_value))
    return redirect


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
    email: EmailStr = Form(...),
    password: str = Form(...),
    user_manager: UserManager = Depends(get_user_manager),
) -> UserRead:
    try:
        user = await user_manager.create(UserCreate(email=email, password=password), safe=True)
    except exceptions.UserAlreadyExists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="REGISTER_USER_ALREADY_EXISTS"
        )
    except exceptions.InvalidPasswordException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "REGISTER_INVALID_PASSWORD", "reason": exc.reason},
        )
    except IntegrityError:
        # Two concurrent registrations for the same email can both pass the pre-insert
        # get_by_email check (Cloud Run runs multiple instances) and race to INSERT; the
        # loser hits the DB's unique index instead of the friendly UserAlreadyExists path.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="REGISTER_USER_ALREADY_EXISTS"
        )
    return UserRead.model_validate(user)


@router.post("/login")
async def login(
    email: EmailStr = Form(...),
    password: str = Form(...),
    user_manager: UserManager = Depends(get_user_manager),
    strategy: Strategy[User, uuid.UUID] = Depends(get_jwt_strategy),
) -> Response:
    try:
        user = await user_manager.get_by_email(email)
    except exceptions.UserNotExists:
        # Hash the submitted password anyway (result discarded) so a request for an unknown
        # email takes about as long as one for a known email with a wrong password - otherwise
        # response timing leaks which emails are registered. Mirrors BaseUserManager.authenticate.
        user_manager.password_helper.hash(password)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="LOGIN_BAD_CREDENTIALS")

    verified, updated_hash = user_manager.password_helper.verify_and_update(
        password, user.hashed_password
    )
    if not verified or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="LOGIN_BAD_CREDENTIALS")
    if updated_hash is not None:
        await user_manager.user_db.update(user, {"hashed_password": updated_hash})

    # auth_backend.login returns fastapi-users' default cookie login response - a bare 204 No
    # Content (issue #43). A plain full-page form POST (JS disabled, or any non-fetch caller) is
    # then left stranded on /login with no navigation; today it only appears to work because
    # login.html's client-side JS does the redirect. Instead 302 to /profile carrying the auth
    # cookie, so the endpoint is correct without relying on client JS - same fix as #27.
    login_response = await auth_backend.login(strategy, user)
    return _redirect_with_login_cookie(login_response, LOGIN_SUCCESS_REDIRECT)


@router.post("/forgot-password")
async def forgot_password(
    request: Request,
    email: EmailStr = Form(...),
    user_manager: UserManager = Depends(get_user_manager),
) -> dict[str, str]:
    try:
        user = await user_manager.get_by_email(email)
    except exceptions.UserNotExists:
        return FORGOT_PASSWORD_RESPONSE

    try:
        await user_manager.forgot_password(user, request)
    except exceptions.UserInactive:
        pass

    return FORGOT_PASSWORD_RESPONSE


@router.post("/reset-password")
async def reset_password(
    token: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    user_manager: UserManager = Depends(get_user_manager),
) -> dict[str, str]:
    if password != confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="RESET_PASSWORD_PASSWORD_MISMATCH"
        )

    try:
        await user_manager.reset_password(token, password)
    except (exceptions.InvalidResetPasswordToken, exceptions.UserNotExists):
        # UserNotExists here means the account the token was issued for no longer exists (e.g.
        # deleted between the forgot-password request and this one) - treated the same as an
        # invalid token rather than surfaced as a distinct case, so this endpoint never reveals
        # whether an account used to exist.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="RESET_PASSWORD_BAD_TOKEN")
    except exceptions.UserInactive:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="RESET_PASSWORD_USER_INACTIVE"
        )
    except exceptions.InvalidPasswordException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "RESET_PASSWORD_INVALID_PASSWORD", "reason": exc.reason},
        )

    return {"detail": "Your password has been reset."}


@router.post("/logout")
async def logout(
    user_token: tuple[User, str] = Depends(fastapi_users.authenticator.current_user_token(active=True)),
    strategy: Strategy[User, uuid.UUID] = Depends(get_jwt_strategy),
) -> Response:
    user, token = user_token
    return await auth_backend.logout(strategy, user, token)


@router.get("/google")
async def google_authorize(
    next_path: str = Query(default=GOOGLE_OAUTH_DEFAULT_NEXT, alias="next"),
    oauth_client: GoogleOAuth2 = Depends(get_google_oauth_client),
) -> RedirectResponse:
    settings = get_settings()
    origin = _sanitize_next(next_path)
    csrf_token = secrets.token_urlsafe(32)
    state = generate_jwt(
        {"csrf": csrf_token, "next": origin, "aud": GOOGLE_OAUTH_STATE_AUDIENCE},
        settings.jwt_secret,
        GOOGLE_OAUTH_STATE_LIFETIME_SECONDS,
    )
    authorization_url = await oauth_client.get_authorization_url(
        settings.google_oauth_redirect_uri, state=state
    )

    response = RedirectResponse(authorization_url, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        GOOGLE_OAUTH_STATE_COOKIE_NAME,
        csrf_token,
        max_age=GOOGLE_OAUTH_STATE_LIFETIME_SECONDS,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
    )
    return response


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    oauth_csrf_cookie: str | None = Cookie(default=None, alias=GOOGLE_OAUTH_STATE_COOKIE_NAME),
    oauth_client: GoogleOAuth2 = Depends(get_google_oauth_client),
    user_manager: UserManager = Depends(get_user_manager),
    strategy: Strategy[User, uuid.UUID] = Depends(get_jwt_strategy),
) -> Response:
    settings = get_settings()

    # Google echoes the original `state` back even on error/cancellation redirects (e.g.
    # error=access_denied when the user clicks "Cancel"), so decode it first to recover which
    # page to send the user back to - falling back to /login only when state is missing/invalid.
    state_data: dict[str, object] = {}
    if state is not None:
        try:
            state_data = decode_jwt(state, settings.jwt_secret, audience=[GOOGLE_OAUTH_STATE_AUDIENCE])
        except pyjwt.PyJWTError:
            state_data = {}

    origin = _sanitize_next(state_data.get("next"))

    def failure_redirect() -> RedirectResponse:
        # A GET endpoint only ever reached via a full-page browser redirect from Google, so a
        # raw 400 JSON body would leave the user staring at an error blob instead of the form
        # they started from - send them back with a query flag the template can show a banner for.
        redirect = RedirectResponse(f"{origin}?error=google_auth_failed", status_code=status.HTTP_302_FOUND)
        redirect.delete_cookie(GOOGLE_OAUTH_STATE_COOKIE_NAME)
        return redirect

    if error is not None or code is None or not state_data:
        return failure_redirect()

    csrf_from_state = str(state_data.get("csrf", ""))
    # secrets.compare_digest raises TypeError on non-ASCII input rather than returning False;
    # oauth_csrf_cookie is attacker-controlled (a raw HTTP client can set any Cookie header
    # value on a direct request to this endpoint, not just a real browser round-tripping our
    # Set-Cookie), so reject non-ASCII values up front instead of comparing them.
    if (
        not oauth_csrf_cookie
        or not oauth_csrf_cookie.isascii()
        or not secrets.compare_digest(oauth_csrf_cookie, csrf_from_state)
    ):
        return failure_redirect()

    try:
        token = await oauth_client.get_access_token(code, settings.google_oauth_redirect_uri)
        account_id, account_email = await oauth_client.get_id_email(token["access_token"])
    except (GetAccessTokenError, GetIdEmailError):
        # Google rejected the exchange - e.g. the authorization code was already used or has
        # expired (a reloaded/replayed callback URL), or a transient Google-side error.
        return failure_redirect()
    if account_email is None:
        return failure_redirect()

    try:
        user = await user_manager.oauth_callback(
            GOOGLE_OAUTH_NAME,
            token["access_token"],
            account_id,
            account_email,
            token.get("expires_at"),
            token.get("refresh_token"),
            request,
            # A user who already registered with email/password and then signs in with Google
            # using the same address gets the Google account linked to their existing user
            # rather than a rejected/duplicate signup - see issue #13 discussion and the
            # Authentication section of docs/features/original-organize-me/technical-approach.md.
            associate_by_email=True,
            # Google has already verified this email address as part of its own OAuth consent
            # flow, so there's no need to make the user re-verify it with us.
            is_verified_by_default=True,
        )
    except exceptions.UserAlreadyExists:
        return failure_redirect()
    except IntegrityError:
        # Two concurrent first-time Google logins for the same email can both pass
        # oauth_callback's pre-insert existence checks and race to INSERT (same class of race
        # register() guards against above - see its comment for the Cloud Run multi-instance
        # explanation).
        return failure_redirect()

    if not user.is_active:
        return failure_redirect()

    # This endpoint is only ever reached via a full-page browser redirect from Google, so the
    # success response has to navigate the browser back into the app itself - a bare 204 would
    # leave the user stranded on Google's consent page (issue #27). 302 to /profile carrying the
    # auth cookie (shared with the email/password login #43), then clear the one-shot CSRF state
    # cookie.
    login_response = await auth_backend.login(strategy, user)
    redirect = _redirect_with_login_cookie(login_response, GOOGLE_OAUTH_SUCCESS_REDIRECT)
    redirect.delete_cookie(GOOGLE_OAUTH_STATE_COOKIE_NAME)
    return redirect
