from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

UserRole = Literal["account_owner", "admin", "manager", "member"]
UserStatus = Literal["active", "inactive", "pending"]
WorkspaceStatus = Literal["active", "suspended", "disabled"]


class WorkspaceSummary(BaseModel):
    public_id: str
    name: str
    slug: str
    status: WorkspaceStatus

    model_config = {"from_attributes": True}


class UserProfile(BaseModel):
    public_id: str
    workspace_public_id: str
    workspace_name: str
    workspace_slug: str
    email: EmailStr
    full_name: str
    role: UserRole
    status: UserStatus
    avatar_url: str | None = None
    job_title: str | None = None
    permissions: list[str] = Field(default_factory=list)


class UserOption(BaseModel):
    public_id: str
    email: EmailStr
    full_name: str
    role: UserRole
    status: UserStatus
    job_title: str | None = None
    last_login_at: datetime | None = None
    created_at: datetime


class UserDetailResponse(UserOption):
    workspace_public_id: str
    invited_by_user_public_id: str | None = None
    avatar_url: str | None = None
    updated_at: datetime


class UserCreateRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=12, max_length=128)
    role: UserRole
    job_title: str | None = Field(default=None, max_length=255)
    avatar_url: str | None = Field(default=None, max_length=512)


class UserUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    role: UserRole | None = None
    status: UserStatus | None = None
    job_title: str | None = Field(default=None, max_length=255)
    avatar_url: str | None = Field(default=None, max_length=512)


class UserPasswordResetRequest(BaseModel):
    password: str = Field(min_length=12, max_length=128)


class UserListResponse(BaseModel):
    items: list[UserOption]


class WorkspaceSettingsResponse(BaseModel):
    workspace: WorkspaceSummary
    owner_user_public_id: str | None = None
    settings: dict[str, object] = Field(default_factory=dict)


class WorkspaceSettingsUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    slug: str | None = Field(default=None, min_length=2, max_length=120)
    settings: dict[str, object] | None = None
