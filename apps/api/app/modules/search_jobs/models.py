from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.shared.enums.jobs import SearchJobStatus, WebsitePreference
from app.shared.utils.identifiers import new_public_id


class SearchRequest(Base):
    __tablename__ = "search_requests"
    __table_args__ = (
        Index("ix_search_requests_workspace_created_at", "workspace_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(24), unique=True, default=lambda: new_public_id("srq")
    )
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    requested_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    business_type: Mapped[str] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(255))
    region: Mapped[str | None] = mapped_column(String(255), nullable=True)
    radius_km: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_results: Mapped[int] = mapped_column(Integer, default=25)
    min_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_reviews: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_reviews: Mapped[int | None] = mapped_column(Integer, nullable=True)
    website_preference: Mapped[str] = mapped_column(String(32), default=WebsitePreference.ANY.value)
    keyword_filter: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))

    jobs = relationship("SearchJob", back_populates="search_request")


class SearchJob(Base):
    __tablename__ = "search_jobs"
    __table_args__ = (
        Index("ix_search_jobs_workspace_status_queued_at", "workspace_id", "status", "queued_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(24), unique=True, default=lambda: new_public_id("job")
    )
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    search_request_id: Mapped[int | None] = mapped_column(
        ForeignKey("search_requests.id"), index=True, nullable=True
    )
    requested_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    business_type: Mapped[str] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(255))
    region: Mapped[str | None] = mapped_column(String(255), nullable=True)
    radius_km: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_results: Mapped[int] = mapped_column(Integer, default=25)

    min_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_reviews: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_reviews: Mapped[int | None] = mapped_column(Integer, nullable=True)
    website_preference: Mapped[str] = mapped_column(String(32), default=WebsitePreference.ANY.value)
    keyword_filter: Mapped[str | None] = mapped_column(String(255), nullable=True)

    status: Mapped[str] = mapped_column(String(32), default=SearchJobStatus.QUEUED.value)
    queued_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)

    candidates_found: Mapped[int] = mapped_column(Integer, default=0)
    leads_upserted: Mapped[int] = mapped_column(Integer, default=0)
    enriched_count: Mapped[int] = mapped_column(Integer, default=0)
    provider_error_count: Mapped[int] = mapped_column(Integer, default=0)

    search_request = relationship("SearchRequest", back_populates="jobs")
    leads = relationship("Lead", back_populates="search_job", cascade="all, delete-orphan")
