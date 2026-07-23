"""The authenticated Settings page (issue #46).

R7 (docs/features/platform-restructure/WBS/slice-R7.md): the Host still renders the Settings *shell*
(tab-bar chrome, from the app-registry's settings_tabs — organizeme_chrome.registry), but no
longer owns any tab's *content*. Storage config (issue #46) and Notifications (issue #88) moved to
the independent event-creator service first; ha-dashboard's own Settings tab (Slice 3 there)
followed once a second hosted app actually needed one. This page aggregates `settings_tabs` across
every registered app (`list_apps()`), not just event-creator, and fetches each tab's content as an
HTML fragment from its *owning* app's own service_name
(`GET /settings/{service_name}/{tab.id}`) rather than a single hardcoded service - since both
services sit behind the same load balancer origin, these are same-origin requests and the
`organizeme_auth` cookie flows automatically (no cross-origin auth wiring needed).

Anonymous visitors are redirected to /login, matching the other authenticated pages.
"""

from dataclasses import dataclass

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from organizeme_chrome.registry import list_apps

from app.auth.users import current_active_user_optional
from app.core.nav import sidebar_nav_context
from app.core.templating import templates
from app.models.user import User

router = APIRouter(tags=["pages"])


@dataclass(frozen=True)
class _OwnedSettingsTab:
    """A `SettingsTab` paired with the `service_name` of the app that owns its content fragment -
    `SettingsTab` itself doesn't carry this (see its own docstring), and the template needs it to
    build each tab's `GET /settings/{service_name}/{id}` fetch URL.
    """

    service_name: str
    id: str
    label: str


def _all_settings_tabs() -> list[_OwnedSettingsTab]:
    """Every registered app's settings_tabs, in app-registration order, each paired with its
    owning app's service_name. Looked up per request, not at module-import time (registry-
    decoupling, organize-me#218) - see the equivalent comment this replaced for why.
    """
    return [
        _OwnedSettingsTab(service_name=app.service_name, id=tab.id, label=tab.label)
        for app in list_apps()
        for tab in app.settings_tabs
    ]


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
            # Explicitly the aggregated per-app tab list, not the `settings_tabs` global that
            # register_chrome() scopes to this page's own app_service_name ("organizeme") — the
            # Host no longer owns any tab's content, so that global is empty (see
            # packages/chrome/src/organizeme_chrome/templating.py). Jinja2 template context takes
            # precedence over environment globals of the same name, so this overrides it for this
            # page only.
            "settings_tabs": _all_settings_tabs(),
            **sidebar_nav_context(user, request),
        },
    )
