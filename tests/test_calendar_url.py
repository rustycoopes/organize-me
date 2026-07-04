"""Unit tests for the Google Calendar / Tasks pre-fill URL builders (Slice 5.1, #54)."""

from datetime import date
from urllib.parse import parse_qs, urlsplit

from app.core.calendar_url import google_calendar_url, google_tasks_url


def _query(url: str) -> dict[str, list[str]]:
    return parse_qs(urlsplit(url).query, keep_blank_values=True)


class TestGoogleCalendarUrl:
    def test_points_at_the_calendar_template_endpoint(self) -> None:
        url = google_calendar_url("Dentist", date(2026, 6, 6), "Saturday 6 June 2026", [])
        parts = urlsplit(url)
        assert parts.scheme == "https"
        assert parts.netloc == "calendar.google.com"
        assert parts.path == "/calendar/render"
        assert _query(url)["action"] == ["TEMPLATE"]

    def test_title_is_the_event_description(self) -> None:
        url = google_calendar_url("Pay school fees", date(2026, 6, 6), "6 June", [])
        assert _query(url)["text"] == ["Pay school fees"]

    def test_all_day_date_range_is_earliest_date_to_next_day_exclusive(self) -> None:
        # Google all-day events use YYYYMMDD/YYYYMMDD with an exclusive end (the next day).
        url = google_calendar_url("X", date(2026, 6, 6), "raw", [])
        assert _query(url)["dates"] == ["20260606/20260607"]

    def test_details_include_raw_date_text_and_agreed_by(self) -> None:
        url = google_calendar_url(
            "X", date(2026, 6, 6), "next Saturday", ["Alice", "Bob"]
        )
        details = _query(url)["details"][0]
        assert "next Saturday" in details
        assert "Alice" in details and "Bob" in details

    def test_details_omit_agreed_by_line_when_empty(self) -> None:
        url = google_calendar_url("X", date(2026, 6, 6), "just the raw text", [])
        details = _query(url)["details"][0]
        assert details == "just the raw text"

    def test_no_dates_param_when_earliest_date_is_unknown(self) -> None:
        # An event whose date couldn't be parsed ("TBC") still gets a usable link — the user
        # picks the date in Google Calendar — rather than a bogus/today date.
        url = google_calendar_url("X", None, "TBC", ["Alice"])
        assert "dates" not in _query(url)
        assert "Alice" in _query(url)["details"][0]

    def test_values_are_url_encoded(self) -> None:
        # Reserved characters in the title/details must be percent-encoded, not injected raw.
        url = google_calendar_url("Tom & Jerry: 3pm?", date(2026, 6, 6), "a, b & c", [])
        assert " " not in url and "&amp;" not in url
        # Round-trips back to the original values once decoded.
        assert _query(url)["text"] == ["Tom & Jerry: 3pm?"]


class TestGoogleTasksUrl:
    def test_title_is_carried(self) -> None:
        url = google_tasks_url("Return library books", date(2026, 6, 6))
        parts = urlsplit(url)
        assert parts.scheme == "https"
        assert "google.com" in parts.netloc
        # title is present under whichever param the builder uses
        assert "Return library books" in url or _query(url).get("title") == [
            "Return library books"
        ]

    def test_due_date_is_iso_formatted(self) -> None:
        url = google_tasks_url("X", date(2026, 6, 6))
        assert "2026-06-06" in url

    def test_no_due_param_when_date_is_unknown(self) -> None:
        url = google_tasks_url("X", None)
        assert "2026" not in url  # no bogus date leaked
        assert "due" not in _query(url)

    def test_values_are_url_encoded(self) -> None:
        url = google_tasks_url("Buy milk & eggs", date(2026, 6, 6))
        assert " " not in url
