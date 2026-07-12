import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi_users import exceptions
from fastapi_users.authentication import Strategy
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.backend import auth_backend, get_jwt_strategy
from app.auth.users import UserManager, current_active_user, fastapi_users, get_user_manager
from app.db.session import get_db
from app.models.user import User
from app.models.user_settings import UserSettings
from app.schemas.user import UserRead, UserUpdate
from app.services.user_settings import get_or_create_user_settings

router = APIRouter(prefix="/api/v1/users", tags=["users"])


def _to_user_read(user: User, settings: UserSettings) -> UserRead:
    """Builds UserRead explicitly from both objects, rather than relying on
    UserRead.model_validate(user)'s attribute-fallback-to-default behaviour (pydantic v2 falls
    back to a field's default when `from_attributes` getattr fails) - notification_email/
    notification_sms no longer live on `User`, and silently reporting the schema defaults instead
    of the real UserSettings values would be a correctness bug (e.g. a user who disabled
    notifications would see them reported as enabled).
    """
    return UserRead(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        is_verified=user.is_verified,
        name=user.name,
        phone_number=user.phone_number,
        dark_mode=user.dark_mode,
        notification_email=settings.notification_email,
        notification_sms=settings.notification_sms,
    )


@router.get("/me", response_model=UserRead)
async def read_current_user(
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    settings = await get_or_create_user_settings(db, user.id)
    return _to_user_read(user, settings)


@router.patch("/me", response_model=UserRead)
async def update_current_user(
    update: UserUpdate,
    user: User = Depends(current_active_user),
    user_manager: UserManager = Depends(get_user_manager),
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    fields_set = update.model_fields_set
    notification_fields = fields_set & {"notification_email", "notification_sms"}

    # Only pass the remaining (non-settings) fields through to fastapi-users' generic update, so
    # it never sees notification_email/notification_sms (User no longer has those columns).
    core_updates = {
        k: v
        for k, v in update.model_dump(exclude_unset=True).items()
        if k not in {"notification_email", "notification_sms"}
    }
    core_update = UserUpdate(**core_updates)
    try:
        # UserUpdate deliberately doesn't inherit schemas.BaseUserUpdate (see its docstring), so
        # it doesn't satisfy BaseUserManager.update()'s UU TypeVar bound under mypy - it still
        # satisfies the runtime contract update() actually needs (create_update_dict() + the
        # profile fields), which is the whole point of that design choice.
        updated_user = await user_manager.update(core_update, user, safe=True)  # type: ignore[type-var]
    except (exceptions.UserAlreadyExists, IntegrityError):
        # IntegrityError case: same concurrent-request race as register() in app/api/v1/auth.py -
        # two PATCHes to the same new email can both pass the pre-update uniqueness check and race
        # to commit, so the loser hits the DB's unique index instead of the friendly pre-check.
        #
        # Raised (and the whole PATCH rejected) BEFORE touching UserSettings below on purpose: a
        # client PATCHing a conflicting email alongside notification-field changes must not have
        # the notification/onboarding half silently persist while the response reports failure.
        # Sequencing the core update first - rather than committing UserSettings early and hoping
        # a later failure rolls it back - makes that atomicity guarantee explicit and independent
        # of session-lifecycle/rollback-on-exception details.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="UPDATE_USER_EMAIL_ALREADY_EXISTS"
        )

    # Saving notification prefs (issue #88) flips the onboarding flag the first time - and every
    # time after, harmlessly, since there's no un-toggling this step once it's done. These fields
    # now live on UserSettings (event_creator.user_settings), not on User (#158 / Slice R2).
    settings = await get_or_create_user_settings(db, user.id)
    if notification_fields:
        if "notification_email" in notification_fields:
            # UserUpdate's `_reject_explicit_null` validator guarantees this is non-None whenever
            # the field was actually set; the `bool | None` annotation only exists so
            # exclude_unset=True can distinguish "omitted" from "provided".
            assert update.notification_email is not None
            settings.notification_email = update.notification_email
        if "notification_sms" in notification_fields:
            assert update.notification_sms is not None
            settings.notification_sms = update.notification_sms
        if not settings.onboarding_notifications_done:
            settings.onboarding_notifications_done = True
        await db.commit()
    return _to_user_read(updated_user, settings)


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
