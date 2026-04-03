from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.scoring.schemas import (
    ActiveScoringConfigResponse,
    ScoringConfigVersionCreateRequest,
    ScoringConfigVersionListResponse,
    ScoringConfigVersionResponse,
)
from app.shared.enums.jobs import SearchJobStatus


class ProviderSettingsResponse(BaseModel):
    hl: str
    gl: str
    google_domain: str
    enrich_top_n: int


class ProviderSettingsUpdateRequest(BaseModel):
    hl: str | None = Field(default=None, max_length=16)
    gl: str | None = Field(default=None, max_length=16)
    google_domain: str | None = Field(default=None, max_length=64)
    enrich_top_n: int | None = Field(default=None, ge=0, le=100)


class PromptTemplateResponse(BaseModel):
    public_id: str
    name: str
    template_text: str
    is_active: bool
    created_at: datetime
    created_by_user_public_id: str


class PromptTemplateListResponse(BaseModel):
    items: list[PromptTemplateResponse]


class PromptTemplateCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    template_text: str = Field(min_length=1, max_length=16000)
    activate: bool = True


class RecentFailedJobResponse(BaseModel):
    public_id: str
    business_type: str
    city: str
    status: SearchJobStatus
    queued_at: datetime
    finished_at: datetime | None
    provider_error_count: int


class RecentProviderFailureResponse(BaseModel):
    public_id: str
    engine: str
    mode: str
    status: str
    http_status: int | None
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None


class OperationalHealthResponse(BaseModel):
    database_ok: bool
    serpapi_configured: bool
    failed_jobs_last_7_days: int
    provider_failures_last_7_days: int
    recent_failed_jobs: list[RecentFailedJobResponse]
    recent_provider_failures: list[RecentProviderFailureResponse]


__all__ = [
    "ActiveScoringConfigResponse",
    "OperationalHealthResponse",
    "PromptTemplateCreateRequest",
    "PromptTemplateListResponse",
    "PromptTemplateResponse",
    "ProviderSettingsResponse",
    "ProviderSettingsUpdateRequest",
    "RecentFailedJobResponse",
    "RecentProviderFailureResponse",
    "ScoringConfigVersionCreateRequest",
    "ScoringConfigVersionListResponse",
    "ScoringConfigVersionResponse",
]
