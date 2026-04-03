from typing import Annotated

from pydantic import BaseModel, EmailStr, StringConstraints


class LoginRequest(BaseModel):
    workspace: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    email: EmailStr
    password: Annotated[str, StringConstraints(min_length=8)]


class AuthTokenClaims(BaseModel):
    sub: str
    workspace_id: int
    workspace_public_id: str
    role: str


class AuthenticatedUser(BaseModel):
    public_id: str
    workspace_public_id: str
    email: EmailStr
    full_name: str
    role: str

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: AuthenticatedUser
