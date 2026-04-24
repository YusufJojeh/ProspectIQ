from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.shared.utils.identifiers import new_public_id


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(32), unique=True)
    label: Mapped[str] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))

    users = relationship("User", back_populates="role_definition")


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(24), unique=True, default=lambda: new_public_id("ws")
    )
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(
        String(120), unique=True, index=True, default=lambda: new_public_id("slug")
    )
    status: Mapped[str] = mapped_column(String(32), default="active")
    settings_json: Mapped[dict[str, object]] = mapped_column(JSON(), default=dict, nullable=False)
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))

    users = relationship("User", back_populates="workspace", foreign_keys="User.workspace_id")
    owner_user = relationship("User", foreign_keys=[owner_user_id], post_update=True)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(24), unique=True, default=lambda: new_public_id("usr")
    )
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), ForeignKey("roles.key"), default="member")
    status: Mapped[str] = mapped_column(String(32), default="active")
    invited_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)

    workspace = relationship("Workspace", back_populates="users", foreign_keys=[workspace_id])
    role_definition = relationship("Role", back_populates="users")
