from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.ai_analysis.schemas import LatestLeadAnalysisResponse, LeadAnalysisSnapshotResponse
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
