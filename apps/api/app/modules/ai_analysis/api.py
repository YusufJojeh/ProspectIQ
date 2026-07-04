from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.ai_analysis.schemas import (
    AIFeedbackRequest,
    AIFeedbackResponse,
    BatchAnalysisRequest,
    BatchAnalysisResponse,
    LatestLeadAnalysisResponse,
    LeadAnalysisHistoryResponse,
    LeadAnalysisSnapshotResponse,
)
from app.modules.ai_analysis.service import AIAnalysisService
from app.modules.auth.policies import get_current_user, get_current_workspace_id
from app.modules.users.models import User

router = APIRouter(prefix="/api/v1/ai-analysis", tags=["ai-analysis"])


@router.get("/leads/{lead_id}/latest", response_model=LatestLeadAnalysisResponse)
def get_latest_lead_analysis(
    lead_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> LatestLeadAnalysisResponse:
    return AIAnalysisService().get_latest_for_lead(
        db,
        workspace_id=workspace_id,
        lead_public_id=lead_id,
    )


@router.get("/leads/{lead_id}/history", response_model=LeadAnalysisHistoryResponse)
def get_lead_analysis_history(
    lead_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> LeadAnalysisHistoryResponse:
    return AIAnalysisService().list_history_for_lead(
        db,
        workspace_id=workspace_id,
        lead_public_id=lead_id,
    )


@router.post("/leads/{lead_id}/generate", response_model=LeadAnalysisSnapshotResponse)
def generate_lead_analysis(
    lead_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> LeadAnalysisSnapshotResponse:
    return AIAnalysisService().generate_for_lead(
        db,
        workspace_id=workspace_id,
        lead_public_id=lead_id,
        current_user=current_user,
    )


@router.post("/{snapshot_id}/feedback", response_model=AIFeedbackResponse)
def submit_analysis_feedback(
    snapshot_id: str,
    payload: AIFeedbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> AIFeedbackResponse:
    return AIAnalysisService().submit_feedback(
        db,
        workspace_id=workspace_id,
        snapshot_public_id=snapshot_id,
        payload=payload,
        current_user=current_user,
    )


@router.post("/batch", response_model=BatchAnalysisResponse)
def batch_generate_analysis(
    payload: BatchAnalysisRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> BatchAnalysisResponse:
    return AIAnalysisService().generate_batch(
        db,
        workspace_id=workspace_id,
        lead_public_ids=payload.lead_ids,
        current_user=current_user,
    )
