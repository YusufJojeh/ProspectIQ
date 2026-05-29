import asyncio
import json
from collections.abc import AsyncIterator
from queue import Empty

from fastapi import APIRouter, BackgroundTasks, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.policies import get_current_user, get_current_workspace_id
from app.modules.search_jobs.schemas import (
    SearchJobCreateRequest,
    SearchJobFromPromptRequest,
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
    service.assert_discovery_runtime_available()
    job = service.create_search_job(
        db,
        payload,
        workspace_id=workspace_id,
        requested_by_user_id=current_user.id,
    )
    background_tasks.add_task(LeadDiscoveryOrchestrator().run, job.public_id)
    return service.to_response(job)


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
    parsed_request = await SearchPromptParser().parse(payload.prompt)
    job = service.create_search_job(
        db,
        parsed_request,
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


_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}
_SSE_TIMEOUT_TICKS = 300  # 1 s per tick → 5-minute max stream


@router.get("/{job_id}/stream")
async def stream_search_job_progress(
    job_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> StreamingResponse:
    service = SearchJobService()
    job = service.get_by_public_id(db, workspace_id, job_id)

    terminal_statuses = {"completed", "partially_completed", "failed"}

    async def _terminal_stream() -> AsyncIterator[str]:
        stage = "done" if job.status in ("completed", "partially_completed") else "error"
        progress = 100 if stage == "done" else 0
        yield f"data: {json.dumps({'stage': stage, 'progress': progress, 'message': job.status})}\n\n"

    if job.status in terminal_statuses:
        return StreamingResponse(_terminal_stream(), media_type="text/event-stream", headers=_SSE_HEADERS)

    from app.core.progress_bus import register, unregister

    q = register(job_id)

    async def _live_stream() -> AsyncIterator[str]:
        ticks_without_event = 0
        try:
            while ticks_without_event < _SSE_TIMEOUT_TICKS:
                try:
                    event = await asyncio.to_thread(q.get, True, 1.0)
                    yield f"data: {json.dumps(event)}\n\n"
                    ticks_without_event = 0
                    if event.get("stage") in ("done", "error"):
                        break
                except Empty:
                    ticks_without_event += 1
                    yield ": keepalive\n\n"
        finally:
            unregister(job_id)

    return StreamingResponse(_live_stream(), media_type="text/event-stream", headers=_SSE_HEADERS)


@router.get("", response_model=SearchJobListResponse)
def list_search_jobs(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> SearchJobListResponse:
    service = SearchJobService()
    items = service.repository.list_for_workspace(db, workspace_id)
    return SearchJobListResponse(items=[service.to_response(item) for item in items])
