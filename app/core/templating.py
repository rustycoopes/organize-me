from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.pages.nav import NAV_ITEMS

APP_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=APP_DIR / "templates")

# Exposed to every template so the authenticated sidebar layout can render its nav from
# the single NAV_ITEMS source. Public pages simply don't include the sidebar partial.
templates.env.globals["nav_items"] = NAV_ITEMS


def initials(name: str) -> str:
    """First+last initials of a name for the events dashboard's ``agreed_by`` chips (#54).

    "Alice Smith" -> "AS", a single name "Alice" -> "AL", blank -> "?".
    """
    parts = name.split()
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


templates.env.filters["initials"] = initials
