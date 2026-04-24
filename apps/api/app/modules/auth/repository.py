from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.users.models import User


class AuthRepository:
    def get_user_by_email(self, db: Session, email: str) -> User | None:
        return db.scalar(select(User).where(func.lower(User.email) == email.lower()))

    def get_user_by_public_id(self, db: Session, public_id: str) -> User | None:
        return db.scalar(select(User).where(User.public_id == public_id))
