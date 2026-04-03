from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints

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


class LeadNoteCreateRequest(BaseModel):
    note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


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
    provider_fetch_public_id: str
    provider_status: str
    request_mode: str
    http_status: int | None
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
    facts: dict[str, Any]
    created_at: datetime


class LeadEvidenceResponse(BaseModel):
    lead_id: str
    items: list[LeadEvidenceItem]


class LeadNoteResponse(BaseModel):
    public_id: str
    note: str
    actor_user_public_id: str | None
    actor_full_name: str | None
    created_at: datetime


class LeadActivityEntry(BaseModel):
    entry_id: str
    entry_type: Literal["status_change", "note"]
    actor_user_public_id: str | None
    actor_full_name: str | None
    created_at: datetime
    from_status: LeadStatus | None = None
    to_status: LeadStatus | None = None
    note: str | None = None


class LeadActivityResponse(BaseModel):
    lead_id: str
    items: list[LeadActivityEntry]


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
