"""Slice R4: the auth cookie's Domain attribute is sourced from COOKIE_DOMAIN, read once at
module import (same pattern as COOKIE_SECURE — see app/auth/backend.py). Reload the module under
patched env vars to exercise both the default (no COOKIE_DOMAIN set - today's host-only cookie,
unchanged behaviour) and explicit-domain cases without touching the process-wide conftest env.
"""

import importlib
from collections.abc import Generator
from types import ModuleType

import pytest

import app.auth.backend as backend_module


@pytest.fixture(autouse=True)
def _restore_backend_module() -> Generator[None]:
    # Each test below reloads app.auth.backend under a patched COOKIE_DOMAIN, which mutates the
    # shared module object in sys.modules. Reload it back to the default (unset) state afterwards
    # so a later test file that imports app.auth.backend fresh doesn't inherit a patched cookie
    # domain from whichever test ran last here.
    yield
    importlib.reload(backend_module)


def _reload_backend_with_env(
    monkeypatch: pytest.MonkeyPatch, *, cookie_domain: str | None
) -> ModuleType:
    if cookie_domain is None:
        monkeypatch.delenv("COOKIE_DOMAIN", raising=False)
    else:
        monkeypatch.setenv("COOKIE_DOMAIN", cookie_domain)
    return importlib.reload(backend_module)


def test_cookie_domain_defaults_to_none_when_env_var_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    reloaded = _reload_backend_with_env(monkeypatch, cookie_domain=None)

    assert reloaded.COOKIE_DOMAIN is None
    assert reloaded.cookie_transport.cookie_domain is None


def test_cookie_domain_blank_env_var_is_treated_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    reloaded = _reload_backend_with_env(monkeypatch, cookie_domain="   ")

    assert reloaded.COOKIE_DOMAIN is None
    assert reloaded.cookie_transport.cookie_domain is None


def test_cookie_domain_set_from_env_var_is_applied_to_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reloaded = _reload_backend_with_env(
        monkeypatch, cookie_domain="organizeme.qa.russcoopersoftware.com"
    )

    assert reloaded.COOKIE_DOMAIN == "organizeme.qa.russcoopersoftware.com"
    assert reloaded.cookie_transport.cookie_domain == "organizeme.qa.russcoopersoftware.com"
