import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Response, status
from fastapi_users import exceptions
from fastapi_users.authentication import Strategy
from pydantic import EmailStr
from sqlalchemy.exc import IntegrityError

from app.auth.backend import auth_backend, get_jwt_strategy
from app.auth.users import UserManager, fastapi_users, get_user_manager
from app.models.user import User
from app.schemas.user import UserCreate, UserRead

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


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


@router.post("/logout")
async def logout(
    user_token: tuple[User, str] = Depends(fastapi_users.authenticator.current_user_token(active=True)),
    strategy: Strategy[User, uuid.UUID] = Depends(get_jwt_strategy),
) -> Response:
    user, token = user_token
    return await auth_backend.logout(strategy, user, token)
