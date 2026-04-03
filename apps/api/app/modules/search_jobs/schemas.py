from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.shared.enums.jobs import SearchJobStatus, WebsitePreference


class SearchJobCreateRequest(BaseModel):
    business_type: str = Field(min_length=2, max_length=255)
    city: str = Field(min_length=2, max_length=255)
    region: str | None = Field(default=None, max_length=255)
    radius_km: int | None = Field(default=None, ge=1, le=500)
    max_results: int = Field(default=25, ge=1, le=100)
    min_rating: float | None = Field(default=None, ge=0, le=5)
    max_rating: float | None = Field(default=None, ge=0, le=5)
    min_reviews: int | None = Field(default=None, ge=0)
    max_reviews: int | None = Field(default=None, ge=0)
    website_preference: WebsitePreference = WebsitePreference.ANY
    keyword_filter: str | None = Field(default=None, min_length=2, max_length=255)

    @model_validator(mode="after")
    def validate_ranges(self) -> "SearchJobCreateRequest":
        if (
            self.min_rating is not None
            and self.max_rating is not None
            and self.max_rating < self.min_rating
        ):
            raise ValueError("max_rating must be greater than or equal to min_rating.")
        if (
            self.min_reviews is not None
            and self.max_reviews is not None
            and self.max_reviews < self.min_reviews
        ):
            raise ValueError("max_reviews must be greater than or equal to min_reviews.")
        return self


class SearchJobResponse(BaseModel):
    public_id: str
    business_type: str
    city: str
    region: str | None
    radius_km: int | None
    max_results: int
    min_rating: float | None
    max_rating: float | None
    min_reviews: int | None
    max_reviews: int | None
    website_preference: WebsitePreference
    keyword_filter: str | None
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
