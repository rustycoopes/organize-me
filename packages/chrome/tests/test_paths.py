from organizeme_chrome.paths import (
    chrome_fonts_dir,
    chrome_package_dir,
    chrome_templates_dir,
    chrome_tokens_css_path,
)


def test_chrome_templates_dir_exists_and_contains_chrome_base() -> None:
    templates_dir = chrome_templates_dir()

    assert templates_dir.is_dir()
    assert (templates_dir / "chrome_base.html").is_file()


def test_chrome_tokens_css_path_exists_and_defines_the_dark_variant() -> None:
    tokens_css_path = chrome_tokens_css_path()

    assert tokens_css_path.is_file()
    assert "@custom-variant dark" in tokens_css_path.read_text()


def test_chrome_fonts_dir_contains_the_self_hosted_webfonts() -> None:
    fonts_dir = chrome_fonts_dir()

    assert fonts_dir.is_dir()
    font_files = {f.name for f in fonts_dir.glob("*.woff2")}
    assert font_files == {
        "bricolage-grotesque-700.woff2",
        "ibm-plex-sans-400.woff2",
        "jetbrains-mono-400.woff2",
    }


def test_all_paths_share_the_same_package_root() -> None:
    root = chrome_package_dir()

    assert chrome_templates_dir().parent == root
    assert chrome_tokens_css_path().parent.parent.parent == root
