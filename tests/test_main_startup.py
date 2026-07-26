"""Tests for the `registry_local_dev_bypass` fail-safe startup guard (local-dev-environment
Slice 3, organize-me#266) - `app/main.py`'s `_reject_registry_bypass_on_cloud_run`. Mirrors
`tests/test_internal_registry.py`'s bypass-inertness tests for the endpoint-level half of this
same fail-safe.
"""

from collections.abc import Iterator

import pytest

from app.core.config import get_settings
from app.main import _reject_registry_bypass_on_cloud_run


@pytest.fixture(autouse=True)
def _configure_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/testdb")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("GOOGLE_OAUTH_REDIRECT_URI", "http://localhost/api/v1/auth/google/callback")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_raises_when_bypass_is_on_and_k_service_is_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REGISTRY_LOCAL_DEV_BYPASS", "true")
    monkeypatch.setenv("K_SERVICE", "organize-me")
    get_settings.cache_clear()

    with pytest.raises(RuntimeError, match="registry_local_dev_bypass"):
        _reject_registry_bypass_on_cloud_run(get_settings())


def test_does_not_raise_when_bypass_is_on_and_k_service_is_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REGISTRY_LOCAL_DEV_BYPASS", "true")
    monkeypatch.delenv("K_SERVICE", raising=False)
    get_settings.cache_clear()

    _reject_registry_bypass_on_cloud_run(get_settings())


def test_does_not_raise_when_bypass_is_off_and_k_service_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REGISTRY_LOCAL_DEV_BYPASS", "false")
    monkeypatch.setenv("K_SERVICE", "organize-me")
    get_settings.cache_clear()

    _reject_registry_bypass_on_cloud_run(get_settings())
