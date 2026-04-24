from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.admin.schemas import (
    ActiveScoringConfigResponse,
    OperationalHealthResponse,
    PromptTemplateCreateRequest,
    PromptTemplateListResponse,
    PromptTemplateResponse,
    ProviderSettingsResponse,
    ProviderSettingsUpdateRequest,
    ScoringConfigVersionCreateRequest,
    ScoringConfigVersionListResponse,
    ScoringConfigVersionResponse,
)
from app.modules.admin.service import AdminService
from app.modules.auth.policies import get_current_workspace_id, require_role
from app.modules.users.models import User

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


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
