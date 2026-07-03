"""The authenticated Prompt page (issue #49).

Lets a user view, edit, and reset the extraction prompt Gemini uses. Backed by
`GET`/`PUT /api/v1/llm-prompt` and `POST /api/v1/llm-prompt/reset`. Served here (rather than as a
generic placeholder in app.pages.app_shell) because it has real content. Anonymous visitors are
redirected to /login, matching the other authenticated pages.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.llm_prompt import get_or_create_user_prompt
from app.auth.users import current_active_user_optional
from app.core.templating import templates
from app.db.session import get_db
from app.models.user import User

router = APIRouter(tags=["pages"])


@router.get("/prompt", response_model=None)
async def prompt_page(
    request: Request,
    user: User | None = Depends(current_active_user_optional),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    if user is None:
        return RedirectResponse("/login", status_code=302)
    # Self-heals a legacy account with no seeded row (mirrors the GET endpoint), so the editor
    # always renders a usable prompt and the DB always holds a real row afterwards.
    prompt = await get_or_create_user_prompt(db, user.id)
    return templates.TemplateResponse(
        request,
        "prompt.html",
        {"user": user, "dark_mode": user.dark_mode, "prompt_text": prompt.prompt_text},
    )
