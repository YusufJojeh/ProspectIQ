from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.enums.jobs import WebsitePreference
from app.shared.utils.identifiers import new_public_id


class IcpProfile(Base):
    __tablename__ = "icp_profiles"
    __table_args__ = (
        Index("ix_icp_profiles_workspace_active", "workspace_id", "is_active"),
        Index("ix_icp_profiles_workspace_name", "workspace_id", "name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(24), unique=True, default=lambda: new_public_id("icp")
    )
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    target_industries: Mapped[list[str]] = mapped_column(JSON(), default=list)
    target_cities: Mapped[list[str]] = mapped_column(JSON(), default=list)
    min_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_reviews: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_reviews: Mapped[int | None] = mapped_column(Integer, nullable=True)
    website_preference: Mapped[str] = mapped_column(
        String(32), default=WebsitePreference.ANY.value
    )
    required_signals: Mapped[list[str]] = mapped_column(JSON(), default=list)
    excluded_keywords: Mapped[list[str]] = mapped_column(JSON(), default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))


class LeadIcpMatch(Base):
    __tablename__ = "lead_icp_matches"
    __table_args__ = (
        Index("ix_lead_icp_matches_workspace_lead", "workspace_id", "lead_id"),
        Index("ix_lead_icp_matches_workspace_profile", "workspace_id", "icp_profile_id"),
        Index("ix_lead_icp_matches_lead_profile", "lead_id", "icp_profile_id", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(24), unique=True, default=lambda: new_public_id("lim")
    )
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)
    icp_profile_id: Mapped[int] = mapped_column(ForeignKey("icp_profiles.id"), index=True)
    fit_score: Mapped[float] = mapped_column(Float)
    matched: Mapped[bool] = mapped_column(Boolean, default=True)
    match_reasons_json: Mapped[dict[str, Any]] = mapped_column(JSON(), default=dict)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))
