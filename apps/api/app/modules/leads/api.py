from fastapi import APIRouter, BackgroundTasks, Body, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.ai_analysis.schemas import LeadAiEvidenceResponse
from app.modules.ai_analysis.service import AIAnalysisService
from app.modules.auth.policies import get_current_user, get_current_workspace_id
from app.modules.crm.schemas import CreateDealsFromSourceRequest, DealResponse
from app.modules.crm.service import CrmService
from app.modules.leads.schemas import (
    LeadActivityResponse,
    LeadAnalysisResponse,
    LeadAssignRequest,
    LeadEvidenceResponse,
    LeadListResponse,
    LeadNoteCreateRequest,
    LeadNoteResponse,
    LeadOutreachResponse,
    LeadResponse,
    LeadScoreBreakdownResponse,
    LeadSortOption,
    LeadStatusUpdateRequest,
)
from app.modules.leads.service import LeadsService
from app.modules.outreach.schemas import OutreachGenerateRequest
from app.modules.signals.schemas import LeadSignalsResponse
from app.modules.signals.service import LeadSignalDetectorService
from app.modules.users.models import User
from app.shared.enums.jobs import LeadScoreBand, LeadStatus
from app.workers.orchestration.lead_refresh import LeadRefreshOrchestrator

router = APIRouter(prefix="/api/v1/leads", tags=["leads"])


def _run_lead_refresh_background(
    workspace_id: int,
    lead_public_id: str,
    actor_user_id: int,
) -> None:
    LeadRefreshOrchestrator().run_for_lead(
        workspace_id=workspace_id,
        lead_public_id=lead_public_id,
        actor_user_id=actor_user_id,
    )


@router.get("", response_model=LeadListResponse)
def list_leads(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q: str | None = Query(default=None),
    city: str | None = Query(default=None),
    category: str | None = Query(default=None),
    status: LeadStatus | None = Query(default=None),
    band: LeadScoreBand | None = Query(default=None),
    min_score: float | None = Query(default=None, ge=0, le=100),
    max_score: float | None = Query(default=None, ge=0, le=100),
    qualified: bool | None = Query(default=None),
    owner_user_id: str | None = Query(default=None),
    search_job_id: str | None = Query(default=None),
    has_website: bool | None = Query(default=None),
    lead_ids: list[str] | None = Query(default=None),
    sort: LeadSortOption = Query(default=LeadSortOption.NEWEST),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> LeadListResponse:
    return LeadsService().list_leads(
        db,
        workspace_id=workspace_id,
        page=page,
        page_size=page_size,
        status=status.value if status else None,
        search_job_id=search_job_id,
        has_website=has_website,
        q=q,
        city=city,
        band=band.value if band else None,
        category=category,
        min_score=min_score,
        max_score=max_score,
        qualified=qualified,
        owner_user_id=owner_user_id,
        lead_public_ids=lead_ids,
        sort=sort,
    )


@router.get("/{lead_id}", response_model=LeadResponse)
def get_lead(
    lead_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> LeadResponse:
    return LeadsService().get_lead(db, workspace_id, lead_id)


@router.post("/{lead_id}/create-deal", response_model=DealResponse, status_code=status.HTTP_201_CREATED)
def create_lead_deal(
    lead_id: str,
    payload: CreateDealsFromSourceRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> DealResponse:
    return CrmService().create_deal_from_lead(
        db,
        workspace_id=workspace_id,
        lead_id=lead_id,
        current_user=current_user,
        allow_duplicate_open=payload.allow_duplicate_open if payload is not None else False,
    )


@router.post(
    "/{lead_id}/refresh",
    response_model=LeadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def refresh_lead(
    lead_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> LeadResponse:
    body = LeadsService().queue_refresh(db, workspace_id, lead_id, current_user=current_user)
    background_tasks.add_task(
        _run_lead_refresh_background,
        workspace_id,
        lead_id,
        current_user.id,
    )
    return body


@router.get("/{lead_id}/activity", response_model=LeadActivityResponse)
def lead_activity(
    lead_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> LeadActivityResponse:
    return LeadsService().list_activity(db, workspace_id, lead_id)


@router.post("/{lead_id}/analyze", response_model=LeadAnalysisResponse)
def analyze_lead(
    lead_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> LeadAnalysisResponse:
    return LeadsService().analyze_lead(db, workspace_id, lead_id, current_user=current_user)


@router.post("/{lead_id}/notes", response_model=LeadNoteResponse)
def create_lead_note(
    lead_id: str,
    payload: LeadNoteCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> LeadNoteResponse:
    return LeadsService().create_note(db, workspace_id, lead_id, payload, current_user=current_user)


@router.post("/{lead_id}/outreach/generate", response_model=LeadOutreachResponse)
def generate_outreach(
    lead_id: str,
    payload: OutreachGenerateRequest = Body(default_factory=OutreachGenerateRequest),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> LeadOutreachResponse:
    return LeadsService().generate_outreach(
        db,
        workspace_id,
        lead_id,
        payload=payload,
        current_user=current_user,
    )


@router.patch("/{lead_id}/status", response_model=LeadResponse)
def update_lead_status(
    lead_id: str,
    payload: LeadStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> LeadResponse:
    return LeadsService().update_status(
        db, workspace_id, lead_id, payload, current_user=current_user
    )


@router.patch("/{lead_id}/assign", response_model=LeadResponse)
def assign_lead(
    lead_id: str,
    payload: LeadAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> LeadResponse:
    return LeadsService().assign(db, workspace_id, lead_id, payload, current_user=current_user)


@router.get("/{lead_id}/evidence", response_model=LeadEvidenceResponse)
def lead_evidence(
    lead_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> LeadEvidenceResponse:
    return LeadsService().evidence(db, workspace_id, lead_id)


@router.get("/{lead_id}/score-breakdown", response_model=LeadScoreBreakdownResponse)
def lead_score_breakdown(
    lead_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> LeadScoreBreakdownResponse:
    return LeadsService().score_breakdown(db, workspace_id, lead_id)


@router.get("/{lead_id}/ai-evidence", response_model=LeadAiEvidenceResponse)
def lead_ai_evidence(
    lead_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> LeadAiEvidenceResponse:
    return AIAnalysisService().get_evidence_for_lead(
        db, workspace_id=workspace_id, lead_public_id=lead_id
    )


@router.get("/{lead_id}/signals", response_model=LeadSignalsResponse)
def lead_signals(
    lead_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> LeadSignalsResponse:
    return LeadSignalDetectorService().get_for_lead(
        db, workspace_id=workspace_id, lead_public_id=lead_id
    )


@router.post("/{lead_id}/signals/recompute", response_model=LeadSignalsResponse)
def recompute_lead_signals(
    lead_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> LeadSignalsResponse:
    return LeadSignalDetectorService().recompute_for_lead_public_id(
        db, workspace_id=workspace_id, lead_public_id=lead_id
    )
