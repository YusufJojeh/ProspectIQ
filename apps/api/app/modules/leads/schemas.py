from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.ai_analysis.schemas import LeadAnalysisResult
from app.modules.outreach.schemas import OutreachMessageResult
from app.shared.enums.jobs import LeadScoreBand, LeadStatus
from app.shared.pagination.schemas import PaginationMeta


class LeadResponse(BaseModel):
    public_id: str
    company_name: str
    category: str | None
    address: str | None
    city: str | None
    phone: str | None
    website_url: str | None
    website_domain: str | None
    review_count: int
    rating: float | None
    lat: float | None
    lng: float | None
    data_completeness: float
    data_confidence: float
    has_website: bool
    status: LeadStatus
    assigned_to_user_public_id: str | None
    latest_score: float | None
    latest_band: LeadScoreBand | None
    created_at: datetime
    updated_at: datetime


class LeadListResponse(BaseModel):
    items: list[LeadResponse]
    pagination: PaginationMeta


class LeadStatusUpdateRequest(BaseModel):
    status: LeadStatus
    note: str | None = Field(default=None, max_length=500)


class LeadAnalysisResponse(BaseModel):
    lead_id: str
    analysis: LeadAnalysisResult


class LeadOutreachResponse(BaseModel):
    lead_id: str
    message: OutreachMessageResult


class LeadAssignRequest(BaseModel):
    assignee_user_public_id: str | None


class LeadEvidenceItem(BaseModel):
    source_type: str
    data_cid: str | None
    data_id: str | None
    place_id: str | None
    company_name: str
    category: str | None
    address: str | None
    city: str | None
    phone: str | None
    website_url: str | None
    website_domain: str | None
    rating: float | None
    review_count: int
    lat: float | None
    lng: float | None
    confidence: float
    completeness: float
    created_at: datetime


class LeadEvidenceResponse(BaseModel):
    lead_id: str
    items: list[LeadEvidenceItem]


class ScoreBreakdownItem(BaseModel):
    key: str
    label: str
    weight: float
    contribution: float
    reason: str


class LeadScoreBreakdownResponse(BaseModel):
    lead_id: str
    scoring_version_id: str
    total_score: float
    band: LeadScoreBand
    qualified: bool
    breakdown: list[ScoreBreakdownItem]
