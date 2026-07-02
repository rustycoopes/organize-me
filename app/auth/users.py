import logging
import uuid
from collections.abc import AsyncIterator

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin, exceptions, schemas
from fastapi_users.password import PasswordHelper
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.backend import auth_backend
from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import User
from app.services.notifications.email import EmailSender, ResendEmailSender

# fastapi-users defaults to Argon2 for newly-hashed passwords; docs/technical-approach.md and
# issue #12 both specify bcrypt, so this app is pinned to a bcrypt-only PasswordHash.
bcrypt_password_helper = PasswordHelper(PasswordHash((BcryptHasher(),)))

MIN_PASSWORD_LENGTH = 8

logger = logging.getLogger(__name__)


async def get_user_db(
    session: AsyncSession = Depends(get_db),
) -> AsyncIterator[SQLAlchemyUserDatabase[User, uuid.UUID]]:
    yield SQLAlchemyUserDatabase(session, User)


def get_email_sender() -> EmailSender:
    return ResendEmailSender()


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    def __init__(
        self,
        user_db: SQLAlchemyUserDatabase[User, uuid.UUID],
        email_sender: EmailSender,
    ) -> None:
        super().__init__(user_db, password_helper=bcrypt_password_helper)
        # Verification token secret; the verify-email flow lands in a later slice, but
        # BaseUserManager requires the attribute to exist regardless.
        secret = get_settings().jwt_secret
        self.reset_password_token_secret = secret
        self.verification_token_secret = secret
        self.email_sender = email_sender

    async def validate_password(self, password: str, user: schemas.UC | User) -> None:
        if len(password) < MIN_PASSWORD_LENGTH:
            raise exceptions.InvalidPasswordException(
                reason=f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
            )

    async def on_after_forgot_password(
        self, user: User, token: str, request: Request | None = None
    ) -> None:
        # Building the link from the incoming request's host (rather than a static
        # BASE_URL setting) means it's correct on both the QA and prod Cloud Run domains
        # without extra per-environment config.
        origin = str(request.base_url).rstrip("/") if request is not None else ""
        reset_link = f"{origin}/reset-password?token={token}"
        try:
            await self.email_sender.send(
                to=user.email,
                subject="Reset your OrganizeMe password",
                html=(
                    "<p>We received a request to reset your OrganizeMe password.</p>"
                    f'<p><a href="{reset_link}">Reset your password</a></p>'
                    "<p>This link expires in 1 hour. If you didn't request this, you can "
                    "safely ignore this email.</p>"
                ),
            )
        except Exception:
            # A delivery failure (bad/missing RESEND_API_KEY, Resend outage, etc.) must not
            # propagate into the forgot-password endpoint: letting it raise would turn into a
            # 500 for known emails only, distinguishing them from the unknown-email 200 path
            # and defeating the account-enumeration protection that endpoint's response is
            # designed to provide.
            logger.exception("Failed to send password reset email to user %s", user.id)


async def get_user_manager(
    user_db: SQLAlchemyUserDatabase[User, uuid.UUID] = Depends(get_user_db),
    email_sender: EmailSender = Depends(get_email_sender),
) -> AsyncIterator[UserManager]:
    yield UserManager(user_db, email_sender)


fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])
current_active_user = fastapi_users.current_user(active=True)
