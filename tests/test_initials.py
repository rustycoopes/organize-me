"""Unit tests for the agreed-by initials helper (issue #100)."""

from app.core.initials import to_initials


def test_to_initials_multi_word_name() -> None:
    assert to_initials("Russ Cooper") == "RC"
    assert to_initials("Christine Cooper") == "CC"


def test_to_initials_single_word_name() -> None:
    assert to_initials("Alice") == "A"


def test_to_initials_lowercases_input_are_uppercased() -> None:
    assert to_initials("russ cooper") == "RC"


def test_to_initials_middle_names_use_first_and_last_only() -> None:
    assert to_initials("Russ Alan Cooper") == "RC"


def test_to_initials_extra_whitespace_is_ignored() -> None:
    assert to_initials("  Russ   Cooper  ") == "RC"


def test_to_initials_empty_string_returns_empty_string() -> None:
    assert to_initials("") == ""
    assert to_initials("   ") == ""
