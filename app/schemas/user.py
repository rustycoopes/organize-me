import uuid

from fastapi_users import schemas
from pydantic import EmailStr, Field, field_validator


class UserRead(schemas.BaseUser[uuid.UUID]):
    name: str | None = None
    phone_number: str | None = None
    dark_mode: bool = False


class UserCreate(schemas.BaseUserCreate):
    pass


# Deliberately does NOT inherit from schemas.BaseUserUpdate: that base class carries
# password/is_active/is_superuser/is_verified fields, which would let a client sneak a
# privilege-escalation change through this profile-only PATCH endpoint. Inheriting from
# CreateUpdateDictModel (BaseUserUpdate's own base) keeps create_update_dict()'s
# exclude_unset=True semantics for partial updates without exposing any of that.
class UserUpdate(schemas.CreateUpdateDictModel):
    # Neither the `users` table nor its Alembic migration bound these columns to a length
    # (plain `sa.String()`), so nothing upstream stops an unbounded payload without these.
    name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = None
    phone_number: str | None = Field(default=None, max_length=32)
    dark_mode: bool | None = None

    # email and dark_mode back NOT NULL columns (users.email, users.dark_mode); they're typed
    # Optional only so exclude_unset=True can tell "omitted" from "provided" for a partial PATCH.
    # Without this guard, an explicit `{"email": null}` (or `{"dark_mode": null}`) sails through
    # pydantic, reaches BaseUserManager._update()/user_db.update(), and only fails at the DB's
    # NOT NULL constraint - surfacing as an IntegrityError that app/api/v1/users.py's handler
    # mislabels as "email already exists" regardless of which field actually caused it. Rejecting
    # the null here turns that into an immediate, correctly-described 422 instead.
    @field_validator("email", "dark_mode")
    @classmethod
    def _reject_explicit_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("must not be null")
        return value
