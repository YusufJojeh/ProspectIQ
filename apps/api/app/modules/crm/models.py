from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.utils.identifiers import new_public_id


class CrmPipeline(Base):
    __tablename__ = "crm_pipelines"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_crm_pipelines_workspace_name"),
        Index("ix_crm_pipelines_workspace_default", "workspace_id", "is_default"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(24), unique=True, default=lambda: new_public_id("pipe")
    )
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    is_default: Mapped[bool] = mapped_column(default=False)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))


class CrmStage(Base):
    __tablename__ = "crm_stages"
    __table_args__ = (
        UniqueConstraint("pipeline_id", "position", name="uq_crm_stages_pipeline_position"),
        Index("ix_crm_stages_pipeline_position", "pipeline_id", "position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(24), unique=True, default=lambda: new_public_id("stage")
    )
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    pipeline_id: Mapped[int] = mapped_column(ForeignKey("crm_pipelines.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    position: Mapped[int] = mapped_column(Integer)
    probability: Mapped[int] = mapped_column(Integer, default=10)
    color: Mapped[str] = mapped_column(String(32), default="slate")
    stage_type: Mapped[str] = mapped_column(String(24), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))


class CrmDeal(Base):
    __tablename__ = "crm_deals"
    __table_args__ = (
        Index("ix_crm_deals_workspace_status", "workspace_id", "status"),
        Index("ix_crm_deals_pipeline_stage", "pipeline_id", "stage_id"),
        Index("ix_crm_deals_lead_status", "lead_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(24), unique=True, default=lambda: new_public_id("deal")
    )
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    pipeline_id: Mapped[int] = mapped_column(ForeignKey("crm_pipelines.id"), index=True)
    stage_id: Mapped[int] = mapped_column(ForeignKey("crm_stages.id"), index=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)
    campaign_id: Mapped[int | None] = mapped_column(
        ForeignKey("campaigns.id"), index=True, nullable=True
    )
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(180))
    value_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    probability: Mapped[int] = mapped_column(Integer, default=10)
    status: Mapped[str] = mapped_column(String(24), default="open")
    lost_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expected_close_date: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    next_follow_up_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))


class CrmActivity(Base):
    __tablename__ = "crm_activities"
    __table_args__ = (
        Index("ix_crm_activities_deal_due", "deal_id", "due_at"),
        Index("ix_crm_activities_workspace_type", "workspace_id", "activity_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(24), unique=True, default=lambda: new_public_id("act")
    )
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    deal_id: Mapped[int] = mapped_column(ForeignKey("crm_deals.id"), index=True)
    activity_type: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(180))
    note: Mapped[str | None] = mapped_column(Text(), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))
