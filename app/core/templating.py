from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.core.initials import to_initials
from app.pages.nav import NAV_ITEMS

APP_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=APP_DIR / "templates")

# Exposed to every template so the authenticated sidebar layout can render its nav from
# the single NAV_ITEMS source. Public pages simply don't include the sidebar partial.
templates.env.globals["nav_items"] = NAV_ITEMS
templates.env.filters["to_initials"] = to_initials
