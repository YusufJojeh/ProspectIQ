from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.policies import get_current_user, get_current_workspace_id
from app.modules.outreach.schemas import (
    LatestOutreachResponse,
    OutreachDraftResponse,
    OutreachGenerateRequest,
    OutreachMessageUpdateRequest,
)
from app.modules.outreach.service import OutreachGenerationService
from app.modules.users.models import User

router = APIRouter(prefix="/api/v1/outreach", tags=["outreach"])


@router.get("/leads/{lead_id}/latest", response_model=LatestOutreachResponse)
def get_latest_outreach(
    lead_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> LatestOutreachResponse:
    return OutreachGenerationService().get_latest_for_lead(
        db,
        workspace_id=workspace_id,
        lead_public_id=lead_id,
    )


@router.post("/leads/{lead_id}/generate", response_model=OutreachDraftResponse)
def generate_outreach(
    lead_id: str,
    payload: OutreachGenerateRequest = Body(default_factory=OutreachGenerateRequest),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> OutreachDraftResponse:
    return OutreachGenerationService().generate_for_lead(
        db,
        workspace_id=workspace_id,
        lead_public_id=lead_id,
        current_user=current_user,
        payload=payload,
    )


@router.patch("/messages/{message_id}", response_model=OutreachDraftResponse)
def update_outreach_message(
    message_id: str,
    payload: OutreachMessageUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> OutreachDraftResponse:
    return OutreachGenerationService().update_draft(
        db,
        workspace_id=workspace_id,
        message_public_id=message_id,
        payload=payload,
        current_user=current_user,
    )
