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
    phone_present: bool = False
    address_present: bool = False
    hours_present: bool = False
    maps_search_present: bool = False
    maps_place_present: bool = False
    web_search_present: bool = False
    evidence_sources_count: int = 0
    category_clarity: float = 0.0
    official_website_found: bool = False
    official_website_source: str | None = None
    website_domain_matches_brand: bool = False
    official_site_position: int | None = None
    official_site_discoverability: float | None = None
    directory_results_before_official: int = 0
    directory_dominance: float = 0.0
    knowledge_graph_present: bool = False
    local_presence_signal: float = 0.0
    weak_website_signal: float = 0.0
    digital_footprint_gap: float = 0.0
    source_agreement: float = 0.0
    maps_reviews_present: bool = False
    website_evidence_consistent: bool = False


class DeterministicScoreContext(BaseModel):
    total_score: float
    band: str
    qualified: bool
