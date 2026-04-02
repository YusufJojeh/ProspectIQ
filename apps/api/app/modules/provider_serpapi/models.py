from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.shared.utils.identifiers import new_public_id


class ProviderSettings(Base):
    __tablename__ = "provider_settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), unique=True)
    hl: Mapped[str] = mapped_column(String(16), default="en")
    gl: Mapped[str] = mapped_column(String(16), default="us")
    google_domain: Mapped[str] = mapped_column(String(64), default="google.com")
    enrich_top_n: Mapped[int] = mapped_column(Integer, default=20)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))


class ProviderFetch(Base):
    __tablename__ = "provider_fetches"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(24), unique=True, default=lambda: new_public_id("pf"))
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    provider: Mapped[str] = mapped_column(String(32), default="serpapi")
    engine: Mapped[str] = mapped_column(String(32))
    mode: Mapped[str] = mapped_column(String(32))
    search_job_id: Mapped[int | None] = mapped_column(ForeignKey("search_jobs.id"), index=True, nullable=True)
    request_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    request_params_json: Mapped[dict] = mapped_column(JSON())
    serpapi_search_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="ok")
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, default=1)

    raw_payloads = relationship("ProviderRawPayload", back_populates="provider_fetch", cascade="all, delete-orphan")


class ProviderRawPayload(Base):
    __tablename__ = "provider_raw_payloads"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider_fetch_id: Mapped[int] = mapped_column(ForeignKey("provider_fetches.id"), index=True)
    payload_json: Mapped[dict] = mapped_column(JSON())
    payload_sha256: Mapped[str] = mapped_column(String(64), index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))

    provider_fetch = relationship("ProviderFetch", back_populates="raw_payloads")


class ProviderNormalizedFact(Base):
    __tablename__ = "provider_normalized_facts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)
    provider_fetch_id: Mapped[int] = mapped_column(ForeignKey("provider_fetches.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(32))
    data_cid: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    data_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    place_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)

    company_name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(String(512), nullable=True)
    city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    website_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    website_domain: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.7)
    completeness: Mapped[float] = mapped_column(Float, default=0.5)
    facts_json: Mapped[dict] = mapped_column(JSON(), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))


class LeadSourceRecord(Base):
    __tablename__ = "lead_source_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)
    provider_normalized_fact_id: Mapped[int] = mapped_column(ForeignKey("provider_normalized_facts.id"), index=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))


class LeadIdentity(Base):
    __tablename__ = "lead_identities"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)
    identity_type: Mapped[str] = mapped_column(String(32))
    identity_value: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))

