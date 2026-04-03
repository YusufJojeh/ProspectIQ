from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.policies import get_current_user, require_role
from app.modules.users.models import User
from app.modules.users.schemas import UserCreateRequest, UserListResponse, UserOption, UserProfile
from app.modules.users.service import UsersService

router = APIRouter(prefix="/api/v1", tags=["users"])


@router.get("/me", response_model=UserProfile)
def me(current_user: User = Depends(get_current_user)) -> UserProfile:
    return UsersService().get_profile(current_user)


@router.get("/users", response_model=UserListResponse)
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "agency_manager")),
) -> UserListResponse:
    return UsersService().list_workspace_users(db, current_user.workspace_id)


@router.post("/users", response_model=UserOption, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
) -> UserOption:
    return UsersService().create_workspace_user(
        db,
        workspace_id=current_user.workspace_id,
        payload=payload,
        actor=current_user,
    )
