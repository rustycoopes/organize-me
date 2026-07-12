import time

import jwt
import pytest

from organizeme_chrome.jwt_verify import ALGORITHM, TOKEN_AUDIENCE, InvalidTokenError, verify_token

SECRET = "test-secret"


def make_token(sub: str = "user-123", secret: str = SECRET, **overrides: object) -> str:
    payload: dict[str, object] = {
        "sub": sub,
        "aud": TOKEN_AUDIENCE,
        "exp": int(time.time()) + 3600,
    }
    payload.update(overrides)
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def test_verify_token_accepts_a_valid_token() -> None:
    token = make_token(sub="user-123")

    assert verify_token(token, SECRET) == "user-123"


def test_verify_token_rejects_a_tampered_signature() -> None:
    token = make_token(secret="wrong-secret")

    with pytest.raises(InvalidTokenError):
        verify_token(token, SECRET)


def test_verify_token_rejects_an_expired_token() -> None:
    token = make_token(exp=int(time.time()) - 3600)

    with pytest.raises(InvalidTokenError):
        verify_token(token, SECRET)


def test_verify_token_rejects_wrong_audience() -> None:
    token = make_token(aud="some-other-audience")

    with pytest.raises(InvalidTokenError):
        verify_token(token, SECRET)


def test_verify_token_rejects_missing_sub_claim() -> None:
    payload = {"aud": TOKEN_AUDIENCE, "exp": int(time.time()) + 3600}
    token = jwt.encode(payload, SECRET, algorithm=ALGORITHM)

    with pytest.raises(InvalidTokenError):
        verify_token(token, SECRET)


def test_verify_token_does_not_import_fastapi_users() -> None:
    import sys

    assert "fastapi_users" not in sys.modules
