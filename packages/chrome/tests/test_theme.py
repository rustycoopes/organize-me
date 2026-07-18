from organizeme_chrome.theme import theme_attr


def test_theme_attr_returns_dark_class_when_dark_mode_is_true() -> None:
    assert theme_attr(True) == "dark"


def test_theme_attr_returns_empty_string_when_dark_mode_is_false() -> None:
    assert theme_attr(False) == ""
