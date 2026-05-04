from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ConflictError
from app.core.security import create_access_token, verify_password
from app.modules.audit_logs.service import AuditLogService
from app.modules.auth.exceptions import InactiveUserError, InvalidCredentialsError
from app.modules.auth.permissions import get_role_permissions
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import (
    AuthenticatedUser,
    LoginRequest,
    LogoutResponse,
    SignupRequest,
    TokenResponse,
)
from app.modules.users.models import User
from app.modules.users.repository import UsersRepository
from app.modules.users.service import (
    ensure_default_roles,
    ensure_password_strength,
    normalize_workspace_slug,
)


class AuthService:
    def __init__(self) -> None:
        self.repository = AuthRepository()
        self.users_repository = UsersRepository()
        self.audit_logs = AuditLogService()

    def authenticate(self, db: Session, payload: LoginRequest) -> TokenResponse:
        email = payload.email.lower()
        user = self.repository.get_user_by_email(db, email)
        if user is None or not verify_password(payload.password, user.hashed_password):
            if user is not None:
                self.audit_logs.record(
                    db,
                    workspace_id=user.workspace_id,
                    actor_user_id=user.id,
                    event_name="auth.login_failed",
                    details=f"Failed login attempt for {email}.",
                )
            raise InvalidCredentialsError()
        if user.status != "active":
            self.audit_logs.record(
                db,
                workspace_id=user.workspace_id,
                actor_user_id=user.id,
                event_name="auth.login_blocked",
                details=f"Blocked login attempt for inactive user {user.public_id}.",
            )
            raise InactiveUserError()

        user = self.repository.update_last_login(db, user)

        self.audit_logs.record(
            db,
            workspace_id=user.workspace_id,
            actor_user_id=user.id,
            event_name="auth.login",
            details=f"User {user.public_id} authenticated successfully.",
        )
        return self._issue_token(user)

    def signup(self, db: Session, payload: SignupRequest) -> TokenResponse:
        from app.modules.billing.service import BillingService

        email = payload.email.lower()
        existing = self.repository.get_user_by_email(db, email)
        if existing is not None:
            raise ConflictError("A user with that email already exists.")
        ensure_password_strength(payload.password)
        ensure_default_roles(db)

        slug = normalize_workspace_slug(payload.workspace_name)
        existing_workspace = self.users_repository.get_workspace_by_slug(db, slug)
        if existing_workspace is not None:
            raise ConflictError("Workspace slug is already in use.")

        user = self.repository.create_workspace_with_owner(
            db,
            workspace_name=payload.workspace_name.strip(),
            slug=slug,
            email=email,
            full_name=payload.full_name.strip(),
            hashed_password=ensure_hashed_password(payload.password),
        )

        billing = BillingService()
        billing.ensure_seed_data(db)
        billing.bootstrap_workspace_subscription(db, workspace=user.workspace, actor_user_id=user.id)

        self.audit_logs.record(
            db,
            workspace_id=user.workspace_id,
            actor_user_id=user.id,
            event_name="auth.signup",
            details=f"Created workspace {user.workspace.public_id} with owner {user.public_id}.",
        )
        return self._issue_token(user)

    def logout(self) -> LogoutResponse:
        return LogoutResponse()

    def me(self, user: User) -> AuthenticatedUser:
        return self._to_authenticated_user(user)

    def _issue_token(self, user: User) -> TokenResponse:
        settings = get_settings()
        workspace = user.workspace
        return TokenResponse(
            access_token=create_access_token(
                user.public_id,
                {
                    "role": user.role,
                    "status": user.status,
                    "workspace_id": workspace.id,
                    "workspace_public_id": workspace.public_id,
                    "workspace_slug": workspace.slug,
                },
            ),
            expires_in=settings.jwt_expire_minutes * 60,
            user=self._to_authenticated_user(user),
        )

    def _to_authenticated_user(self, user: User) -> AuthenticatedUser:
        return AuthenticatedUser(
            public_id=user.public_id,
            workspace_public_id=user.workspace.public_id,
            workspace_name=user.workspace.name,
            workspace_slug=user.workspace.slug,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            status=user.status,
            permissions=get_role_permissions(user.role),
        )


def ensure_hashed_password(raw_password: str) -> str:
    from app.core.security import hash_password

    return hash_password(raw_password)
