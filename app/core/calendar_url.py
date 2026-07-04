"""Build pre-filled Google Calendar / Google Tasks URLs for an extracted event (Slice 5.1, #54).

The dashboard renders an "Add to Google Calendar" and "Add to Google Task" link per event row.
Rather than take OAuth write access to a user's calendar (an explicit PRD non-goal), each link
simply opens Google's own creation UI in a new tab with the event details pre-filled via query
params — the user reviews and saves. These are pure functions so they're unit-testable without a
browser and reusable by later slices.

Google Calendar exposes a documented template endpoint (``/calendar/render?action=TEMPLATE``).
Google Tasks has **no** officially documented pre-fill URL scheme, so ``google_tasks_url`` is a
best-effort construction (title + ISO due date as query params) — see the changelog note; a
follow-up may revisit it if/when a stable scheme is confirmed.
"""

from datetime import date, timedelta
from urllib.parse import urlencode

CALENDAR_TEMPLATE_URL = "https://calendar.google.com/calendar/render"
TASKS_URL = "https://tasks.google.com/tasks/"


def _calendar_details(raw_date_text: str, agreed_by: list[str]) -> str:
    """Compose the Calendar event description from the raw date text plus who agreed it."""
    details = raw_date_text
    if agreed_by:
        details += f"\n\nAgreed by: {', '.join(agreed_by)}"
    return details


def google_calendar_url(
    title: str, start_date: date | None, raw_date_text: str, agreed_by: list[str]
) -> str:
    """Pre-filled Google Calendar event-creation URL for one event.

    ``title`` is the event description; ``start_date`` is ``resolved_date_earliest`` (rendered as
    an all-day event — Google's ``dates`` range is ``YYYYMMDD/YYYYMMDD`` with an *exclusive* end,
    so a single day spans to the next). When the date is unknown (unparseable "TBC"-style text) the
    ``dates`` param is omitted so the link still works and the user picks the date themselves. The
    raw date text and the ``agreed_by`` names go into the event description.
    """
    params: dict[str, str] = {"action": "TEMPLATE", "text": title}
    if start_date is not None:
        end_date = start_date + timedelta(days=1)  # exclusive end for an all-day event
        params["dates"] = f"{start_date:%Y%m%d}/{end_date:%Y%m%d}"
    details = _calendar_details(raw_date_text, agreed_by)
    if details:
        params["details"] = details
    return f"{CALENDAR_TEMPLATE_URL}?{urlencode(params)}"


def google_tasks_url(title: str, due_date: date | None) -> str:
    """Best-effort pre-filled Google Tasks creation URL (title + ISO due date).

    Google Tasks has no public, documented pre-fill URL, so this carries the title and due date as
    query params on the Tasks web endpoint — enough to open Tasks with the intent captured. The
    ``due`` param is omitted when the date is unknown so no bogus date is implied.
    """
    params: dict[str, str] = {"title": title}
    if due_date is not None:
        params["due"] = due_date.isoformat()
    return f"{TASKS_URL}?{urlencode(params)}"
