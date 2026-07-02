from fastapi import APIRouter, Depends

from app.auth.users import current_active_user
from app.models.user import User
from app.schemas.user import UserRead

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def read_current_user(user: User = Depends(current_active_user)) -> UserRead:
    return UserRead.model_validate(user)
