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
    serpapi_live_reachable: bool
    serpapi_runtime_mode: str
    discovery_runtime: str
    discovery_execution_mode: str
    discovery_kill_switch: bool
    discovery_multi_engine_enabled: bool
    current_ai_runtime: str
    analysis_runtime: str
    analysis_fallback_runtime: str | None
    ollama_configured: bool
    ollama_reachable: bool
    openai_configured: bool
    openai_fallback_configured: bool
    demo_fallbacks_enabled: bool
    runtime_warnings: list[str]
    failed_jobs_last_7_days: int
    provider_failures_last_7_days: int
    recent_failed_jobs: list[RecentFailedJobResponse]
    recent_provider_failures: list[RecentProviderFailureResponse]


class PromptTemplateTestRequest(BaseModel):
    lead_id: str


class ServiceCatalogItemResponse(BaseModel):
    public_id: str
    service_name: str
    description: str | None
    is_active: bool
    rank_order: int
    created_at: datetime


class ServiceCatalogListResponse(BaseModel):
    items: list[ServiceCatalogItemResponse]
    is_default: bool


class ServiceCatalogItemCreateRequest(BaseModel):
    service_name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool = True
    rank_order: int = Field(default=1, ge=1, le=999)


class ServiceCatalogItemUpdateRequest(BaseModel):
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None
    rank_order: int | None = Field(default=None, ge=1, le=999)


__all__ = [
    "ActiveScoringConfigResponse",
    "OperationalHealthResponse",
    "PromptTemplateCreateRequest",
    "PromptTemplateListResponse",
    "PromptTemplateResponse",
    "PromptTemplateTestRequest",
    "ProviderSettingsResponse",
    "ProviderSettingsUpdateRequest",
    "RecentFailedJobResponse",
    "RecentProviderFailureResponse",
    "ScoringConfigVersionCreateRequest",
    "ScoringConfigVersionListResponse",
    "ScoringConfigVersionResponse",
    "ServiceCatalogItemCreateRequest",
    "ServiceCatalogItemResponse",
    "ServiceCatalogItemUpdateRequest",
    "ServiceCatalogListResponse",
]
