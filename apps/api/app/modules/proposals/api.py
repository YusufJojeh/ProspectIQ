from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.policies import get_current_user, get_current_workspace_id
from app.modules.proposals.schemas import (
    BrandListResponse,
    ProposalCreateRequest,
    ProposalDecisionRequest,
    ProposalListResponse,
    ProposalResponse,
    ProposalUpdateRequest,
)
from app.modules.proposals.service import ProposalService
from app.modules.users.models import User

router = APIRouter(prefix="/api/v1/proposals", tags=["proposals"])


@router.get("/brands", response_model=BrandListResponse)
def list_brands(_: User = Depends(get_current_user)) -> BrandListResponse:
    return ProposalService().list_brands()


@router.get("", response_model=ProposalListResponse)
def list_proposals(
    lead_id: str | None = Query(default=None, max_length=32),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> ProposalListResponse:
    return ProposalService().list_proposals(
        db, workspace_id=workspace_id, current_user=current_user, lead_public_id=lead_id
    )


@router.post("", response_model=ProposalResponse, status_code=status.HTTP_201_CREATED)
def create_proposal(
    payload: ProposalCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> ProposalResponse:
    return ProposalService().create_for_lead(
        db, workspace_id=workspace_id, payload=payload, current_user=current_user
    )


@router.get("/{proposal_id}", response_model=ProposalResponse)
def get_proposal(
    proposal_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> ProposalResponse:
    return ProposalService().get(
        db, workspace_id=workspace_id, proposal_public_id=proposal_id, current_user=current_user
    )


@router.patch("/{proposal_id}", response_model=ProposalResponse)
def update_proposal(
    proposal_id: str,
    payload: ProposalUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> ProposalResponse:
    return ProposalService().update(
        db,
        workspace_id=workspace_id,
        proposal_public_id=proposal_id,
        payload=payload,
        current_user=current_user,
    )


@router.post("/{proposal_id}/ready", response_model=ProposalResponse)
def mark_proposal_ready(
    proposal_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> ProposalResponse:
    return ProposalService().mark_ready(
        db, workspace_id=workspace_id, proposal_public_id=proposal_id, current_user=current_user
    )


@router.post("/{proposal_id}/sent", response_model=ProposalResponse)
def mark_proposal_sent(
    proposal_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> ProposalResponse:
    return ProposalService().mark_sent(
        db, workspace_id=workspace_id, proposal_public_id=proposal_id, current_user=current_user
    )


@router.post("/{proposal_id}/decision", response_model=ProposalResponse)
def record_proposal_decision(
    proposal_id: str,
    payload: ProposalDecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> ProposalResponse:
    return ProposalService().record_decision(
        db,
        workspace_id=workspace_id,
        proposal_public_id=proposal_id,
        payload=payload,
        current_user=current_user,
    )
