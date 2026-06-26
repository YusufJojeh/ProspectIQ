from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.shared.dto.lead_score_context import LeadScoreContext


class LocalBusinessFactsInput(BaseModel):
    company_name: str
    category: str | None = None
    city: str | None = None
    address: str | None = None
    phone: str | None = None
    website_url: str | None = None
    website_domain: str | None = None
    rating: float | None = None
    review_count: int = 0
    data_completeness: float = Field(ge=0, le=1)
    data_confidence: float = Field(ge=0, le=1)
    phone_present: bool = False
    address_present: bool = False
    hours_present: bool = False
    category_clarity: float = Field(ge=0, le=1)


class PlaceEnrichmentSummary(BaseModel):
    maps_search_present: bool = False
    maps_place_present: bool = False
    official_website_found: bool = False
    official_website_source: str | None = None
    website_domain_matches_brand: bool = False
    local_presence_signal: float = Field(ge=0, le=1)


class WebVisibilitySummary(BaseModel):
    web_search_present: bool = False
    official_site_discoverability: float | None = Field(default=None, ge=0, le=1)
    official_site_position: int | None = None
    directory_results_before_official: int = 0
    directory_dominance: float = Field(ge=0, le=1)
    knowledge_graph_present: bool = False
    visibility_source: str | None = None


class LeadAnalysisInput(BaseModel):
    prompt_instructions: str | None = None
    local_business: LocalBusinessFactsInput
    place_enrichment: PlaceEnrichmentSummary
    web_visibility: WebVisibilitySummary
    deterministic_score: LeadScoreContext | None = None
    allowed_service_catalog: list[str] = Field(default_factory=list)


class LeadAnalysisResult(BaseModel):
    summary: str
    weaknesses: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    recommended_services: list[str] = Field(default_factory=list)
    outreach_subject: str
    outreach_message: str
    confidence: float = Field(ge=0, le=1)
    recommended_tone: str | None = None
    # Evidence-grounded fields (Phase 2). All optional with defaults so existing
    # snapshots and frontend consumers remain backward compatible.
    pain_points: list[str] = Field(default_factory=list)
    opportunity_reason: str | None = None
    outreach_angle: str | None = None
    risks_or_uncertainties: list[str] = Field(default_factory=list)
    evidence_used: list[str] = Field(default_factory=list)


class ServiceRecommendationResponse(BaseModel):
    public_id: str
    service_name: str
    rationale: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    rank_order: int
    created_at: datetime


class LeadAnalysisSnapshotResponse(BaseModel):
    public_id: str
    lead_id: str
    ai_provider: str
    model_name: str
    created_at: datetime
    analysis: LeadAnalysisResult
    service_recommendations: list[ServiceRecommendationResponse] = Field(default_factory=list)


class LatestLeadAnalysisResponse(BaseModel):
    lead_id: str
    snapshot: LeadAnalysisSnapshotResponse | None = None


class LeadAnalysisHistoryResponse(BaseModel):
    lead_id: str
    items: list[LeadAnalysisSnapshotResponse]


class AIEvidenceItem(BaseModel):
    public_id: str
    source_type: str
    source_url: str | None = None
    evidence_text: str
    confidence: float
    created_at: datetime


class LeadAiEvidenceResponse(BaseModel):
    lead_id: str
    snapshot_public_id: str | None = None
    items: list[AIEvidenceItem] = Field(default_factory=list)


class AIFeedbackRequest(BaseModel):
    rating: Literal["useful", "not_useful"]
    correction_text: str | None = Field(default=None, max_length=2000)


class AIFeedbackResponse(BaseModel):
    public_id: str
    snapshot_public_id: str
    rating: str
    correction_text: str | None = None
    created_at: datetime


class BatchAnalysisRequest(BaseModel):
    lead_ids: list[str] = Field(min_length=1, max_length=50)


class BatchAnalysisResult(BaseModel):
    lead_id: str
    snapshot: LeadAnalysisSnapshotResponse | None = None
    error: str | None = None


class BatchAnalysisResponse(BaseModel):
    triggered_count: int
    results: list[BatchAnalysisResult]


__all__ = [
    "AIEvidenceItem",
    "AIFeedbackRequest",
    "AIFeedbackResponse",
    "BatchAnalysisRequest",
    "BatchAnalysisResponse",
    "BatchAnalysisResult",
    "LeadAiEvidenceResponse",
    "LatestLeadAnalysisResponse",
    "LeadAnalysisHistoryResponse",
    "LeadAnalysisInput",
    "LeadAnalysisResult",
    "LeadAnalysisSnapshotResponse",
    "LeadScoreContext",
    "LocalBusinessFactsInput",
    "PlaceEnrichmentSummary",
    "ServiceRecommendationResponse",
    "WebVisibilitySummary",
]
