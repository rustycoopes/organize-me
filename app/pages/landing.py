from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.core.templating import templates

router = APIRouter(tags=["pages"])


@router.get("/", response_class=HTMLResponse)
async def landing_page(request: Request) -> HTMLResponse:
    # Anonymous visitor: no User.dark_mode to read, always light mode. Passed explicitly (rather
    # than relying on Jinja's Undefined.__bool__() falling through to False) so chrome_base.html's
    # theme_attr(dark_mode) call keeps working if the environment is ever hardened with
    # StrictUndefined.
    return templates.TemplateResponse(request, "landing.html", {"dark_mode": False})
