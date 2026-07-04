from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.shared.enums.jobs import WebsitePreference

IcpName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class IcpProfileBase(BaseModel):
    name: IcpName
    description: str | None = Field(default=None, max_length=2000)
    target_industries: list[str] = Field(default_factory=list)
    target_cities: list[str] = Field(default_factory=list)
    min_rating: float | None = Field(default=None, ge=0, le=5)
    max_rating: float | None = Field(default=None, ge=0, le=5)
    min_reviews: int | None = Field(default=None, ge=0)
    max_reviews: int | None = Field(default=None, ge=0)
    website_preference: WebsitePreference = WebsitePreference.ANY
    required_signals: list[str] = Field(default_factory=list)
    excluded_keywords: list[str] = Field(default_factory=list)
    is_active: bool = True

    @model_validator(mode="after")
    def validate_ranges(self) -> IcpProfileBase:
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


class IcpProfileCreateRequest(IcpProfileBase):
    pass


class IcpProfileUpdateRequest(BaseModel):
    name: IcpName | None = None
    description: str | None = Field(default=None, max_length=2000)
    target_industries: list[str] | None = None
    target_cities: list[str] | None = None
    min_rating: float | None = Field(default=None, ge=0, le=5)
    max_rating: float | None = Field(default=None, ge=0, le=5)
    min_reviews: int | None = Field(default=None, ge=0)
    max_reviews: int | None = Field(default=None, ge=0)
    website_preference: WebsitePreference | None = None
    required_signals: list[str] | None = None
    excluded_keywords: list[str] | None = None
    is_active: bool | None = None


class IcpProfileResponse(IcpProfileBase):
    public_id: str
    created_at: datetime
    updated_at: datetime


class IcpProfileListResponse(BaseModel):
    items: list[IcpProfileResponse]


class LeadIcpMatchResponse(BaseModel):
    public_id: str
    lead_id: str
    icp_profile_id: str
    fit_score: float
    matched: bool
    match_reasons: dict[str, Any]
    calculated_at: datetime


class LeadIcpMatchListResponse(BaseModel):
    items: list[LeadIcpMatchResponse]
