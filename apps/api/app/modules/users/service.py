from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.modules.users.models import User, Workspace
from app.modules.users.repository import UsersRepository
from app.modules.users.schemas import UserProfile


class UsersService:
    def get_profile(self, user: User) -> UserProfile:
        return UserProfile(
            public_id=user.public_id,
            workspace_public_id=user.workspace.public_id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
        )


def bootstrap_default_admin(db: Session) -> None:
    # Deprecated: seeding is now handled via scripts/seed.py, not on API startup.
    return None


def seed_default_workspace_and_admin(db: Session) -> tuple[Workspace, User]:
    settings = get_settings()
    repository = UsersRepository()

    workspace = repository.get_workspace_by_public_id(db, settings.default_workspace_public_id)
    if workspace is None:
        workspace = repository.add_workspace(
            db,
            Workspace(public_id=settings.default_workspace_public_id, name=settings.default_workspace_name),
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
