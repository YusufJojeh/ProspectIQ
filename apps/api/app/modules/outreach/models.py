from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.utils.identifiers import new_public_id


class OutreachMessage(Base):
    __tablename__ = "outreach_messages"
    __table_args__ = (
        Index("ix_outreach_messages_lead_created_at", "lead_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(24), unique=True, default=lambda: new_public_id("om")
    )
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)
    ai_analysis_snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("ai_analysis_snapshots.id"), index=True
    )
    subject: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text())
    edited_subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    edited_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))
