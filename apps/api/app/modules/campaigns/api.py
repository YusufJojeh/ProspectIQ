from fastapi import APIRouter, Body, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.policies import get_current_user, get_current_workspace_id
from app.modules.campaigns.schemas import (
    CampaignActionResponse,
    CampaignCreateRequest,
    CampaignDetailResponse,
    CampaignGenerateDraftsResponse,
    CampaignLeadAddRequest,
    CampaignListResponse,
    CampaignUpdateRequest,
    OutreachEventResponse,
    SequenceStepResponse,
    SequenceStepUpdateRequest,
)
from app.modules.campaigns.service import CampaignService
from app.modules.crm.schemas import CampaignCreateDealsResponse, CreateDealsFromSourceRequest
from app.modules.crm.service import CrmService
from app.modules.users.models import User

router = APIRouter(prefix="/api/v1/campaigns", tags=["campaigns"])


@router.get("", response_model=CampaignListResponse)
def list_campaigns(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> CampaignListResponse:
    return CampaignService().list_campaigns(db, workspace_id=workspace_id)


@router.post("", response_model=CampaignDetailResponse, status_code=status.HTTP_201_CREATED)
def create_campaign(
    payload: CampaignCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> CampaignDetailResponse:
    return CampaignService().create_campaign(
        db, workspace_id=workspace_id, payload=payload, current_user=current_user
    )


@router.get("/{campaign_id}", response_model=CampaignDetailResponse)
def get_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> CampaignDetailResponse:
    return CampaignService().get_campaign(db, workspace_id=workspace_id, campaign_id=campaign_id)


@router.patch("/{campaign_id}", response_model=CampaignDetailResponse)
def update_campaign(
    campaign_id: str,
    payload: CampaignUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> CampaignDetailResponse:
    return CampaignService().update_campaign(
        db, workspace_id=workspace_id, campaign_id=campaign_id, payload=payload
    )


@router.delete("/{campaign_id}", response_model=CampaignActionResponse)
def delete_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> CampaignActionResponse:
    return CampaignService().archive_campaign(
        db, workspace_id=workspace_id, campaign_id=campaign_id
    )


@router.post("/{campaign_id}/leads", response_model=CampaignDetailResponse)
def add_campaign_leads(
    campaign_id: str,
    payload: CampaignLeadAddRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> CampaignDetailResponse:
    return CampaignService().add_leads(
        db, workspace_id=workspace_id, campaign_id=campaign_id, payload=payload
    )


@router.delete("/{campaign_id}/leads/{lead_id}", response_model=CampaignActionResponse)
def remove_campaign_lead(
    campaign_id: str,
    lead_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> CampaignActionResponse:
    return CampaignService().remove_lead(
        db, workspace_id=workspace_id, campaign_id=campaign_id, lead_id=lead_id
    )


@router.post("/{campaign_id}/generate-sequence", response_model=list[SequenceStepResponse])
def generate_sequence(
    campaign_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> list[SequenceStepResponse]:
    return CampaignService().generate_sequence(
        db, workspace_id=workspace_id, campaign_id=campaign_id
    )


@router.get("/{campaign_id}/sequence-steps", response_model=list[SequenceStepResponse])
def list_sequence_steps(
    campaign_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> list[SequenceStepResponse]:
    return CampaignService().list_sequence_steps(
        db, workspace_id=workspace_id, campaign_id=campaign_id
    )


@router.patch(
    "/{campaign_id}/sequence-steps/{step_id}",
    response_model=SequenceStepResponse,
)
def update_sequence_step(
    campaign_id: str,
    step_id: str,
    payload: SequenceStepUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> SequenceStepResponse:
    return CampaignService().update_sequence_step(
        db,
        workspace_id=workspace_id,
        campaign_id=campaign_id,
        step_id=step_id,
        payload=payload,
    )


@router.post("/{campaign_id}/generate-drafts", response_model=CampaignGenerateDraftsResponse)
def generate_campaign_drafts(
    campaign_id: str,
    _: object = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> CampaignGenerateDraftsResponse:
    return CampaignService().generate_drafts(
        db, workspace_id=workspace_id, campaign_id=campaign_id, current_user=current_user
    )


@router.get("/{campaign_id}/events", response_model=list[OutreachEventResponse])
def list_campaign_events(
    campaign_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> list[OutreachEventResponse]:
    return CampaignService().list_events(db, workspace_id=workspace_id, campaign_id=campaign_id)


@router.post("/{campaign_id}/create-deals", response_model=CampaignCreateDealsResponse)
def create_campaign_deals(
    campaign_id: str,
    payload: CreateDealsFromSourceRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> CampaignCreateDealsResponse:
    return CrmService().create_deals_from_campaign(
        db,
        workspace_id=workspace_id,
        campaign_id=campaign_id,
        current_user=current_user,
        allow_duplicate_open=payload.allow_duplicate_open if payload is not None else False,
    )
