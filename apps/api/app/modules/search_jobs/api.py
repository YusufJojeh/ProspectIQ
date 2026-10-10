import re

from fastapi import APIRouter, BackgroundTasks, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.policies import get_current_user, get_current_workspace_id
from app.modules.provider_serpapi.models import ProviderSettings
from app.modules.search_jobs.schemas import (
    SearchJobCreateRequest,
    SearchJobFromPromptRequest,
    SearchJobListResponse,
    SearchJobResponse,
)
from app.modules.search_jobs.service import SearchJobService
from app.modules.search_jobs.stream import (
    SSE_HEADERS,
    TERMINAL_STATUSES,
    live_stream,
    terminal_stream,
)
from app.modules.users.models import User
from app.workers.orchestration.lead_discovery import LeadDiscoveryOrchestrator

router = APIRouter(prefix="/api/v1/search-jobs", tags=["search-jobs"])
_ARABIC_RE = re.compile(r"[\u0600-\u06FF]")


def _apply_prompt_locale(db: Session, workspace_id: int, prompt: str) -> None:
    if not _ARABIC_RE.search(prompt):
        return
    lowered = prompt.casefold()
    gl = "sa"
    if any(
        city in lowered
        for city in (
            "\u062f\u0628\u064a",
            "\u0623\u0628\u0648\u0638\u0628\u064a",
            "\u0627\u0628\u0648\u0638\u0628\u064a",
            "\u0627\u0644\u0634\u0627\u0631\u0642\u0629",
        )
    ):
        gl = "ae"
    elif "\u0627\u0644\u062f\u0648\u062d\u0629" in lowered:
        gl = "qa"
    elif any(
        city in lowered
        for city in (
            "\u0625\u0633\u0637\u0646\u0628\u0648\u0644",
            "\u0627\u0633\u0637\u0646\u0628\u0648\u0644",
        )
    ):
        gl = "tr"

    existing = db.scalar(
        select(ProviderSettings).where(ProviderSettings.workspace_id == workspace_id)
    )
    if existing is None:
        db.add(ProviderSettings(workspace_id=workspace_id, hl="ar", gl=gl))
    else:
        existing.hl = "ar"
        existing.gl = gl
    db.commit()


@router.post("", response_model=SearchJobResponse, status_code=status.HTTP_202_ACCEPTED)
def create_search_job(
    payload: SearchJobCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> SearchJobResponse:
    service = SearchJobService()
    service.assert_discovery_runtime_available()
    job = service.create_search_job(
        db,
        payload,
        workspace_id=workspace_id,
        requested_by_user_id=current_user.id,
    )
    background_tasks.add_task(LeadDiscoveryOrchestrator().run, job.public_id)
    return service.to_response(job, db)


@router.post("/from-prompt", response_model=SearchJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_search_job_from_prompt(
    payload: SearchJobFromPromptRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> SearchJobResponse:
    from app.modules.search_jobs.prompt_parser import SearchPromptParser

    service = SearchJobService()
    service.assert_discovery_runtime_available()
    _apply_prompt_locale(db, workspace_id, payload.prompt)
    parsed_request = await SearchPromptParser().parse(payload.prompt)
    job = service.create_search_job(
        db,
        parsed_request,
        workspace_id=workspace_id,
        requested_by_user_id=current_user.id,
    )
    background_tasks.add_task(LeadDiscoveryOrchestrator().run, job.public_id)
    return service.to_response(job, db)


@router.get("/{job_id}", response_model=SearchJobResponse)
def get_search_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> SearchJobResponse:
    service = SearchJobService()
    requeued_jobs = service.requeue_stale_active_jobs(db, workspace_id=workspace_id)
    for requeued_job in requeued_jobs:
        background_tasks.add_task(LeadDiscoveryOrchestrator().run, requeued_job.public_id)
    job = service.get_by_public_id(db, workspace_id, job_id)
    return service.to_response(job, db)


@router.get("/{job_id}/stream")
async def stream_search_job_progress(
    job_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> StreamingResponse:
    job = SearchJobService().get_by_public_id(db, workspace_id, job_id)
    if job.status in TERMINAL_STATUSES:
        body = terminal_stream(job.status)
    else:
        body = live_stream(job_id, workspace_id)
    return StreamingResponse(body, media_type="text/event-stream", headers=SSE_HEADERS)


@router.get("", response_model=SearchJobListResponse)
def list_search_jobs(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> SearchJobListResponse:
    service = SearchJobService()
    requeued_jobs = service.requeue_stale_active_jobs(db, workspace_id=workspace_id)
    for requeued_job in requeued_jobs:
        background_tasks.add_task(LeadDiscoveryOrchestrator().run, requeued_job.public_id)
    items = service.repository.list_for_workspace(db, workspace_id)
    return SearchJobListResponse(items=[service.to_response(item, db) for item in items])
