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
    __table_args__ = (Index("ix_ai_analysis_snapshots_lead_created_at", "lead_id", "created_at"),)

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


class AIAnalysisEvidence(Base):
    __tablename__ = "ai_analysis_evidence"
    __table_args__ = (
        Index(
            "ix_ai_analysis_evidence_snapshot",
            "ai_analysis_snapshot_id",
        ),
        Index(
            "ix_ai_analysis_evidence_workspace_snapshot",
            "workspace_id",
            "ai_analysis_snapshot_id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(24), unique=True, default=lambda: new_public_id("aev")
    )
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    ai_analysis_snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("ai_analysis_snapshots.id"), index=True
    )
    source_type: Mapped[str] = mapped_column(String(64))
    source_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    evidence_text: Mapped[str] = mapped_column(Text())
    confidence: Mapped[float] = mapped_column(Float, default=0.7)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))


class AIFeedback(Base):
    __tablename__ = "ai_feedback"
    __table_args__ = (
        Index("ix_ai_feedback_snapshot", "ai_analysis_snapshot_id"),
        Index("ix_ai_feedback_user", "user_id"),
        Index("ix_ai_feedback_workspace_snapshot", "workspace_id", "ai_analysis_snapshot_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(24), unique=True, default=lambda: new_public_id("afb")
    )
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    ai_analysis_snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("ai_analysis_snapshots.id"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    rating: Mapped[str] = mapped_column(String(16))
    correction_text: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))


class WorkspaceServiceCatalogItem(Base):
    __tablename__ = "workspace_service_catalog_items"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "service_name",
            name="uq_wsc_workspace_service",
        ),
        Index("ix_wsc_workspace_rank", "workspace_id", "rank_order"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(24), unique=True, default=lambda: new_public_id("scat")
    )
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    service_name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    rank_order: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))
