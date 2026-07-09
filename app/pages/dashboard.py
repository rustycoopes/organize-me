"""The authenticated Events dashboard (Slice 5.1/5.2, #54/#55).

The first user-visible payoff of the processing pipeline: a paginated, filterable table of the
events Gemini extracted, with per-row Google Calendar/Tasks links and delete. Served here (rather
than as the generic placeholder in app.pages.app_shell) now that it has real content. Anonymous
visitors are redirected to /login like the other authenticated pages.

Filtering/sorting/search (#55) is HTMX-driven: the filter form and pagination/sort links target
``#dashboard-body`` and this route detects the ``HX-Request`` header to return just that fragment
(``partials/dashboard_body.html``, which wraps the filter form and the events panel together -
see its docstring for why both must swap as one unit) instead of the full page, so narrowing the
table never triggers a full page reload.
"""

from datetime import date as date_
from functools import partial
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.events import (
    PAGE_SIZE,
    SortOrder,
    list_user_event_types,
    list_user_events,
    parse_date_param,
    to_event_read,
)
from app.auth.users import current_active_user_optional
from app.core.onboarding import build_onboarding_steps, onboarding_complete
from app.core.templating import templates
from app.db.session import get_db
from app.models.user import User

router = APIRouter(tags=["pages"])


def _dashboard_url(
    *,
    page: int,
    type: str | None,  # noqa: A002 - mirrors the query param name
    date_from: date_ | None,
    date_to: date_ | None,
    q: str | None,
    sort: SortOrder,
    show_reviewed: bool = False,
) -> str:
    """Build a /dashboard URL carrying only the non-default filters, so a plain unfiltered link
    stays as short as ``/dashboard?page=2`` (existing pagination tests assert this exact form)."""
    params: dict[str, str] = {}
    if type:
        params["type"] = type
    if date_from is not None:
        params["date_from"] = date_from.isoformat()
    if date_to is not None:
        params["date_to"] = date_to.isoformat()
    if q:
        params["q"] = q
    if sort != "desc":
        params["sort"] = sort
    if show_reviewed:
        params["show_reviewed"] = "true"
    params["page"] = str(page)
    return f"/dashboard?{urlencode(params)}"


@router.get("/dashboard", response_model=None)
async def dashboard_page(
    request: Request,
    page: int = Query(default=1, ge=1),
    type: str | None = Query(default=None, alias="type"),  # noqa: A002
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    q: str | None = Query(default=None),
    sort: SortOrder = Query(default="desc"),
    show_reviewed: bool = Query(default=False),
    user: User | None = Depends(current_active_user_optional),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    if user is None:
        return RedirectResponse("/login", status_code=302)
    # The filter form is a plain <form> HTMX serializes as-is, so an untouched date picker submits
    # "" rather than omitting the param - parse_date_param treats that the same as unset.
    parsed_date_from = parse_date_param(date_from)
    parsed_date_to = parse_date_param(date_to)
    events, total = await list_user_events(
        db,
        user.id,
        page,
        event_type=type,
        date_from=parsed_date_from,
        date_to=parsed_date_to,
        search=q,
        sort=sort,
        show_reviewed=show_reviewed,
    )
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    # Bound to the current filters so every call site below only has to vary page/sort - keeping
    # a filter param out of sync across prev/next/sort/redirect (four call sites) isn't possible
    # since there's only one place they're threaded through.
    url_for = partial(
        _dashboard_url,
        type=type,
        date_from=parsed_date_from,
        date_to=parsed_date_to,
        q=q,
        show_reviewed=show_reviewed,
    )
    # A page beyond the last valid one (e.g. a stale bookmark, or the last event on that page was
    # just deleted) would otherwise render the empty-state message even though the user has
    # earlier events - redirect to the last real page instead of showing a misleading "No events
    # yet". Only applies here (the browsable page); the JSON API returns an honest empty list for
    # an out-of-range page rather than redirecting a GET a client didn't ask to be redirected from.
    if total > 0 and page > total_pages:
        return RedirectResponse(url_for(page=total_pages, sort=sort), status_code=302)

    event_types = await list_user_event_types(db, user.id)
    # list_user_event_types is unaffected by any filter (see its docstring), so a non-empty result
    # here means the user has events somewhere even if none are showing - e.g. every event is
    # reviewed and "Show reviewed" is off. Without this, a returning user whose events are all
    # reviewed would see the misleading first-time "No events yet" message instead of "No events
    # match these filters" (#113).
    has_active_filters = bool(
        type or parsed_date_from or parsed_date_to or q or show_reviewed or event_types
    )
    context = {
        "user": user,
        "dark_mode": user.dark_mode,
        "events": [to_event_read(e) for e in events],
        "page": page,
        "total_pages": total_pages,
        "total": total,
        "event_types": event_types,
        "has_active_filters": has_active_filters,
        "filters": {
            "type": type or "",
            "date_from": parsed_date_from.isoformat() if parsed_date_from else "",
            "date_to": parsed_date_to.isoformat() if parsed_date_to else "",
            "q": q or "",
            "sort": sort,
            "show_reviewed": show_reviewed,
        },
        "prev_url": url_for(page=page - 1, sort=sort) if page > 1 else None,
        "next_url": url_for(page=page + 1, sort=sort) if page < total_pages else None,
        "sort_toggle_url": url_for(page=1, sort="asc" if sort == "desc" else "desc"),
        "onboarding_steps": build_onboarding_steps(user),
        "onboarding_complete": onboarding_complete(user),
    }
    template_name = (
        "partials/dashboard_body.html"
        if request.headers.get("hx-request") == "true"
        else "dashboard.html"
    )
    return templates.TemplateResponse(request, template_name, context)
