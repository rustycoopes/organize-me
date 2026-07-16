"""The authenticated Settings page (issue #46).

R7 (docs/features/platform-restructure/WBS/slice-R7.md): the Host still renders the Settings *shell*
(tab-bar chrome, from the app-registry's settings_tabs — organizeme_chrome.registry), but no
longer owns any tab's *content*. Storage config (issue #46) and Notifications (issue #88) have
moved to the independent event-creator service, which now declares those tabs (plus a new stub
Preferences tab) via its own app-registry entry and serves their content as HTML fragments at
`GET /settings/event-creator/{storage,notifications,preferences}`. This page fetches each tab's
fragment via HTMX rather than rendering it inline; since both services sit behind the same load
balancer origin, these are same-origin requests and the `organizeme_auth` cookie flows
automatically (no cross-origin auth wiring needed).

Anonymous visitors are redirected to /login, matching the other authenticated pages.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from organizeme_chrome.registry import get_app

from app.auth.users import current_active_user_optional
from app.core.nav import sidebar_nav_context
from app.core.templating import templates
from app.models.user import User

router = APIRouter(tags=["pages"])

# The event-creator app-registry entry (organizeme_chrome.registry) is the single source of truth
# for which Settings tabs exist and their labels; this page just needs its tab ids to build each
# tab's HTMX fragment URL (GET /settings/event-creator/{tab.id}).
_EVENT_CREATOR_APP = get_app("event-creator")


@router.get("/settings", response_model=None)
async def settings_page(
    request: Request,
    user: User | None = Depends(current_active_user_optional),
) -> HTMLResponse | RedirectResponse:
    if user is None:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "user": user,
            "dark_mode": user.dark_mode,
            # Explicitly the event-creator entry's tabs, not the `settings_tabs` global that
            # register_chrome() scopes to this page's own app_service_name ("organizeme") — the
            # Host no longer owns any tab's content, so that global is empty (see
            # packages/chrome/src/organizeme_chrome/templating.py). Jinja2 template context takes
            # precedence over environment globals of the same name, so this overrides it for this
            # page only.
            "settings_tabs": _EVENT_CREATOR_APP.settings_tabs,
            **sidebar_nav_context(user, request),
        },
    )
