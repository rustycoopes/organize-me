from pathlib import Path

from fastapi.templating import Jinja2Templates
from organizeme_chrome import register_chrome

from app.core.initials import to_initials

APP_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=APP_DIR / "templates")

# organizeme_chrome owns the sidebar/header/Settings-tab-bar templates, theme config, and the
# app-registry (nav_items / settings_tabs globals) — see packages/chrome. This wires the Host's
# environment up to consume them as a pinned dependency.
register_chrome(templates.env, app_service_name="organizeme")
templates.env.filters["to_initials"] = to_initials
