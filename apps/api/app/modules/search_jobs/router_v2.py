"""V2 search API — locale-aware job creation and results in the v2 lead shape.

Wraps the existing discovery pipeline (search-job → LeadDiscoveryOrchestrator)
without modifying any existing files.  The only net-new behaviour is:
  - Resolving AR/EN locale from the request and persisting it on the workspace's
    ProviderSettings before the job runs (so the SERP client picks it up).
  - Mapping internal progress-bus stage names to the v2 stage vocabulary.
  - Exposing leads in the compact V2Lead shape expected by apps/frontend.
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from queue import Empty
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.policies import get_current_user, get_current_workspace_id
from app.modules.exports.service import ExportService
from app.modules.leads.repository import LeadsRepository
from app.modules.leads.schemas import LeadSortOption
from app.modules.provider_serpapi.models import ProviderSettings
from app.modules.search_jobs.service import SearchJobService
from app.modules.users.models import User
from app.workers.orchestration.lead_discovery import LeadDiscoveryOrchestrator

router = APIRouter(prefix="/api/v2", tags=["search-v2"])

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}
_SSE_TIMEOUT_TICKS = 300

# Maps internal orchestrator stage names → v2 public stage vocabulary.
_V2_STAGE_MAP: dict[str, str] = {
    "fetching": "searching",
    "normalizing": "searching",
    "enriching": "enriching",
    "scoring": "scoring",
    "done": "done",
    "error": "done",
}

_DEFAULT_PER_PAGE = 20
_MAX_PER_PAGE = 100


# ─── Schemas ────────────────────────────────────────────────────────────────


class V2SearchRequest(BaseModel):
    query: str = Field(min_length=5, max_length=1000)
    lang: Literal["ar", "en"] = "en"
    auto_detect: bool = False


class V2SearchResponse(BaseModel):
    job_id: str
    status: str = "queued"


class V2Lead(BaseModel):
    company: str
    contact_name: str | None = None
    email: str | None = None
    email_confidence: float | None = None
    linkedin_url: str | None = None
    industry: str | None = None
    employee_count: int | None = None
    lead_score: float | None = None
    ai_opener: str | None = None
    logo_url: str | None = None


class V2ResultsResponse(BaseModel):
    items: list[V2Lead]
    page: int
    per_page: int
    total: int


# ─── Helpers ────────────────────────────────────────────────────────────────


def _resolve_locale(
    lang: Literal["ar", "en"],
    *,
    auto_detect: bool,
    accept_language: str | None,
) -> tuple[str, str]:
    """Return (hl, gl) for SERP params.  ar→(ar, sa)  en→(en, us)."""
    if auto_detect and accept_language:
        first_tag = accept_language.lower().split(",")[0].strip().split(";")[0]
        if first_tag.startswith("ar"):
            return "ar", "sa"
        return "en", "us"
    return ("ar", "sa") if lang == "ar" else ("en", "us")


def _upsert_provider_locale(db: Session, workspace_id: int, hl: str, gl: str) -> None:
    """Persist (hl, gl) on the workspace ProviderSettings before the job runs.

    The LeadDiscoveryOrchestrator reads ProviderSettings when it starts, so
    setting them here propagates the locale into every downstream SERP call.
    """
    existing = db.scalar(
        select(ProviderSettings).where(ProviderSettings.workspace_id == workspace_id)
    )
    if existing is None:
        db.add(ProviderSettings(workspace_id=workspace_id, hl=hl, gl=gl))
    else:
        existing.hl = hl
        existing.gl = gl
    db.commit()


# ─── Endpoints ──────────────────────────────────────────────────────────────


@router.post("/search", response_model=V2SearchResponse, status_code=202)
async def create_v2_search(
    payload: V2SearchRequest,
    background_tasks: BackgroundTasks,
    accept_language: Annotated[str | None, Header(alias="Accept-Language")] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> V2SearchResponse:
    """Queue a locale-aware search job from a natural-language query."""
    from app.modules.search_jobs.prompt_parser import SearchPromptParser

    hl, gl = _resolve_locale(
        payload.lang, auto_detect=payload.auto_detect, accept_language=accept_language
    )
    _upsert_provider_locale(db, workspace_id, hl, gl)

    service = SearchJobService()
    service.assert_discovery_runtime_available()

    job_request = await SearchPromptParser().parse(payload.query)
    job = service.create_search_job(
        db, job_request, workspace_id=workspace_id, requested_by_user_id=current_user.id
    )
    background_tasks.add_task(LeadDiscoveryOrchestrator().run, job.public_id)
    return V2SearchResponse(job_id=job.public_id, status="queued")


@router.get("/stream/{job_id}")
async def stream_v2_progress(
    job_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> StreamingResponse:
    """SSE stream of job progress using v2 stage vocabulary."""
    service = SearchJobService()
    job = service.get_by_public_id(db, workspace_id, job_id)

    terminal_statuses = {"completed", "partially_completed", "failed"}

    async def _terminal_stream() -> AsyncIterator[str]:
        progress = 100 if job.status in ("completed", "partially_completed") else 0
        yield (
            f"data: {json.dumps({'stage': 'done', 'progress': progress, 'message': job.status})}\n\n"
        )

    if job.status in terminal_statuses:
        return StreamingResponse(
            _terminal_stream(), media_type="text/event-stream", headers=_SSE_HEADERS
        )

    from app.core.progress_bus import register, unregister

    q = register(job_id)

    async def _live_stream() -> AsyncIterator[str]:
        ticks_without_event = 0
        try:
            while ticks_without_event < _SSE_TIMEOUT_TICKS:
                try:
                    event = await asyncio.to_thread(q.get, True, 1.0)
                    mapped: dict[str, object] = dict(event)
                    raw_stage = str(event.get("stage", ""))
                    mapped["stage"] = _V2_STAGE_MAP.get(raw_stage, "searching")
                    yield f"data: {json.dumps(mapped)}\n\n"
                    ticks_without_event = 0
                    if mapped["stage"] == "done":
                        break
                except Empty:
                    ticks_without_event += 1
                    yield ": keepalive\n\n"
        finally:
            unregister(job_id)

    return StreamingResponse(
        _live_stream(), media_type="text/event-stream", headers=_SSE_HEADERS
    )


@router.get("/results/{job_id}", response_model=V2ResultsResponse)
def get_v2_results(
    job_id: str,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=_DEFAULT_PER_PAGE, ge=1, le=_MAX_PER_PAGE),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> V2ResultsResponse:
    """Paginated leads for a search job in the compact V2Lead shape."""
    service = SearchJobService()
    service.get_by_public_id(db, workspace_id, job_id)

    repo = LeadsRepository()
    leads, total = repo.list_paginated(
        db,
        workspace_id=workspace_id,
        page=page,
        page_size=per_page,
        status=None,
        search_job_public_id=job_id,
        has_website=None,
        sort=LeadSortOption.NEWEST,
    )
    scores = repo.get_latest_scores(db, [lead.id for lead in leads])
    items = [
        V2Lead(
            company=lead.company_name,
            contact_name=None,
            email=lead.email,
            email_confidence=lead.email_confidence,
            linkedin_url=lead.linkedin_url,
            industry=lead.industry,
            employee_count=lead.employee_count,
            lead_score=float(scores[lead.id].total_score) if lead.id in scores else None,
            ai_opener=lead.ai_opener,
            logo_url=lead.logo_url,
        )
        for lead in leads
    ]
    return V2ResultsResponse(items=items, page=page, per_page=per_page, total=total)


@router.get("/export/{job_id}")
def export_v2_leads(
    job_id: str,
    export_format: Literal["csv", "json"] = Query(default="csv", alias="format"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_current_workspace_id),
) -> Response:
    """Download leads for a search job as CSV or JSON."""
    service = SearchJobService()
    service.get_by_public_id(db, workspace_id, job_id)

    payload = ExportService().export_with_billing(
        db,
        workspace_id=workspace_id,
        actor_user_id=current_user.id,
        fmt=export_format,
        search_job_public_id=job_id,
    )
    if export_format == "json":
        return Response(
            content=payload,
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="prospectiq-v2-leads.json"'},
        )
    return Response(
        content=payload,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="prospectiq-v2-leads.csv"'},
    )
