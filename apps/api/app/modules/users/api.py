from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.policies import get_current_user
from app.modules.users.models import User
from app.modules.users.schemas import (
    UserCreateRequest,
    UserDetailResponse,
    UserListResponse,
    UserOption,
    UserPasswordResetRequest,
    UserProfile,
    UserUpdateRequest,
    WorkspaceSettingsResponse,
    WorkspaceSettingsUpdateRequest,
)
from app.modules.users.service import UsersService

router = APIRouter(prefix="/api/v1", tags=["users"])


@router.get("/me", response_model=UserProfile)
def me(current_user: User = Depends(get_current_user)) -> UserProfile:
    return UsersService().get_profile(current_user)


@router.get("/users", response_model=UserListResponse)
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserListResponse:
    return UsersService().list_workspace_users(db, current_user.workspace_id)


@router.post("/users", response_model=UserOption, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserOption:
    return UsersService().create_workspace_user(
        db,
        workspace_id=current_user.workspace_id,
        payload=payload,
        actor=current_user,
    )


@router.get("/users/{user_id}", response_model=UserDetailResponse)
def get_user_detail(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserDetailResponse:
    return UsersService().get_workspace_user(
        db,
        workspace_id=current_user.workspace_id,
        user_public_id=user_id,
    )


@router.patch("/users/{user_id}", response_model=UserDetailResponse)
def update_user(
    user_id: str,
    payload: UserUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserDetailResponse:
    return UsersService().update_user(
        db,
        workspace_id=current_user.workspace_id,
        user_public_id=user_id,
        payload=payload,
        actor=current_user,
    )


@router.post("/users/{user_id}/reset-password", response_model=UserDetailResponse)
def reset_user_password(
    user_id: str,
    payload: UserPasswordResetRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserDetailResponse:
    return UsersService().reset_password(
        db,
        workspace_id=current_user.workspace_id,
        user_public_id=user_id,
        payload=payload,
        actor=current_user,
    )


@router.get("/workspace-settings", response_model=WorkspaceSettingsResponse)
def get_workspace_settings(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> WorkspaceSettingsResponse:
    return UsersService().get_workspace_settings(db, actor=current_user)


@router.patch("/workspace-settings", response_model=WorkspaceSettingsResponse)
def update_workspace_settings(
    payload: WorkspaceSettingsUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkspaceSettingsResponse:
    return UsersService().update_workspace_settings(db, actor=current_user, payload=payload)
