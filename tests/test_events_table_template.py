"""Template-level tests for the events table fragment (Slice 5.1, #54).

These render the Jinja partial directly (no DB) to guard the delete button's `@click` attribute
against the HTML-attribute-breakout class of bug: `{{ description | tojson }}` emits a JSON string
whose surrounding double quotes must not terminate the attribute early — otherwise Alpine gets a
truncated expression and Delete silently dies on every row.
"""

import uuid
from html.parser import HTMLParser

from app.api.v1.events import EventsPage, EventView
from app.core.templating import templates


def _render(description: str) -> str:
    view = EventView(
        id=uuid.uuid4(),
        type="Medical",
        description=description,
        resolved_date="6 June 2026",
        raw_date_text="6 June",
        agreed_by=[],
        calendar_url="https://calendar.google.com/x",
        tasks_url="https://tasks.google.com/x",
    )
    page = EventsPage(events=[view], page=1, total=1, page_size=50)
    return templates.env.get_template("partials/events_table.html").render(events_page=page)


class _AttrCollector(HTMLParser):
    """Collect every (tag, attr_name) pair so we can detect an attribute broken out of quoting."""

    def __init__(self) -> None:
        super().__init__()
        self.button_click: str | None = None
        self.attr_names: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            self.attr_names.add(name)
            if name == "@click" and value and "confirmDelete" in value:
                self.button_click = value


def _parse(html: str) -> _AttrCollector:
    parser = _AttrCollector()
    parser.feed(html)
    return parser


def test_delete_click_is_well_formed_for_a_plain_description() -> None:
    parsed = _parse(_render("Dentist"))
    assert parsed.button_click is not None
    assert parsed.button_click.startswith("confirmDelete(")
    # A clean parse means the attribute never broke out: no stray attribute named after the text.
    assert "dentist" not in parsed.attr_names


def test_delete_click_survives_quotes_and_angle_brackets_in_description() -> None:
    # Double quote (the exact char tojson does NOT escape), a single quote, and an HTML tag.
    parsed = _parse(_render('Dinner "at 6" it\'s <b>bold</b>'))
    assert parsed.button_click is not None
    assert parsed.button_click.startswith("confirmDelete(")
    # The description carried a full <b>…</b>; if the attribute had broken out, the parser would
    # have seen stray attributes / a real <b> start tag inside the row. It must not.
    assert "b" not in parsed.attr_names
    # The whole description reaches the handler (escaped), not a truncated fragment.
    assert "Dinner" in parsed.button_click and "bold" in parsed.button_click
