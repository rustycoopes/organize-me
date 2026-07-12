"""The authenticated Settings page (issue #46).

Hosts a **Storage** tab (pick a provider, set the watch-folder path, backed by
`GET`/`PUT /api/v1/storage-config`) and a **Notifications** tab (toggle SMS/email, backed by the
existing `PATCH /api/v1/users/me`, issue #88). Served here (rather than as a generic placeholder in
app.pages.app_shell) because it has real content; more tabs land in later slices. Anonymous
visitors are redirected to /login, matching the other authenticated pages.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.storage_config import get_user_storage_config
from app.auth.users import current_active_user_optional
from app.core.templating import templates
from app.db.session import get_db
from app.models.storage_config import StorageProviderType
from app.models.user import User
from app.services.user_settings import get_or_create_user_settings

router = APIRouter(tags=["pages"])


@router.get("/settings", response_model=None)
async def settings_page(
    request: Request,
    user: User | None = Depends(current_active_user_optional),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    if user is None:
        return RedirectResponse("/login", status_code=302)
    config = await get_user_storage_config(db, user.id)
    # Prefill from any saved config; default to Google Drive with an empty folder for a fresh user
    # (Drive is the only provider actually wired up in this slice).
    storage_data = {
        "provider": (
            config.provider.value if config is not None else StorageProviderType.GOOGLE_DRIVE.value
        ),
        "folder_path": config.folder_path if config is not None else "",
        # Whether Drive is authenticated (a token is stored) - drives the connected/disconnected
        # state of the tab's Connect/Disconnect controls (#47).
        "is_connected": config.oauth_access_token is not None if config is not None else False,
        # Whether a config row exists at all: Connect can only run once a folder path is saved
        # (the tokens attach to that row), so the button is gated on this.
        "has_config": config is not None,
    }
    user_settings = await get_or_create_user_settings(db, user.id)
    notifications_data = {
        "notification_email": user_settings.notification_email,
        "notification_sms": user_settings.notification_sms,
        "email": user.email,
        "phone_number": user.phone_number or "",
    }
    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "user": user,
            "dark_mode": user.dark_mode,
            "storage_data": storage_data,
            "notifications_data": notifications_data,
        },
    )
