from organizeme_chrome.design import (
    ALERT_VARIANT_CLASSES,
    BADGE_VARIANT_CLASSES,
    BUTTON_VARIANT_CLASSES,
    STATUS_VARIANT_CLASSES,
    TABLE_BODY_ROW_CLASSES,
    TABLE_HEAD_ROW_CLASSES,
)
from organizeme_chrome.paths import chrome_templates_dir

# docs/adr/design-refresh-dark-mode-css-strategy.md: every component's dark-mode styling must be
# expressed with ordinary `dark:` utility classes (tokens.css has no light/dark color pairing
# built in) - easy to silently drop while restyling, so pin that each touched/new template (or its
# backing class table, for the ones that source classes from design/classes.py) still carries at
# least one dark: class.
_TEMPLATES_REQUIRING_DARK_VARIANTS = [
    "chrome_authenticated_base.html",
    "macros/chrome_nav.html",
    "macros/chrome_tabs.html",
    "components/input.html",
    "components/card_shell.html",
    "components/status_dot.html",
]


def test_shell_and_component_templates_carry_dark_mode_classes() -> None:
    templates_dir = chrome_templates_dir()

    for relative_path in _TEMPLATES_REQUIRING_DARK_VARIANTS:
        content = (templates_dir / relative_path).read_text(encoding="utf-8")
        assert "dark:" in content, f"{relative_path} has no dark: classes"


def test_button_variant_classes_carry_dark_mode_classes() -> None:
    # button.html sources its color classes from BUTTON_VARIANT_CLASSES rather than embedding
    # them as template literals, so the dark: coverage lives in the Python table instead.
    assert any("dark:" in classes for classes in BUTTON_VARIANT_CLASSES.values())


def test_badge_variant_classes_carry_dark_mode_classes() -> None:
    assert all("dark:" in classes for classes in BADGE_VARIANT_CLASSES.values())


def test_status_variant_classes_carry_dark_mode_classes() -> None:
    assert any("dark:" in classes for classes in STATUS_VARIANT_CLASSES.values())


def test_alert_variant_classes_carry_dark_mode_classes() -> None:
    assert all("dark:" in classes for classes in ALERT_VARIANT_CLASSES.values())


def test_table_row_classes_carry_dark_mode_classes() -> None:
    assert "dark:" in TABLE_HEAD_ROW_CLASSES
    assert "dark:" in TABLE_BODY_ROW_CLASSES
