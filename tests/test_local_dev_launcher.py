"""scripts/local_dev.py: unit tests for its pure functions — repo-path resolution and the
generic non-Host subprocess env-var injection — with constructed inputs, no real filesystem/
subprocess/network dependency. Mirrors tests/test_path_rules.py's constructed-input style; see
docs/features/local-dev-environment/WBS/slice-2-launcher-and-proxy-host-only.md "Testing".
"""

from pathlib import Path

import pytest

import scripts.local_dev as local_dev
from scripts.local_dev import (
    REPO_ROOT,
    _select_non_host_services,
    host_subprocess_env,
    non_host_subprocess_env,
    resolve_repo_path,
)


def test_organizeme_resolves_to_this_launchers_own_repo() -> None:
    assert resolve_repo_path("organizeme") == REPO_ROOT


def test_non_host_app_resolves_to_a_sibling_directory_by_default() -> None:
    assert resolve_repo_path("event-creator", env={}) == REPO_ROOT.parent / "event-creator"


def test_non_host_app_resolution_is_overridable_via_env_var() -> None:
    custom_path = str(Path("C:/worktrees/event-creator-feature-x"))

    resolved = resolve_repo_path("event-creator", env={"EVENT_CREATOR_REPO_PATH": custom_path})

    assert resolved == Path(custom_path)


def test_hyphenated_service_name_maps_to_underscored_env_var() -> None:
    resolved = resolve_repo_path("doc-library", env={"DOC_LIBRARY_REPO_PATH": "/tmp/doc-library"})

    assert resolved == Path("/tmp/doc-library")


def test_host_subprocess_env_only_sets_port() -> None:
    env = host_subprocess_env({"organizeme": 8000}, base_env={})

    assert env == {"PORT": "8000"}


def test_non_host_subprocess_env_sets_all_three_generic_vars() -> None:
    # Applied to *any* non-Host app the launcher starts, independent of whether that app's own
    # Settings class reads them yet (Slices 4/6/7 add the consumer-side wiring later).
    env = non_host_subprocess_env(
        "event-creator", {"organizeme": 8000, "event-creator": 8001}, base_env={}
    )

    assert env == {
        "PORT": "8001",
        "REGISTRY_LOCAL_DEV_BYPASS": "true",
        "REGISTRY_HOST_URL": "http://localhost:8000",
    }


def test_non_host_subprocess_env_preserves_unrelated_base_env_vars() -> None:
    env = non_host_subprocess_env(
        "doc-library",
        {"organizeme": 8000, "doc-library": 8002},
        base_env={"PATH": "/usr/bin", "SOME_OTHER_VAR": "1"},
    )

    assert env["PATH"] == "/usr/bin"
    assert env["SOME_OTHER_VAR"] == "1"
    assert env["PORT"] == "8002"
    assert env["REGISTRY_LOCAL_DEV_BYPASS"] == "true"
    assert env["REGISTRY_HOST_URL"] == "http://localhost:8000"


def _stub_repo_with_dev_py(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, service_name: str) -> Path:
    """Makes resolve_repo_path(service_name) resolve to a throwaway directory containing a
    scripts/dev.py, so _select_non_host_services' upfront existence check passes without
    depending on a real sibling checkout being present."""
    repo_path = tmp_path / service_name
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "scripts" / "dev.py").write_text("")

    def fake_resolve(name: str) -> Path:
        assert name == service_name
        return repo_path

    monkeypatch.setattr(local_dev, "resolve_repo_path", fake_resolve)
    return repo_path


def test_select_non_host_services_returns_explicit_apps_list_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(local_dev, "PORTS", {"organizeme": 8000, "event-creator": 8001})
    _stub_repo_with_dev_py(tmp_path, monkeypatch, "event-creator")

    result = _select_non_host_services(["event-creator"])

    assert result == ["event-creator"]


def test_select_non_host_services_drops_organizeme_since_host_always_starts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(local_dev, "PORTS", {"organizeme": 8000, "event-creator": 8001})
    _stub_repo_with_dev_py(tmp_path, monkeypatch, "event-creator")

    result = _select_non_host_services(["organizeme", "event-creator"])

    assert result == ["event-creator"]


def test_select_non_host_services_exits_with_actionable_error_for_unknown_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(local_dev, "PORTS", {"organizeme": 8000})

    with pytest.raises(SystemExit):
        _select_non_host_services(["not-a-real-app"])


def test_select_non_host_services_exits_with_actionable_error_when_repo_not_checked_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Regression: an explicitly-requested app whose repo/scripts/dev.py isn't actually present
    # must fail fast, before the Host (or any earlier --apps entry) gets started - otherwise a
    # crash here would leave already-started subprocesses orphaned with nothing to clean them up.
    monkeypatch.setattr(local_dev, "PORTS", {"organizeme": 8000, "event-creator": 8001})

    with pytest.raises(SystemExit):
        _select_non_host_services(["event-creator"])


def test_select_non_host_services_defaults_to_no_apps_when_none_are_onboarded_yet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Slice 2 itself: ports.py only has "organizeme" - the auto-discovery default must resolve to
    # a Host-only session even if sibling repo directories happen to exist on disk.
    monkeypatch.setattr(local_dev, "PORTS", {"organizeme": 8000})

    result = _select_non_host_services(None)

    assert result == []
