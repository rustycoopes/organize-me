"""Pins the shipped `.om-stacked-table` pattern (mobile-responsive-tables slice 1).

Asserts the *stable core* only - the selector, the label mechanism, and the breakpoint - not full
rule bodies, so tuning the padding/border of the card layout doesn't churn this test.
"""

from organizeme_chrome.design import STACKED_TABLE_CLASS
from organizeme_chrome.paths import chrome_components_css_path, chrome_tokens_css_path


def test_components_css_ships_the_stacked_table_pattern() -> None:
    css_path = chrome_components_css_path()

    assert css_path.is_file()
    assert css_path.parent == chrome_tokens_css_path().parent  # reached the same way a consumer does

    css = css_path.read_text(encoding="utf-8")
    assert ".om-stacked-table" in css
    assert "content: attr(data-label)" in css
    assert "1023.98px" in css
    # ink-2 is also the dark card surface, so the pattern must restate border/label for .dark
    # (same bug class as design/classes.py's page_header / zebra-stripe comments).
    assert ".dark .om-stacked-table" in css


def test_stacked_table_class_is_importable_and_matches_the_css() -> None:
    assert STACKED_TABLE_CLASS == "om-stacked-table"
    assert STACKED_TABLE_CLASS in chrome_components_css_path().read_text(encoding="utf-8")
