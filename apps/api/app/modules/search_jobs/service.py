from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.modules.search_jobs.models import SearchJob
from app.modules.search_jobs.repository import SearchJobRepository
from app.modules.search_jobs.schemas import SearchJobCreateRequest, SearchJobResponse
from app.shared.enums.jobs import SearchJobStatus


class SearchJobService:
    def __init__(self) -> None:
        self.repository = SearchJobRepository()

    def create_search_job(
        self,
        db: Session,
        payload: SearchJobCreateRequest,
        *,
        workspace_id: int,
        requested_by_user_id: int,
    ) -> SearchJob:
        job = SearchJob(
            workspace_id=workspace_id,
            requested_by_user_id=requested_by_user_id,
            business_type=payload.business_type,
            city=payload.city,
            region=payload.region,
            max_results=payload.max_results,
            min_rating=payload.min_rating,
            min_reviews=payload.min_reviews,
            require_website=payload.require_website,
            status=SearchJobStatus.QUEUED.value,
        )
        return self.repository.add(db, job)

    def get_by_public_id(self, db: Session, workspace_id: int, public_id: str) -> SearchJob:
        job = self.repository.get_by_public_id(db, public_id)
        if job is None or job.workspace_id != workspace_id:
            raise NotFoundError("Search job was not found.")
        return job

    def to_response(self, job: SearchJob) -> SearchJobResponse:
        return SearchJobResponse(
            public_id=job.public_id,
            business_type=job.business_type,
            city=job.city,
            region=job.region,
            max_results=job.max_results,
            min_rating=job.min_rating,
            min_reviews=job.min_reviews,
            require_website=job.require_website,
            status=SearchJobStatus(job.status),
            queued_at=job.queued_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
            candidates_found=job.candidates_found,
            leads_upserted=job.leads_upserted,
            enriched_count=job.enriched_count,
            provider_error_count=job.provider_error_count,
        )
