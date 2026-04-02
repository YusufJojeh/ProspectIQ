from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    workspace: str
    email: EmailStr
    password: str


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
