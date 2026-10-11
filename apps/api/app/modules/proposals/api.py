from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.policies import get_current_user, get_current_workspace_id
from app.modules.proposals.audit_service import LeadAuditService
from app.modules.proposals.brand_service import ProposalBrandService
from app.modules.proposals.schemas import (
    BrandCreateRequest,
    BrandListResponse,
    BrandResponse,
    BrandTemplateListResponse,
    BrandUpdateRequest,
    LeadAuditResponse,
    ProposalCreateRequest,
    ProposalDecisionRequest,
    ProposalListResponse,
    ProposalResponse,
    ProposalUpdateRequest,
)
from app.modules.proposals.service import ProposalService
from app.modules.users.models import User

router = APIRouter(prefix="/api/v1/proposals", tags=["proposals"])


# Brand and audit routes are declared before "/{proposal_id}" so "brands",
# "brand-templates" and "lead-audit" are never read as a proposal id.


@router.get("/lead-audit/{lead_id}", response_model=LeadAuditResponse)
def get_lead_audit(
    lead_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> LeadAuditResponse:
    return LeadAuditService().build(
        db, workspace_id=workspace_id, lead_public_id=lead_id, current_user=current_user
    )


@router.get("/brands", response_model=BrandListResponse)
def list_brands(
    include_archived: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> BrandListResponse:
    return ProposalBrandService().list_brands(
        db, workspace_id=workspace_id, current_user=current_user, include_archived=include_archived
    )


@router.get("/brand-templates", response_model=BrandTemplateListResponse)
def list_brand_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> BrandTemplateListResponse:
    return ProposalBrandService().list_templates(
        db, workspace_id=workspace_id, current_user=current_user
    )


@router.post("/brands", response_model=BrandResponse, status_code=status.HTTP_201_CREATED)
def create_brand(
    payload: BrandCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> BrandResponse:
    return ProposalBrandService().create(
        db, workspace_id=workspace_id, payload=payload, current_user=current_user
    )


@router.get("/brands/{brand_id}", response_model=BrandResponse)
def get_brand(
    brand_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> BrandResponse:
    return ProposalBrandService().get(
        db, workspace_id=workspace_id, brand_public_id=brand_id, current_user=current_user
    )


@router.patch("/brands/{brand_id}", response_model=BrandResponse)
def update_brand(
    brand_id: str,
    payload: BrandUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> BrandResponse:
    return ProposalBrandService().update(
        db,
        workspace_id=workspace_id,
        brand_public_id=brand_id,
        payload=payload,
        current_user=current_user,
    )


@router.post("/brands/{brand_id}/default", response_model=BrandResponse)
def set_default_brand(
    brand_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> BrandResponse:
    return ProposalBrandService().set_default(
        db, workspace_id=workspace_id, brand_public_id=brand_id, current_user=current_user
    )


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
