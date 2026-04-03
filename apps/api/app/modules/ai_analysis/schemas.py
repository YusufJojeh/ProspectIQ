from datetime import datetime

from pydantic import BaseModel, Field


class LeadScoreContext(BaseModel):
    total_score: float | None = None
    band: str | None = None
    qualified: bool | None = None
    reasons: list[str] = Field(default_factory=list)


class LeadAnalysisResult(BaseModel):
    summary: str
    weaknesses: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    recommended_services: list[str] = Field(default_factory=list)
    outreach_subject: str
    outreach_message: str
    confidence: float = Field(ge=0, le=1)


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
