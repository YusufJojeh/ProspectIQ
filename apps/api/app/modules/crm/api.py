from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.policies import get_current_user, get_current_workspace_id
from app.modules.crm.schemas import (
    ActivityCreateRequest,
    ActivityResponse,
    ActivityUpdateRequest,
    DealActionResponse,
    DealCreateRequest,
    DealDetailResponse,
    DealListResponse,
    DealLostRequest,
    DealMoveRequest,
    DealResponse,
    DealStatus,
    DealUpdateRequest,
    PipelineCreateRequest,
    PipelineListResponse,
    PipelineResponse,
    PipelineUpdateRequest,
    StageCreateRequest,
    StageReorderRequest,
    StageResponse,
    StageUpdateRequest,
)
from app.modules.crm.service import CrmService
from app.modules.users.models import User

router = APIRouter(prefix="/api/v1/crm", tags=["crm"])


@router.get("/pipelines", response_model=PipelineListResponse)
def list_pipelines(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> PipelineListResponse:
    return CrmService().list_pipelines(db, workspace_id=workspace_id, current_user=current_user)


@router.post("/pipelines", response_model=PipelineResponse, status_code=status.HTTP_201_CREATED)
def create_pipeline(
    payload: PipelineCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> PipelineResponse:
    return CrmService().create_pipeline(
        db, workspace_id=workspace_id, current_user=current_user, payload=payload
    )


@router.get("/pipelines/{pipeline_id}", response_model=PipelineResponse)
def get_pipeline(
    pipeline_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> PipelineResponse:
    return CrmService().get_pipeline(
        db, workspace_id=workspace_id, pipeline_id=pipeline_id, current_user=current_user
    )


@router.patch("/pipelines/{pipeline_id}", response_model=PipelineResponse)
def update_pipeline(
    pipeline_id: str,
    payload: PipelineUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> PipelineResponse:
    return CrmService().update_pipeline(
        db,
        workspace_id=workspace_id,
        pipeline_id=pipeline_id,
        payload=payload,
        current_user=current_user,
    )


@router.post("/pipelines/{pipeline_id}/stages", response_model=PipelineResponse)
def create_stage(
    pipeline_id: str,
    payload: StageCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> PipelineResponse:
    return CrmService().create_stage(
        db,
        workspace_id=workspace_id,
        pipeline_id=pipeline_id,
        payload=payload,
        current_user=current_user,
    )


@router.patch("/pipelines/{pipeline_id}/stages/{stage_id}", response_model=StageResponse)
def update_stage(
    pipeline_id: str,
    stage_id: str,
    payload: StageUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> StageResponse:
    return CrmService().update_stage(
        db,
        workspace_id=workspace_id,
        pipeline_id=pipeline_id,
        stage_id=stage_id,
        payload=payload,
        current_user=current_user,
    )


@router.post("/pipelines/{pipeline_id}/stages/reorder", response_model=PipelineResponse)
def reorder_stages(
    pipeline_id: str,
    payload: StageReorderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> PipelineResponse:
    return CrmService().reorder_stages(
        db,
        workspace_id=workspace_id,
        pipeline_id=pipeline_id,
        payload=payload,
        current_user=current_user,
    )


@router.get("/deals", response_model=DealListResponse)
def list_deals(
    pipeline_id: str | None = Query(default=None),
    stage_id: str | None = Query(default=None),
    lead_id: str | None = Query(default=None),
    campaign_id: str | None = Query(default=None),
    status_filter: DealStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> DealListResponse:
    return CrmService().list_deals(
        db,
        workspace_id=workspace_id,
        current_user=current_user,
        pipeline_id=pipeline_id,
        stage_id=stage_id,
        lead_id=lead_id,
        campaign_id=campaign_id,
        status=status_filter,
    )


@router.post("/deals", response_model=DealResponse, status_code=status.HTTP_201_CREATED)
def create_deal(
    payload: DealCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> DealResponse:
    return CrmService().create_deal(
        db, workspace_id=workspace_id, current_user=current_user, payload=payload
    )


@router.get("/deals/{deal_id}", response_model=DealDetailResponse)
def get_deal(
    deal_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> DealDetailResponse:
    return CrmService().get_deal(db, workspace_id=workspace_id, deal_id=deal_id)


@router.patch("/deals/{deal_id}", response_model=DealResponse)
def update_deal(
    deal_id: str,
    payload: DealUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> DealResponse:
    return CrmService().update_deal(
        db,
        workspace_id=workspace_id,
        deal_id=deal_id,
        payload=payload,
        current_user=current_user,
    )


@router.delete("/deals/{deal_id}", response_model=DealActionResponse)
def archive_deal(
    deal_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> DealActionResponse:
    return CrmService().archive_deal(
        db, workspace_id=workspace_id, deal_id=deal_id, current_user=current_user
    )


@router.post("/deals/{deal_id}/move", response_model=DealResponse)
def move_deal(
    deal_id: str,
    payload: DealMoveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> DealResponse:
    return CrmService().move_deal(
        db,
        workspace_id=workspace_id,
        deal_id=deal_id,
        payload=payload,
        current_user=current_user,
    )


@router.post("/deals/{deal_id}/mark-won", response_model=DealResponse)
def mark_deal_won(
    deal_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> DealResponse:
    return CrmService().mark_won(
        db, workspace_id=workspace_id, deal_id=deal_id, current_user=current_user
    )


@router.post("/deals/{deal_id}/mark-lost", response_model=DealResponse)
def mark_deal_lost(
    deal_id: str,
    payload: DealLostRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> DealResponse:
    return CrmService().mark_lost(
        db,
        workspace_id=workspace_id,
        deal_id=deal_id,
        payload=payload,
        current_user=current_user,
    )


@router.post("/deals/{deal_id}/activities", response_model=ActivityResponse)
def create_activity(
    deal_id: str,
    payload: ActivityCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> ActivityResponse:
    return CrmService().create_activity(
        db,
        workspace_id=workspace_id,
        deal_id=deal_id,
        payload=payload,
        current_user=current_user,
    )


@router.patch("/deals/{deal_id}/activities/{activity_id}", response_model=ActivityResponse)
def update_activity(
    deal_id: str,
    activity_id: str,
    payload: ActivityUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> ActivityResponse:
    return CrmService().update_activity(
        db,
        workspace_id=workspace_id,
        deal_id=deal_id,
        activity_id=activity_id,
        payload=payload,
        current_user=current_user,
    )


@router.post("/deals/{deal_id}/activities/{activity_id}/complete", response_model=ActivityResponse)
def complete_activity(
    deal_id: str,
    activity_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> ActivityResponse:
    return CrmService().complete_activity(
        db,
        workspace_id=workspace_id,
        deal_id=deal_id,
        activity_id=activity_id,
        current_user=current_user,
    )
