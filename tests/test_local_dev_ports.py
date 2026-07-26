"""infra/local_dev/ports.py: unit tested as a pure function of its environment - given a
constructed env var, resolve the Caddy listen port to use - no real filesystem/subprocess
dependency, mirroring tests/test_path_rules.py's constructed-input style.
"""

import importlib

import pytest

from infra.local_dev import ports as ports_module


def test_organizeme_defaults_to_port_8000() -> None:
    assert ports_module.PORTS["organizeme"] == 8000


def test_caddy_local_port_defaults_to_10000(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CADDY_LOCAL_PORT", raising=False)

    reloaded = importlib.reload(ports_module)

    assert reloaded.CADDY_LOCAL_PORT == 10000


def test_caddy_local_port_overridable_via_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CADDY_LOCAL_PORT", "9999")

    reloaded = importlib.reload(ports_module)

    try:
        assert reloaded.CADDY_LOCAL_PORT == 9999
    finally:
        monkeypatch.delenv("CADDY_LOCAL_PORT", raising=False)
        importlib.reload(ports_module)
