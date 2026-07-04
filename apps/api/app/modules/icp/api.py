from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.policies import get_current_user, get_current_workspace_id
from app.modules.icp.schemas import (
    IcpProfileCreateRequest,
    IcpProfileListResponse,
    IcpProfileResponse,
    IcpProfileUpdateRequest,
    LeadIcpMatchListResponse,
    LeadIcpMatchResponse,
)
from app.modules.icp.service import IcpProfileService
from app.modules.users.models import User

router = APIRouter(prefix="/api/v1/icp-profiles", tags=["icp-profiles"])


@router.get("", response_model=IcpProfileListResponse)
def list_icp_profiles(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> IcpProfileListResponse:
    return IcpProfileService().list_profiles(db, workspace_id=workspace_id)


@router.post("", response_model=IcpProfileResponse, status_code=status.HTTP_201_CREATED)
def create_icp_profile(
    payload: IcpProfileCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> IcpProfileResponse:
    return IcpProfileService().create_profile(
        db,
        workspace_id=workspace_id,
        created_by_user_id=current_user.id,
        payload=payload,
    )


@router.patch("/{profile_id}", response_model=IcpProfileResponse)
def update_icp_profile(
    profile_id: str,
    payload: IcpProfileUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> IcpProfileResponse:
    return IcpProfileService().update_profile(
        db, workspace_id=workspace_id, profile_public_id=profile_id, payload=payload
    )


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_icp_profile(
    profile_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> Response:
    IcpProfileService().delete_profile(
        db, workspace_id=workspace_id, profile_public_id=profile_id
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{profile_id}/match/{lead_id}", response_model=LeadIcpMatchResponse)
def recompute_icp_profile_match(
    profile_id: str,
    lead_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> LeadIcpMatchResponse:
    return IcpProfileService().recompute_profile_match(
        db,
        workspace_id=workspace_id,
        profile_public_id=profile_id,
        lead_public_id=lead_id,
    )


@router.post("/leads/{lead_id}/matches", response_model=LeadIcpMatchListResponse)
def recompute_lead_icp_matches(
    lead_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> LeadIcpMatchListResponse:
    return IcpProfileService().recompute_lead_matches(
        db, workspace_id=workspace_id, lead_public_id=lead_id
    )
