from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.users.models import User, Workspace


class UsersRepository:
    def get_by_email(self, db: Session, workspace_id: int, email: str) -> User | None:
        return db.scalar(select(User).where(User.workspace_id == workspace_id, User.email == email))

    def get_by_public_id(self, db: Session, workspace_id: int, public_id: str) -> User | None:
        return db.scalar(select(User).where(User.workspace_id == workspace_id, User.public_id == public_id))

    def get_workspace_by_public_id(self, db: Session, public_id: str) -> Workspace | None:
        return db.scalar(select(Workspace).where(Workspace.public_id == public_id))

    def add(self, db: Session, user: User) -> User:
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def add_workspace(self, db: Session, workspace: Workspace) -> Workspace:
        db.add(workspace)
        db.commit()
        db.refresh(workspace)
        return workspace
