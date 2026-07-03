"""The authenticated Upload page (Slice 4.1, #52).

Drag-and-drop + file-picker for a ``.txt`` / ``.zip`` / ``.csv`` export, which it POSTs to
``/api/v1/upload`` and then follows to the processing progress page (#53). Served here (rather than
as the generic placeholder in app.pages.app_shell) now that it has real content. Anonymous visitors
are redirected to /login like the other authenticated pages.

Whether Google Drive is connected is passed to the template so the page can steer an unconnected
user to Settings first (the upload itself is gated server-side in app.api.v1.upload regardless).
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.storage_config import get_user_storage_config
from app.auth.users import current_active_user_optional
from app.core.templating import templates
from app.db.session import get_db
from app.models.user import User

router = APIRouter(tags=["pages"])


@router.get("/upload", response_model=None)
async def upload_page(
    request: Request,
    user: User | None = Depends(current_active_user_optional),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    if user is None:
        return RedirectResponse("/login", status_code=302)
    config = await get_user_storage_config(db, user.id)
    drive_connected = config is not None and config.oauth_access_token is not None
    return templates.TemplateResponse(
        request,
        "upload.html",
        {"user": user, "dark_mode": user.dark_mode, "drive_connected": drive_connected},
    )
