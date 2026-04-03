from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.shared.utils.identifiers import new_public_id


class ScoringConfigVersion(Base):
    __tablename__ = "scoring_config_versions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(24), unique=True, default=lambda: new_public_id("scv")
    )
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    weights_json: Mapped[dict[str, Any]] = mapped_column(JSON())
    thresholds_json: Mapped[dict[str, Any]] = mapped_column(JSON())
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))


class WorkspaceScoringActive(Base):
    __tablename__ = "workspace_scoring_active"

    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), primary_key=True)
    active_scoring_config_version_id: Mapped[int] = mapped_column(
        ForeignKey("scoring_config_versions.id")
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))


class LeadScore(Base):
    __tablename__ = "lead_scores"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)
    scoring_config_version_id: Mapped[int] = mapped_column(
        ForeignKey("scoring_config_versions.id"), index=True
    )
    total_score: Mapped[float] = mapped_column(Float)
    band: Mapped[str] = mapped_column(String(32))
    qualified: Mapped[bool] = mapped_column(Boolean, default=True)
    scored_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))

    breakdown_items = relationship(
        "ScoreBreakdown", back_populates="lead_score", cascade="all, delete-orphan"
    )


class ScoreBreakdown(Base):
    __tablename__ = "score_breakdowns"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    lead_score_id: Mapped[int] = mapped_column(ForeignKey("lead_scores.id"), index=True)
    key: Mapped[str] = mapped_column(String(64))
    label: Mapped[str] = mapped_column(String(255))
    weight: Mapped[float] = mapped_column(Float)
    contribution: Mapped[float] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(Text())

    lead_score = relationship("LeadScore", back_populates="breakdown_items")
