from fastapi import APIRouter, Depends

from app.modules.auth.policies import get_current_user
from app.modules.users.models import User
from app.modules.users.schemas import UserProfile
from app.modules.users.service import UsersService

router = APIRouter(prefix="/api/v1", tags=["users"])


@router.get("/me", response_model=UserProfile)
def me(current_user: User = Depends(get_current_user)) -> UserProfile:
    return UsersService().get_profile(current_user)

