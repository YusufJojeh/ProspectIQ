from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.utils.identifiers import new_public_id


class LeadSignal(Base):
    __tablename__ = "lead_signals"
    __table_args__ = (
        Index("ix_lead_signals_workspace_lead_detected", "workspace_id", "lead_id", "detected_at"),
        Index("ix_lead_signals_workspace_type", "workspace_id", "signal_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(24), unique=True, default=lambda: new_public_id("sig")
    )
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)
    signal_type: Mapped[str] = mapped_column(String(64))
    signal_strength: Mapped[float] = mapped_column(Float)
    evidence_text: Mapped[str] = mapped_column(Text())
    source_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))


class LeadSignalScore(Base):
    __tablename__ = "lead_signal_scores"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "lead_id",
            "signal_type",
            name="uq_lead_signal_scores_workspace_lead_type",
        ),
        Index("ix_lead_signal_scores_workspace_lead", "workspace_id", "lead_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)
    signal_type: Mapped[str] = mapped_column(String(64))
    score: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float, default=0.7)
    evidence_count: Mapped[int] = mapped_column(Integer, default=1)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))
