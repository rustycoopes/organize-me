from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth.users import current_active_user_optional
from app.core.templating import templates
from app.models.user import User

router = APIRouter(tags=["pages"])


@router.get("/profile", response_model=None)
async def profile_page(
    request: Request, user: User | None = Depends(current_active_user_optional)
) -> HTMLResponse | RedirectResponse:
    if user is None:
        return RedirectResponse("/login", status_code=302)
    profile_data = {
        "name": user.name or "",
        "email": user.email,
        "phone_number": user.phone_number or "",
        "dark_mode": user.dark_mode,
    }
    return templates.TemplateResponse(
        request,
        "profile.html",
        {"user": user, "dark_mode": profile_data["dark_mode"], "profile_data": profile_data},
    )
