from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.policies import get_current_user, get_current_workspace_id
from app.modules.search_jobs.schemas import (
    SearchJobCreateRequest,
    SearchJobListResponse,
    SearchJobResponse,
)
from app.modules.search_jobs.service import SearchJobService
from app.modules.users.models import User
from app.workers.orchestration.lead_discovery import LeadDiscoveryOrchestrator

router = APIRouter(prefix="/api/v1/search-jobs", tags=["search-jobs"])


@router.post("", response_model=SearchJobResponse, status_code=status.HTTP_202_ACCEPTED)
def create_search_job(
    payload: SearchJobCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> SearchJobResponse:
    service = SearchJobService()
    job = service.create_search_job(
        db,
        payload,
        workspace_id=workspace_id,
        requested_by_user_id=current_user.id,
    )
    background_tasks.add_task(LeadDiscoveryOrchestrator().run, job.public_id)
    return service.to_response(job)


@router.get("/{job_id}", response_model=SearchJobResponse)
def get_search_job(
    job_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> SearchJobResponse:
    service = SearchJobService()
    job = service.get_by_public_id(db, workspace_id, job_id)
    return service.to_response(job)


@router.get("", response_model=SearchJobListResponse)
def list_search_jobs(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> SearchJobListResponse:
    service = SearchJobService()
    items = service.repository.list_for_workspace(db, workspace_id)
    return SearchJobListResponse(items=[service.to_response(item) for item in items])
