"""Slice 3 (organize-me#255): unit coverage for infra/gcp_lb/verify_static_routing.py's pure
logic, with gcloud/network calls mocked out — the script itself is a manual, real-infra tool (see
its own module docstring), not something CI can run end-to-end.
"""

import json
import subprocess
from unittest.mock import MagicMock, patch
from urllib.error import URLError

import pytest
from organizeme_chrome.static_paths import static_mount_path

from infra.gcp_lb.verify_static_routing import (
    VerificationError,
    _gcloud,
    _validate_service_name,
    assert_single_revision_full_traffic,
    fetch,
    main,
    verify_app,
)


def _traffic_json(traffic: list[dict[str, object]]) -> str:
    return json.dumps({"status": {"traffic": traffic}})


@patch("infra.gcp_lb.verify_static_routing._gcloud")
def test_single_revision_full_traffic_passes(mock_gcloud: MagicMock) -> None:
    mock_gcloud.return_value = _traffic_json([{"revisionName": "doc-library-qa-00001", "percent": 100}])

    assert_single_revision_full_traffic("doc-library-qa")


@patch("infra.gcp_lb.verify_static_routing._gcloud")
def test_split_traffic_across_two_revisions_is_rejected(mock_gcloud: MagicMock) -> None:
    mock_gcloud.return_value = _traffic_json(
        [
            {"revisionName": "ha-dashboard-prod-00001", "percent": 90},
            {"revisionName": "ha-dashboard-prod-00002", "percent": 10},
        ]
    )

    with pytest.raises(VerificationError, match="not serving 100% traffic"):
        assert_single_revision_full_traffic("ha-dashboard-prod")


@patch("infra.gcp_lb.verify_static_routing._gcloud")
def test_no_active_traffic_entries_is_rejected(mock_gcloud: MagicMock) -> None:
    mock_gcloud.return_value = _traffic_json([])

    with pytest.raises(VerificationError, match="not serving 100% traffic"):
        assert_single_revision_full_traffic("doc-library-qa")


def test_validate_service_name_accepts_real_registry_style_names() -> None:
    for name in ("doc-library", "event-creator", "ha-dashboard", "organizeme"):
        _validate_service_name(name)  # must not raise


@pytest.mark.parametrize(
    "malicious_name",
    [
        "doc-library && echo pwned",
        "doc-library; rm -rf /",
        "%COMSPEC%",
        "doc library",
        "DOC-LIBRARY",
        "",
    ],
)
def test_validate_service_name_rejects_shell_unsafe_input(malicious_name: str) -> None:
    # This is the actual security boundary: on Windows, _gcloud() runs `gcloud` with shell=True
    # (required since gcloud is a .cmd wrapper), so a CLI-supplied app name reaching it unchecked
    # would be a real command-injection vector (cmd.exe re-parses %VAR%-expanded text for shell
    # operators) — this check must reject it before it ever reaches subprocess.run().
    with pytest.raises(VerificationError, match="not a valid service_name"):
        _validate_service_name(malicious_name)


def test_gcloud_invokes_subprocess_with_an_argument_list_never_a_joined_string() -> None:
    # Locks in the actual subprocess construction (every other test here mocks _gcloud itself
    # out) — a future refactor that reintroduces string-concatenated commands, which would be
    # unsafe together with shell=True, must fail this test.
    with patch("infra.gcp_lb.verify_static_routing.subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="ok", stderr="")

        _gcloud("run", "services", "describe", "doc-library-qa")

        args, kwargs = mock_run.call_args
        assert args[0] == ["gcloud", "run", "services", "describe", "doc-library-qa"]
        assert isinstance(args[0], list)
        assert "timeout" in kwargs


def test_gcloud_timeout_raises_verification_error() -> None:
    with patch(
        "infra.gcp_lb.verify_static_routing.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="gcloud", timeout=30),
    ):
        with pytest.raises(VerificationError, match="did not complete within"):
            _gcloud("run", "services", "describe", "doc-library-qa")


@patch("infra.gcp_lb.verify_static_routing._gcloud")
def test_gcloud_nonzero_exit_raises_verification_error(mock_gcloud_subprocess: MagicMock) -> None:
    # Exercises _gcloud's own error-translation path directly (not through a caller), since a
    # failed gcloud invocation is exactly the kind of message an operator relies on when the
    # script itself — not just the comparison it's making — is broken.
    with patch("infra.gcp_lb.verify_static_routing.subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["gcloud"], returncode=1, stdout="", stderr="ERROR: (gcloud.run.services.describe) NOT_FOUND"
        )
        with pytest.raises(VerificationError, match="NOT_FOUND"):
            _gcloud("run", "services", "describe", "no-such-service")


def test_fetch_translates_url_error_into_verification_error() -> None:
    with patch("infra.gcp_lb.verify_static_routing.urllib.request.urlopen", side_effect=URLError("timed out")):
        with pytest.raises(VerificationError, match="timed out"):
            fetch("https://doc-library-qa-abc123.a.run.app/doc-library/static/css/app.css")


@patch("infra.gcp_lb.verify_static_routing.fetch")
@patch("infra.gcp_lb.verify_static_routing.direct_service_url")
@patch("infra.gcp_lb.verify_static_routing.assert_single_revision_full_traffic")
def test_verify_app_uses_the_shared_static_mount_path_helper(
    mock_traffic_check: MagicMock, mock_direct_url: MagicMock, mock_fetch: MagicMock
) -> None:
    mock_direct_url.return_value = "https://doc-library-qa-abc123.a.run.app"
    mock_fetch.return_value = b"same-bytes"

    verify_app("doc-library", shared_host="organizeme.qa.russcoopersoftware.com", env="qa")

    mock_traffic_check.assert_called_once_with("doc-library-qa")
    asset_path = f"{static_mount_path('doc-library')}/css/app.css"
    fetched_urls = [call.args[0] for call in mock_fetch.call_args_list]
    assert fetched_urls == [
        f"https://organizeme.qa.russcoopersoftware.com{asset_path}",
        f"https://doc-library-qa-abc123.a.run.app{asset_path}",
    ]


@patch("infra.gcp_lb.verify_static_routing.direct_service_url")
@patch("infra.gcp_lb.verify_static_routing.assert_single_revision_full_traffic")
def test_verify_app_rejects_mismatched_content(
    mock_traffic_check: MagicMock, mock_direct_url: MagicMock
) -> None:
    mock_direct_url.return_value = "https://doc-library-qa-abc123.a.run.app"
    with patch(
        "infra.gcp_lb.verify_static_routing.fetch", side_effect=[b"shared-version", b"direct-version"]
    ):
        with pytest.raises(VerificationError, match="differs between"):
            verify_app("doc-library", shared_host="organizeme.qa.russcoopersoftware.com", env="qa")


def test_main_keeps_checking_remaining_apps_after_one_raises_an_unexpected_error() -> None:
    # An app's own bug (e.g. malformed `gcloud` JSON raising json.JSONDecodeError, not
    # VerificationError) must not abort evaluation of the apps after it in the list.
    def fake_verify_app(app_service_name: str, *, shared_host: str, env: str) -> None:
        if app_service_name == "event-creator":
            raise json.JSONDecodeError("bad json", "doc", 0)

    with patch("infra.gcp_lb.verify_static_routing.verify_app", side_effect=fake_verify_app) as mock_verify:
        exit_code = main(["--env", "qa", "event-creator", "doc-library"])

    assert exit_code == 1
    assert [call.args[0] for call in mock_verify.call_args_list] == ["event-creator", "doc-library"]
