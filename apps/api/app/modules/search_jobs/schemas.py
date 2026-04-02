from datetime import datetime

from pydantic import BaseModel, Field

from app.shared.enums.jobs import SearchJobStatus


class SearchJobCreateRequest(BaseModel):
    business_type: str = Field(min_length=2, max_length=255)
    city: str = Field(min_length=2, max_length=255)
    region: str | None = Field(default=None, max_length=255)
    max_results: int = Field(default=25, ge=1, le=100)
    min_rating: float | None = Field(default=None, ge=0, le=5)
    min_reviews: int | None = Field(default=None, ge=0)
    require_website: bool = False


class SearchJobResponse(BaseModel):
    public_id: str
    business_type: str
    city: str
    region: str | None
    max_results: int
    min_rating: float | None
    min_reviews: int | None
    require_website: bool
    status: SearchJobStatus
    queued_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    candidates_found: int
    leads_upserted: int
    enriched_count: int
    provider_error_count: int


class SearchJobListResponse(BaseModel):
    items: list[SearchJobResponse]
