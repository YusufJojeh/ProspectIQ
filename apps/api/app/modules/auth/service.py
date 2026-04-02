from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token, verify_password
from app.modules.auth.exceptions import InvalidCredentialsError
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import AuthenticatedUser, LoginRequest, TokenResponse


class AuthService:
    def __init__(self) -> None:
        self.repository = AuthRepository()

    def authenticate(self, db: Session, payload: LoginRequest) -> TokenResponse:
        workspace = self.repository.get_workspace_by_public_id(db, payload.workspace)
        if workspace is None:
            raise InvalidCredentialsError()
        user = self.repository.get_user_by_email(db, workspace.id, payload.email)
        if user is None or not verify_password(payload.password, user.hashed_password):
            raise InvalidCredentialsError()
        settings = get_settings()
        return TokenResponse(
            access_token=create_access_token(
                user.public_id,
                {
                    "role": user.role,
                    "workspace_id": workspace.id,
                    "workspace_public_id": workspace.public_id,
                },
            ),
            expires_in=settings.jwt_expire_minutes * 60,
            user=AuthenticatedUser(
                public_id=user.public_id,
                workspace_public_id=workspace.public_id,
                email=user.email,
                full_name=user.full_name,
                role=user.role,
            ),
        )
