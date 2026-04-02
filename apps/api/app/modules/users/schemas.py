from pydantic import BaseModel, EmailStr


class UserProfile(BaseModel):
    public_id: str
    workspace_public_id: str
    email: EmailStr
    full_name: str
    role: str

    model_config = {"from_attributes": True}
