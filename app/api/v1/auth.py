import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from fastapi_users import exceptions
from fastapi_users.authentication import Strategy
from pydantic import EmailStr
from sqlalchemy.exc import IntegrityError

from app.auth.backend import auth_backend, get_jwt_strategy
from app.auth.users import UserManager, fastapi_users, get_user_manager
from app.models.user import User
from app.schemas.user import UserCreate, UserRead

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# Same response body regardless of whether the email is registered, so the endpoint
# doesn't leak account existence.
FORGOT_PASSWORD_RESPONSE = {
    "detail": "If that email address is registered, a password reset link has been sent."
}


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

    return await auth_backend.login(strategy, user)


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
