"""Authenticated placeholder pages behind the sidebar shell (issue #17).

Each nav route renders the shared authenticated layout with a generic placeholder body;
real content lands in later slices. Profile (app.pages.profile) and Settings
(app.pages.settings) are served separately as they already have real content. All routes
redirect anonymous visitors to /login, matching the profile page's gating.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth.users import current_active_user_optional
from app.core.templating import templates
from app.models.user import User
from app.pages.nav import NAV_ITEMS

router = APIRouter(tags=["pages"])

# Placeholder pages are every nav destination except the ones with their own router and real
# content (/profile, /settings, /prompt). Derived from NAV_ITEMS so paths/labels have a single
# source of truth.
PAGES_WITH_OWN_ROUTER = {"/profile", "/settings", "/prompt"}
PLACEHOLDER_PAGES: list[tuple[str, str]] = [
    (item.path, item.label) for item in NAV_ITEMS if item.path not in PAGES_WITH_OWN_ROUTER
]


def _register(path: str, title: str) -> None:
    @router.get(path, response_model=None, name=f"page{path.replace('/', '_')}")
    async def placeholder_page(
        request: Request, user: User | None = Depends(current_active_user_optional)
    ) -> HTMLResponse | RedirectResponse:
        if user is None:
            return RedirectResponse("/login", status_code=302)
        return templates.TemplateResponse(
            request,
            "pages/placeholder.html",
            {"user": user, "dark_mode": user.dark_mode, "page_title": title},
        )


for _path, _title in PLACEHOLDER_PAGES:
    _register(_path, _title)
