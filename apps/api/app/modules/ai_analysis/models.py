from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.shared.utils.identifiers import new_public_id


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(24), unique=True, default=lambda: new_public_id("pt")
    )
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    template_text: Mapped[str] = mapped_column(Text())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))


class AIAnalysisSnapshot(Base):
    __tablename__ = "ai_analysis_snapshots"
    __table_args__ = (
        Index("ix_ai_analysis_snapshots_lead_created_at", "lead_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(24), unique=True, default=lambda: new_public_id("ais")
    )
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)
    prompt_template_id: Mapped[int] = mapped_column(ForeignKey("prompt_templates.id"), index=True)
    ai_provider: Mapped[str] = mapped_column(String(32))
    model_name: Mapped[str] = mapped_column(String(128))
    input_hash: Mapped[str] = mapped_column(String(64), index=True)
    output_json: Mapped[dict[str, Any]] = mapped_column(JSON())
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))

    service_recommendations = relationship(
        "ServiceRecommendation",
        back_populates="ai_analysis_snapshot",
        cascade="all, delete-orphan",
    )


class ServiceRecommendation(Base):
    __tablename__ = "service_recommendations"
    __table_args__ = (
        UniqueConstraint(
            "ai_analysis_snapshot_id",
            "rank_order",
            name="uq_service_recommendations_snapshot_rank",
        ),
        Index("ix_service_recommendations_lead_created_at", "lead_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(24), unique=True, default=lambda: new_public_id("srv")
    )
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)
    ai_analysis_snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("ai_analysis_snapshots.id"), index=True
    )
    service_name: Mapped[str] = mapped_column(String(255))
    rationale: Mapped[str | None] = mapped_column(Text(), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    rank_order: Mapped[int] = mapped_column(Integer, default=1)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))

    ai_analysis_snapshot = relationship(
        "AIAnalysisSnapshot",
        back_populates="service_recommendations",
    )
