from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.users.models import User, Workspace


class UsersRepository:
    def get_by_email(self, db: Session, email: str) -> User | None:
        return db.scalar(select(User).where(func.lower(User.email) == email.lower()))

    def get_by_public_id(self, db: Session, workspace_id: int, public_id: str) -> User | None:
        return db.scalar(
            select(User).where(User.workspace_id == workspace_id, User.public_id == public_id)
        )

    def get_workspace_by_public_id(self, db: Session, public_id: str) -> Workspace | None:
        return db.scalar(select(Workspace).where(Workspace.public_id == public_id))

    def get_workspace_by_slug(self, db: Session, slug: str) -> Workspace | None:
        return db.scalar(select(Workspace).where(Workspace.slug == slug))

    def get_workspace_by_id(self, db: Session, workspace_id: int) -> Workspace | None:
        return db.scalar(select(Workspace).where(Workspace.id == workspace_id))

    def list_for_workspace(self, db: Session, workspace_id: int) -> list[User]:
        statement = (
            select(User)
            .where(User.workspace_id == workspace_id)
            .order_by(User.created_at.asc(), User.email.asc())
        )
        return list(db.scalars(statement))

    def count_for_workspace(self, db: Session, workspace_id: int) -> int:
        return int(
            db.scalar(select(func.count(User.id)).where(User.workspace_id == workspace_id)) or 0
        )

    def add(self, db: Session, user: User) -> User:
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def save(self, db: Session, user: User) -> User:
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def add_workspace(self, db: Session, workspace: Workspace) -> Workspace:
        db.add(workspace)
        db.commit()
        db.refresh(workspace)
        return workspace

    def save_workspace(self, db: Session, workspace: Workspace) -> Workspace:
        db.add(workspace)
        db.commit()
        db.refresh(workspace)
        return workspace
