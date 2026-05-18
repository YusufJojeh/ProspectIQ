from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.shared.utils.identifiers import new_public_id


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    __table_args__ = (
        Index("ix_chat_sessions_workspace_created_at", "workspace_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(24), unique=True, default=lambda: new_public_id("cs")
    )
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    lead_id: Mapped[int | None] = mapped_column(ForeignKey("leads.id"), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(255), default="New Chat")
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))

    messages: Mapped[list[ChatMessage]] = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        Index("ix_chat_messages_session_created_at", "session_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(24), unique=True, default=lambda: new_public_id("cm")
    )
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))

    session: Mapped[ChatSession] = relationship("ChatSession", back_populates="messages")
