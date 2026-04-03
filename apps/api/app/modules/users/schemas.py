from typing import Literal

from pydantic import BaseModel, EmailStr, Field

UserRole = Literal["admin", "agency_manager", "sales_user"]


class UserProfile(BaseModel):
    public_id: str
    workspace_public_id: str
    email: EmailStr
    full_name: str
    role: UserRole

    model_config = {"from_attributes": True}


class UserOption(BaseModel):
    public_id: str
    email: EmailStr
    full_name: str
    role: UserRole


class UserCreateRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: UserRole


class UserListResponse(BaseModel):
    items: list[UserOption]
