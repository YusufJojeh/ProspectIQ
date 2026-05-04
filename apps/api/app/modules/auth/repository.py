from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.users.models import User, Workspace


class AuthRepository:
    def get_user_by_email(self, db: Session, email: str) -> User | None:
        return db.scalar(select(User).where(func.lower(User.email) == email.lower()))

    def get_user_by_public_id(self, db: Session, public_id: str) -> User | None:
        return db.scalar(select(User).where(User.public_id == public_id))

    def update_last_login(self, db: Session, user: User) -> User:
        user.last_login_at = datetime.now(tz=UTC)
        user.updated_at = datetime.now(tz=UTC)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def create_workspace_with_owner(
        self,
        db: Session,
        *,
        workspace_name: str,
        slug: str,
        email: str,
        full_name: str,
        hashed_password: str,
    ) -> User:
        from app.modules.provider_serpapi.models import ProviderSettings

        workspace = Workspace(
            name=workspace_name,
            slug=slug,
            status="active",
            settings_json={"locale": "en-US", "theme": "dark"},
        )
        db.add(workspace)
        db.flush()

        user = User(
            workspace_id=workspace.id,
            email=email,
            full_name=full_name,
            hashed_password=hashed_password,
            role="account_owner",
            status="active",
            last_login_at=datetime.now(tz=UTC),
        )
        db.add(user)
        db.flush()

        workspace.owner_user_id = user.id
        workspace.updated_at = datetime.now(tz=UTC)
        db.add(
            ProviderSettings(
                workspace_id=workspace.id,
                hl="en",
                gl="us",
                google_domain="google.com",
                enrich_top_n=20,
            )
        )
        db.commit()
        db.refresh(user)
        db.refresh(workspace)
        return user
