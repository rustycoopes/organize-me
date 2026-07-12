"""Standalone JWT verification: signature + expiry only, no login/password handling.

Mirrors what fastapi_users.authentication.strategy.JWTStrategy checks on read (HS256,
audience "fastapi-users:auth", PyJWT under the hood) so a Host-issued cookie token verifies
identically here — but with no fastapi-users import and no network/DB call, so a hosted app
(Event Creator, R6) can depend on this helper alone for identity.
"""

import jwt

TOKEN_AUDIENCE = "fastapi-users:auth"
ALGORITHM = "HS256"


class InvalidTokenError(Exception):
    """Raised when a token's signature is invalid, it is expired, or otherwise malformed."""


def verify_token(token: str, secret: str) -> str:
    """Verify `token`'s signature and expiry and return the subject (user id) it encodes.

    Raises InvalidTokenError for a tampered signature, expired token, missing/invalid
    audience, or a missing `sub` claim.
    """
    try:
        payload = jwt.decode(
            token, secret, audience=TOKEN_AUDIENCE, algorithms=[ALGORITHM]
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc

    subject = payload.get("sub")
    if subject is None:
        raise InvalidTokenError("token has no 'sub' claim")
    return str(subject)
