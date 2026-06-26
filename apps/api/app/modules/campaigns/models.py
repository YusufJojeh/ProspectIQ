from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.utils.identifiers import new_public_id


class Campaign(Base):
    __tablename__ = "campaigns"
    __table_args__ = (Index("ix_campaigns_workspace_status", "workspace_id", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(24), unique=True, default=lambda: new_public_id("cmp")
    )
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    icp_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("icp_profiles.id"), index=True, nullable=True
    )
    status: Mapped[str] = mapped_column(String(24), default="draft")
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))


class CampaignLead(Base):
    __tablename__ = "campaign_leads"
    __table_args__ = (
        UniqueConstraint("campaign_id", "lead_id", name="uq_campaign_leads_campaign_lead"),
        Index("ix_campaign_leads_campaign_lead", "campaign_id", "lead_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), index=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)
    status: Mapped[str] = mapped_column(String(24), default="added")
    added_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))


class SequenceStep(Base):
    __tablename__ = "sequence_steps"
    __table_args__ = (
        UniqueConstraint("campaign_id", "step_order", name="uq_sequence_steps_campaign_order"),
        Index("ix_sequence_steps_campaign_order", "campaign_id", "step_order"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(24), unique=True, default=lambda: new_public_id("seq")
    )
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), index=True)
    step_order: Mapped[int] = mapped_column(Integer)
    channel: Mapped[str] = mapped_column(String(24), default="email")
    delay_days: Mapped[int] = mapped_column(Integer, default=0)
    tone: Mapped[str] = mapped_column(String(32), default="consultative")
    language: Mapped[str] = mapped_column(String(8), default="en")
    template_text: Mapped[str] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))


class OutreachEvent(Base):
    __tablename__ = "outreach_events"
    __table_args__ = (
        Index("ix_outreach_events_workspace_type", "workspace_id", "event_type"),
        Index("ix_outreach_events_campaign_type", "campaign_id", "event_type"),
        Index("ix_outreach_events_lead_type", "lead_id", "event_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(24), unique=True, default=lambda: new_public_id("oev")
    )
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    campaign_id: Mapped[int | None] = mapped_column(
        ForeignKey("campaigns.id"), index=True, nullable=True
    )
    lead_id: Mapped[int | None] = mapped_column(ForeignKey("leads.id"), index=True, nullable=True)
    outreach_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("outreach_messages.id"), index=True, nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
