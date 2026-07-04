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


class AdminUsageMetricResponse(BaseModel):
    metric_key: str
    current_value: int


class PlatformAdminOverviewResponse(BaseModel):
    total_workspaces: int
    active_workspaces: int
    disabled_workspaces: int
    total_users: int
    active_users: int
    total_leads: int
    total_search_jobs: int
    failed_search_jobs: int
    total_ai_analyses: int
    total_evidence_rows: int
    total_icp_profiles: int
    total_signals: int
    monthly_recurring_revenue: float
    unpaid_invoices_count: int
    provider_error_count: int
    usage_by_metric: list[AdminUsageMetricResponse]


class AdminWorkspaceSummaryResponse(BaseModel):
    public_id: str
    name: str
    slug: str
    status: str
    owner_public_id: str | None
    owner_email: str | None
    users_count: int
    leads_count: int
    plan_code: str | None
    subscription_status: str | None
    created_at: datetime


class AdminWorkspaceListResponse(BaseModel):
    items: list[AdminWorkspaceSummaryResponse]


class AdminUserSummaryResponse(BaseModel):
    public_id: str
    full_name: str
    email: str
    role: str
    status: str
    workspace_public_id: str
    workspace_name: str
    last_login_at: datetime | None
    created_at: datetime


class AdminUserListResponse(BaseModel):
    items: list[AdminUserSummaryResponse]


class AdminPlanResponse(BaseModel):
    code: str
    name: str
    monthly_price: float
    yearly_price: float
    limits: dict[str, int]
    is_active: bool


class AdminPlanListResponse(BaseModel):
    items: list[AdminPlanResponse]


class AdminSubscriptionResponse(BaseModel):
    public_id: str
    workspace_public_id: str
    workspace_name: str
    plan_code: str
    plan_name: str
    status: str
    billing_cycle: str
    started_at: datetime
    renews_at: datetime | None
    ends_at: datetime | None


class AdminSubscriptionListResponse(BaseModel):
    items: list[AdminSubscriptionResponse]


class AdminInvoiceItemResponse(BaseModel):
    description: str
    amount: float
    quantity: int


class AdminPaymentAttemptResponse(BaseModel):
    public_id: str
    status: str
    simulated_result: str
    attempted_at: datetime
    error_message: str | None


class AdminInvoiceResponse(BaseModel):
    public_id: str
    workspace_public_id: str
    workspace_name: str
    amount: float
    currency: str
    status: str
    issued_at: datetime
    due_at: datetime | None
    paid_at: datetime | None
    items: list[AdminInvoiceItemResponse] = Field(default_factory=list)
    payment_attempts: list[AdminPaymentAttemptResponse] = Field(default_factory=list)


class AdminInvoiceListResponse(BaseModel):
    items: list[AdminInvoiceResponse]


class AdminUsageCounterResponse(BaseModel):
    workspace_public_id: str
    workspace_name: str
    metric_key: str
    current_value: int
    period_start: datetime
    period_end: datetime


class AdminUsageListResponse(BaseModel):
    items: list[AdminUsageCounterResponse]
    quota_override_supported: bool = False
    quota_override_todo: str = (
        "Quota override is not implemented because the current plans/usage schema "
        "does not include a per-workspace override model."
    )


class AdminProviderSettingResponse(BaseModel):
    workspace_public_id: str
    workspace_name: str
    hl: str
    gl: str
    google_domain: str
    enrich_top_n: int


class AdminProviderFetchResponse(BaseModel):
    public_id: str
    workspace_public_id: str
    workspace_name: str
    provider: str
    engine: str
    mode: str
    status: str
    http_status: int | None
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None


class AdminProvidersResponse(BaseModel):
    settings: list[AdminProviderSettingResponse]
    recent_fetches: list[AdminProviderFetchResponse]
    recent_errors: list[AdminProviderFetchResponse]
    success_count: int
    failure_count: int


class AdminSearchJobResponse(BaseModel):
    public_id: str
    workspace_public_id: str
    workspace_name: str
    business_type: str
    city: str
    status: SearchJobStatus
    queued_at: datetime
    finished_at: datetime | None
    candidates_found: int
    leads_upserted: int
    provider_error_count: int


class AdminSearchJobListResponse(BaseModel):
    items: list[AdminSearchJobResponse]


class AdminAIFeedbackSummaryResponse(BaseModel):
    rating: str
    count: int


class AdminAIFeedbackResponse(BaseModel):
    public_id: str
    workspace_public_id: str
    rating: str
    correction_text: str | None
    created_at: datetime


class AdminFlaggedAnalysisResponse(BaseModel):
    public_id: str
    workspace_public_id: str
    workspace_name: str
    lead_public_id: str
    lead_name: str
    confidence: float
    risks_or_uncertainties: list[str]
    created_at: datetime


class AdminAIUsageResponse(BaseModel):
    analyses_count: int
    evidence_rows_count: int
    feedback_counts: list[AdminAIFeedbackSummaryResponse]
    latest_feedback: list[AdminAIFeedbackResponse]
    flagged_analyses: list[AdminFlaggedAnalysisResponse]


class AdminFeatureHealthResponse(BaseModel):
    icp_profiles_count: int
    lead_signals_count: int
    scoring_versions_count: int
    lead_scores_count: int
    ai_evidence_count: int
    ai_feedback_count: int
    top_signal_types: list[AdminUsageMetricResponse]
    priority_band_distribution: list[AdminUsageMetricResponse]
    failed_jobs: list[AdminSearchJobResponse]


class AdminAuditLogResponse(BaseModel):
    public_id: str
    actor_user_public_id: str | None
    event_name: str
    details: str
    created_at: datetime


class AdminWorkspaceDetailResponse(BaseModel):
    workspace: AdminWorkspaceSummaryResponse
    owner: AdminUserSummaryResponse | None
    users: list[AdminUserSummaryResponse]
    users_count: int
    leads_count: int
    searches_count: int
    icp_profiles_count: int
    signals_count: int
    scoring_versions_count: int
    lead_scores_count: int
    ai_analyses_count: int
    ai_evidence_count: int
    ai_feedback_count: int
    subscription: AdminSubscriptionResponse | None
    invoices: list[AdminInvoiceResponse]
    usage_counters: list[AdminUsageCounterResponse]
    recent_jobs: list[AdminSearchJobResponse]
    recent_provider_errors: list[AdminProviderFetchResponse]
    recent_audit_logs: list[AdminAuditLogResponse]


class AdminActionResponse(BaseModel):
    status: str


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
