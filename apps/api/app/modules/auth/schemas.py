from collections.abc import Sequence
from typing import Annotated

from pydantic import BaseModel, StringConstraints

from app.shared.validation import EmailAddress


class LoginRequest(BaseModel):
    email: EmailAddress
    password: Annotated[str, StringConstraints(min_length=1)]


class SignupRequest(BaseModel):
    full_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=2, max_length=255)
    ]
    workspace_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=2, max_length=255)
    ]
    email: EmailAddress
    password: Annotated[str, StringConstraints(min_length=12, max_length=128)]


class LogoutResponse(BaseModel):
    success: bool = True


class AuthTokenClaims(BaseModel):
    sub: str
    workspace_id: int
    workspace_public_id: str
    workspace_slug: str
    role: str
    status: str


class AuthenticatedUser(BaseModel):
    public_id: str
    workspace_public_id: str
    workspace_name: str
    workspace_slug: str
    email: EmailAddress
    full_name: str
    role: str
    status: str
    permissions: Sequence[str]

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: AuthenticatedUser
