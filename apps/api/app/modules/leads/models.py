from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.shared.enums.jobs import LeadStatus
from app.shared.utils.identifiers import new_public_id


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(24), unique=True, default=lambda: new_public_id("lead"))
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    search_job_id: Mapped[int | None] = mapped_column(ForeignKey("search_jobs.id"), index=True, nullable=True)
    assigned_to_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    company_name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(String(512), nullable=True)
    city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    website_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    website_domain: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    data_completeness: Mapped[float] = mapped_column(Float, default=0.0)
    data_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    has_website: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32), default=LeadStatus.NEW.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))

    search_job = relationship("SearchJob", back_populates="leads")


class LeadNote(Base):
    __tablename__ = "lead_notes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(24), unique=True, default=lambda: new_public_id("note"))
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)
    note: Mapped[str] = mapped_column(Text())
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))


class LeadStatusHistory(Base):
    __tablename__ = "lead_status_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32))
    changed_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))
