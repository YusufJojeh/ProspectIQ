from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.admin.schemas import (
    ActiveScoringConfigResponse,
    AdminActionResponse,
    AdminAIUsageResponse,
    AdminFeatureHealthResponse,
    AdminInvoiceListResponse,
    AdminPlanListResponse,
    AdminProvidersResponse,
    AdminSearchJobListResponse,
    AdminSubscriptionListResponse,
    AdminUsageListResponse,
    AdminUserListResponse,
    AdminWorkspaceDetailResponse,
    AdminWorkspaceListResponse,
    OperationalHealthResponse,
    PlatformAdminOverviewResponse,
    PromptTemplateCreateRequest,
    PromptTemplateListResponse,
    PromptTemplateResponse,
    PromptTemplateTestRequest,
    ProviderSettingsResponse,
    ProviderSettingsUpdateRequest,
    ScoringConfigVersionCreateRequest,
    ScoringConfigVersionListResponse,
    ScoringConfigVersionResponse,
    ServiceCatalogItemCreateRequest,
    ServiceCatalogItemResponse,
    ServiceCatalogItemUpdateRequest,
    ServiceCatalogListResponse,
)
from app.modules.admin.service import AdminService
from app.modules.ai_analysis.schemas import LeadAnalysisSnapshotResponse
from app.modules.ai_analysis.service import AIAnalysisService
from app.modules.auth.policies import (
    get_current_workspace_id,
    require_platform_admin,
    require_role,
)
from app.modules.users.models import User

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/overview", response_model=PlatformAdminOverviewResponse)
def get_platform_overview(
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_admin),
) -> PlatformAdminOverviewResponse:
    return AdminService().get_platform_overview(db)


@router.get("/workspaces", response_model=AdminWorkspaceListResponse)
def list_platform_workspaces(
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_admin),
) -> AdminWorkspaceListResponse:
    return AdminService().list_platform_workspaces(db)


@router.get("/workspaces/{workspace_id}", response_model=AdminWorkspaceDetailResponse)
def get_platform_workspace(
    workspace_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_admin),
) -> AdminWorkspaceDetailResponse:
    return AdminService().get_platform_workspace_detail(db, workspace_public_id=workspace_id)


@router.post("/workspaces/{workspace_id}/disable", response_model=AdminActionResponse)
def disable_platform_workspace(
    workspace_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_platform_admin),
) -> AdminActionResponse:
    return AdminService().set_workspace_enabled(
        db,
        workspace_public_id=workspace_id,
        enabled=False,
        actor=current_user,
    )


@router.post("/workspaces/{workspace_id}/enable", response_model=AdminActionResponse)
def enable_platform_workspace(
    workspace_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_platform_admin),
) -> AdminActionResponse:
    return AdminService().set_workspace_enabled(
        db,
        workspace_public_id=workspace_id,
        enabled=True,
        actor=current_user,
    )


@router.get("/users", response_model=AdminUserListResponse)
def list_platform_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_admin),
) -> AdminUserListResponse:
    return AdminService().list_platform_users(db)


@router.post("/users/{user_id}/disable", response_model=AdminActionResponse)
def disable_platform_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_platform_admin),
) -> AdminActionResponse:
    return AdminService().set_user_enabled(
        db,
        user_public_id=user_id,
        enabled=False,
        actor=current_user,
    )


@router.post("/users/{user_id}/enable", response_model=AdminActionResponse)
def enable_platform_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_platform_admin),
) -> AdminActionResponse:
    return AdminService().set_user_enabled(
        db,
        user_public_id=user_id,
        enabled=True,
        actor=current_user,
    )


@router.get("/plans", response_model=AdminPlanListResponse)
def list_platform_plans(
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_admin),
) -> AdminPlanListResponse:
    return AdminService().list_platform_plans(db)


@router.get("/subscriptions", response_model=AdminSubscriptionListResponse)
def list_platform_subscriptions(
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_admin),
) -> AdminSubscriptionListResponse:
    return AdminService().list_platform_subscriptions(db)


@router.get("/invoices", response_model=AdminInvoiceListResponse)
def list_platform_invoices(
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_admin),
) -> AdminInvoiceListResponse:
    return AdminService().list_platform_invoices(db)


@router.get("/usage", response_model=AdminUsageListResponse)
def list_platform_usage(
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_admin),
) -> AdminUsageListResponse:
    return AdminService().list_platform_usage(db)


@router.get("/providers", response_model=AdminProvidersResponse)
def get_platform_providers(
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_admin),
) -> AdminProvidersResponse:
    return AdminService().get_platform_providers(db)


@router.get("/search-jobs", response_model=AdminSearchJobListResponse)
def list_platform_search_jobs(
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_admin),
) -> AdminSearchJobListResponse:
    return AdminService().list_platform_search_jobs(db)


@router.get("/ai-usage", response_model=AdminAIUsageResponse)
def get_platform_ai_usage(
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_admin),
) -> AdminAIUsageResponse:
    return AdminService().get_platform_ai_usage(db)


@router.get("/feature-health", response_model=AdminFeatureHealthResponse)
def get_platform_feature_health(
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_admin),
) -> AdminFeatureHealthResponse:
    return AdminService().get_platform_feature_health(db)


@router.get("/scoring-config/active", response_model=ActiveScoringConfigResponse)
def get_active_scoring_config(
    db: Session = Depends(get_db),
    workspace_id: int = Depends(get_current_workspace_id),
    _: User = Depends(require_role("account_owner", "admin")),
) -> ActiveScoringConfigResponse:
    return AdminService().get_active_scoring(db, workspace_id=workspace_id)


@router.get("/scoring-config/versions", response_model=ScoringConfigVersionListResponse)
def list_scoring_versions(
    db: Session = Depends(get_db),
    workspace_id: int = Depends(get_current_workspace_id),
    _: User = Depends(require_role("account_owner", "admin")),
) -> ScoringConfigVersionListResponse:
    return AdminService().list_scoring_versions(db, workspace_id=workspace_id)


@router.post("/scoring-config/versions", response_model=ScoringConfigVersionResponse)
def create_scoring_version(
    payload: ScoringConfigVersionCreateRequest,
    db: Session = Depends(get_db),
    workspace_id: int = Depends(get_current_workspace_id),
    current_user: User = Depends(require_role("account_owner", "admin")),
) -> ScoringConfigVersionResponse:
    return AdminService().create_scoring_version(
        db,
        workspace_id=workspace_id,
        created_by=current_user,
        actor=current_user,
        payload=payload,
    )


@router.post("/scoring-config/activate/{version_id}", response_model=ActiveScoringConfigResponse)
def activate_scoring_version(
    version_id: str,
    db: Session = Depends(get_db),
    workspace_id: int = Depends(get_current_workspace_id),
    current_user: User = Depends(require_role("account_owner", "admin")),
) -> ActiveScoringConfigResponse:
    return AdminService().activate_scoring_version(
        db,
        workspace_id=workspace_id,
        version_public_id=version_id,
        actor=current_user,
    )


@router.get("/provider-settings", response_model=ProviderSettingsResponse)
def get_provider_settings(
    db: Session = Depends(get_db),
    workspace_id: int = Depends(get_current_workspace_id),
    _: User = Depends(require_role("account_owner", "admin")),
) -> ProviderSettingsResponse:
    return AdminService().get_provider_settings(db, workspace_id=workspace_id)


@router.patch("/provider-settings", response_model=ProviderSettingsResponse)
def update_provider_settings(
    payload: ProviderSettingsUpdateRequest,
    db: Session = Depends(get_db),
    workspace_id: int = Depends(get_current_workspace_id),
    current_user: User = Depends(require_role("account_owner", "admin")),
) -> ProviderSettingsResponse:
    return AdminService().update_provider_settings(
        db,
        workspace_id=workspace_id,
        payload=payload,
        actor=current_user,
    )


@router.get("/prompt-templates", response_model=PromptTemplateListResponse)
def list_prompt_templates(
    db: Session = Depends(get_db),
    workspace_id: int = Depends(get_current_workspace_id),
    _: User = Depends(require_role("account_owner", "admin")),
) -> PromptTemplateListResponse:
    return AdminService().list_prompt_templates(db, workspace_id=workspace_id)


@router.post("/prompt-templates", response_model=PromptTemplateResponse)
def create_prompt_template(
    payload: PromptTemplateCreateRequest,
    db: Session = Depends(get_db),
    workspace_id: int = Depends(get_current_workspace_id),
    current_user: User = Depends(require_role("account_owner", "admin")),
) -> PromptTemplateResponse:
    return AdminService().create_prompt_template(
        db,
        workspace_id=workspace_id,
        payload=payload,
        actor=current_user,
    )


@router.post(
    "/prompt-templates/activate/{prompt_template_id}", response_model=PromptTemplateResponse
)
def activate_prompt_template(
    prompt_template_id: str,
    db: Session = Depends(get_db),
    workspace_id: int = Depends(get_current_workspace_id),
    current_user: User = Depends(require_role("account_owner", "admin")),
) -> PromptTemplateResponse:
    return AdminService().activate_prompt_template(
        db,
        workspace_id=workspace_id,
        prompt_template_public_id=prompt_template_id,
        actor=current_user,
    )


@router.get("/operations/health", response_model=OperationalHealthResponse)
def get_operational_health(
    db: Session = Depends(get_db),
    workspace_id: int = Depends(get_current_workspace_id),
    _: User = Depends(require_role("account_owner", "admin")),
) -> OperationalHealthResponse:
    return AdminService().get_operational_health(db, workspace_id=workspace_id)


@router.get("/service-catalog", response_model=ServiceCatalogListResponse)
def list_service_catalog(
    db: Session = Depends(get_db),
    workspace_id: int = Depends(get_current_workspace_id),
    _: User = Depends(require_role("account_owner", "admin")),
) -> ServiceCatalogListResponse:
    return AdminService().list_service_catalog(db, workspace_id=workspace_id)


@router.post("/service-catalog", response_model=ServiceCatalogItemResponse, status_code=201)
def create_catalog_item(
    payload: ServiceCatalogItemCreateRequest,
    db: Session = Depends(get_db),
    workspace_id: int = Depends(get_current_workspace_id),
    current_user: User = Depends(require_role("account_owner", "admin")),
) -> ServiceCatalogItemResponse:
    return AdminService().create_catalog_item(
        db,
        workspace_id=workspace_id,
        payload=payload,
        actor=current_user,
    )


@router.patch("/service-catalog/{item_id}", response_model=ServiceCatalogItemResponse)
def update_catalog_item(
    item_id: str,
    payload: ServiceCatalogItemUpdateRequest,
    db: Session = Depends(get_db),
    workspace_id: int = Depends(get_current_workspace_id),
    current_user: User = Depends(require_role("account_owner", "admin")),
) -> ServiceCatalogItemResponse:
    return AdminService().update_catalog_item(
        db,
        workspace_id=workspace_id,
        public_id=item_id,
        payload=payload,
        actor=current_user,
    )


@router.delete("/service-catalog/{item_id}", status_code=204)
def delete_catalog_item(
    item_id: str,
    db: Session = Depends(get_db),
    workspace_id: int = Depends(get_current_workspace_id),
    current_user: User = Depends(require_role("account_owner", "admin")),
) -> None:
    AdminService().delete_catalog_item(
        db,
        workspace_id=workspace_id,
        public_id=item_id,
        actor=current_user,
    )


@router.post("/prompt-templates/{template_id}/test", response_model=LeadAnalysisSnapshotResponse)
def test_prompt_template(
    template_id: str,
    payload: PromptTemplateTestRequest,
    db: Session = Depends(get_db),
    workspace_id: int = Depends(get_current_workspace_id),
    current_user: User = Depends(require_role("account_owner", "admin")),
) -> LeadAnalysisSnapshotResponse:
    return AIAnalysisService().test_prompt_template(
        db,
        workspace_id=workspace_id,
        template_public_id=template_id,
        lead_public_id=payload.lead_id,
        current_user=current_user,
    )
