from pathlib import Path

import pytest

from organizeme_chrome.assets import chrome_asset_version


def test_chrome_asset_version_falls_back_when_no_compiled_css_present() -> None:
    # The test process's cwd has no app/static/css/app.css (this package has no app/ tree of its
    # own) - assert the graceful fallback rather than a raised FileNotFoundError.
    assert chrome_asset_version() == "dev"


def test_chrome_asset_version_hashes_the_compiled_css_relative_to_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    css_dir = tmp_path / "app" / "static" / "css"
    css_dir.mkdir(parents=True)
    (css_dir / "app.css").write_bytes(b".a{color:red}")
    monkeypatch.chdir(tmp_path)

    version = chrome_asset_version()

    assert version != "dev"
    assert len(version) == 12


def test_chrome_asset_version_changes_when_the_compiled_css_content_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    css_dir = tmp_path / "app" / "static" / "css"
    css_dir.mkdir(parents=True)
    css_path = css_dir / "app.css"
    monkeypatch.chdir(tmp_path)

    css_path.write_bytes(b".a{color:red}")
    first = chrome_asset_version()

    css_path.write_bytes(b".a{color:blue}")
    second = chrome_asset_version()

    assert first != second
