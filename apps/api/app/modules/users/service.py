from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ConflictError
from app.core.security import hash_password
from app.modules.audit_logs.service import AuditLogService
from app.modules.users.models import Role, User, Workspace
from app.modules.users.repository import UsersRepository
from app.modules.users.schemas import (
    UserCreateRequest,
    UserListResponse,
    UserOption,
    UserProfile,
    UserRole,
)


class UsersService:
    def __init__(self) -> None:
        self.repository = UsersRepository()
        self.audit_logs = AuditLogService()

    def get_profile(self, user: User) -> UserProfile:
        return UserProfile(
            public_id=user.public_id,
            workspace_public_id=user.workspace.public_id,
            email=user.email,
            full_name=user.full_name,
            role=cast(UserRole, user.role),
        )

    def list_workspace_users(self, db: Session, workspace_id: int) -> UserListResponse:
        users = self.repository.list_for_workspace(db, workspace_id)
        return UserListResponse(
            items=[
                UserOption(
                    public_id=user.public_id,
                    email=user.email,
                    full_name=user.full_name,
                    role=cast(UserRole, user.role),
                )
                for user in users
            ]
        )

    def create_workspace_user(
        self,
        db: Session,
        *,
        workspace_id: int,
        payload: UserCreateRequest,
        actor: User,
    ) -> UserOption:
        email = payload.email.lower()
        existing = self.repository.get_by_email(db, workspace_id, email)
        if existing is not None:
            raise ConflictError("A user with that email already exists in this workspace.")

        created = self.repository.add(
            db,
            User(
                workspace_id=workspace_id,
                email=email,
                full_name=payload.full_name.strip(),
                hashed_password=hash_password(payload.password),
                role=payload.role,
            ),
        )
        self.audit_logs.record(
            db,
            workspace_id=workspace_id,
            actor_user_id=actor.id,
            event_name="user.created",
            details=f"Created user {created.public_id} with role {created.role}.",
        )
        return UserOption(
            public_id=created.public_id,
            email=created.email,
            full_name=created.full_name,
            role=cast(UserRole, created.role),
        )


def bootstrap_default_admin(db: Session) -> None:
    # Deprecated: seeding is now handled via scripts/seed.py, not on API startup.
    return None


def ensure_default_roles(db: Session) -> None:
    expected_roles = {
        "admin": ("Administrator", "Full workspace administration."),
        "agency_manager": ("Agency Manager", "Operational lead and scoring oversight."),
        "sales_user": ("Sales User", "Lead qualification and outreach execution."),
    }
    existing = {key for key in db.scalars(select(Role.key).where(Role.key.in_(expected_roles)))}
    missing = [
        Role(key=key, label=label, description=description)
        for key, (label, description) in expected_roles.items()
        if key not in existing
    ]
    if missing:
        db.add_all(missing)
        db.commit()


def seed_default_workspace_and_admin(db: Session) -> tuple[Workspace, User]:
    settings = get_settings()
    repository = UsersRepository()
    ensure_default_roles(db)

    workspace = repository.get_workspace_by_public_id(db, settings.default_workspace_public_id)
    if workspace is None:
        workspace = repository.add_workspace(
            db,
            Workspace(
                public_id=settings.default_workspace_public_id, name=settings.default_workspace_name
            ),
        )

    user = repository.get_by_email(db, workspace.id, settings.default_admin_email)
    if user is None:
        user = repository.add(
            db,
            User(
                workspace_id=workspace.id,
                email=settings.default_admin_email,
                full_name=settings.default_admin_name,
                hashed_password=hash_password(settings.default_admin_password),
                role="admin",
            ),
        )
    return workspace, user
