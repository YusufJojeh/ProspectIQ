from typing import Any, Literal

from pydantic import BaseModel, Field


class LeadIdentityCandidate(BaseModel):
    identity_type: str
    identity_value: str


class LeadCandidate(BaseModel):
    data_cid: str | None = None
    data_id: str | None = None
    place_id: str | None = None
    company_name: str
    category: str | None = None
    address: str | None = None
    city: str | None = None
    phone: str | None = None
    website_url: str | None = None
    website_domain: str | None = None
    rating: float | None = None
    review_count: int = 0
    lat: float | None = None
    lng: float | None = None
    confidence: float = 0.7
    completeness: float = 0.5
    facts: dict[str, Any] = Field(default_factory=dict)
    identities: list[LeadIdentityCandidate] = Field(default_factory=list)


class WebsiteDiscoveryResult(BaseModel):
    website_url: str | None = None
    website_domain: str | None = None
    confidence: float = 0.6
    facts: dict[str, Any] = Field(default_factory=dict)


class PlaceLookupKey(BaseModel):
    key_type: Literal["place_id", "data_cid", "data"]
    value: str
