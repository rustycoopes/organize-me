import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi_users import exceptions
from fastapi_users.authentication import Strategy
from sqlalchemy.exc import IntegrityError

from app.auth.backend import auth_backend, get_jwt_strategy
from app.auth.users import UserManager, current_active_user, fastapi_users, get_user_manager
from app.models.user import User
from app.schemas.user import UserRead, UserUpdate

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def read_current_user(user: User = Depends(current_active_user)) -> UserRead:
    return UserRead.model_validate(user)


@router.patch("/me", response_model=UserRead)
async def update_current_user(
    update: UserUpdate,
    user: User = Depends(current_active_user),
    user_manager: UserManager = Depends(get_user_manager),
) -> UserRead:
    try:
        # UserUpdate deliberately doesn't inherit schemas.BaseUserUpdate (see its docstring), so
        # it doesn't satisfy BaseUserManager.update()'s UU TypeVar bound under mypy - it still
        # satisfies the runtime contract update() actually needs (create_update_dict() + the
        # profile fields), which is the whole point of that design choice.
        updated_user = await user_manager.update(update, user, safe=True)  # type: ignore[type-var]
    except (exceptions.UserAlreadyExists, IntegrityError):
        # IntegrityError case: same concurrent-request race as register() in app/api/v1/auth.py -
        # two PATCHes to the same new email can both pass the pre-update uniqueness check and race
        # to commit, so the loser hits the DB's unique index instead of the friendly pre-check.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="UPDATE_USER_EMAIL_ALREADY_EXISTS"
        )
    return UserRead.model_validate(updated_user)


@router.delete("/me")
async def delete_current_user(
    user_token: tuple[User, str] = Depends(
        fastapi_users.authenticator.current_user_token(active=True)
    ),
    user_manager: UserManager = Depends(get_user_manager),
    strategy: Strategy[User, uuid.UUID] = Depends(get_jwt_strategy),
) -> Response:
    user, token = user_token
    await user_manager.delete(user)
    return await auth_backend.logout(strategy, user, token)
