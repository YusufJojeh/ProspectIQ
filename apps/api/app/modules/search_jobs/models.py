from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.shared.enums.jobs import SearchJobStatus
from app.shared.utils.identifiers import new_public_id


class SearchJob(Base):
    __tablename__ = "search_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(24), unique=True, default=lambda: new_public_id("job"))
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    requested_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    business_type: Mapped[str] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(255))
    region: Mapped[str | None] = mapped_column(String(255), nullable=True)
    max_results: Mapped[int] = mapped_column(Integer, default=25)

    min_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_reviews: Mapped[int | None] = mapped_column(Integer, nullable=True)
    require_website: Mapped[bool] = mapped_column(Boolean, default=False)

    status: Mapped[str] = mapped_column(String(32), default=SearchJobStatus.QUEUED.value)
    queued_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(tz=UTC))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)

    candidates_found: Mapped[int] = mapped_column(Integer, default=0)
    leads_upserted: Mapped[int] = mapped_column(Integer, default=0)
    enriched_count: Mapped[int] = mapped_column(Integer, default=0)
    provider_error_count: Mapped[int] = mapped_column(Integer, default=0)

    leads = relationship("Lead", back_populates="search_job", cascade="all, delete-orphan")
