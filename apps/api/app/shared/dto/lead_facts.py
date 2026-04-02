from pydantic import BaseModel


class NormalizedLeadFacts(BaseModel):
    company_name: str
    category: str | None = None
    address: str | None = None
    city: str | None = None
    phone: str | None = None
    website_url: str | None = None
    website_domain: str | None = None
    review_count: int = 0
    rating: float | None = None
    lat: float | None = None
    lng: float | None = None
    data_completeness: float = 0.0
    data_confidence: float = 0.0
    has_website: bool = False
    visibility_confidence: float | None = None
    visibility_source: str | None = None


class DeterministicScoreContext(BaseModel):
    total_score: float
    band: str
    qualified: bool
