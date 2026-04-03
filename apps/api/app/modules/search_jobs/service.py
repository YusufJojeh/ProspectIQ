from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.modules.audit_logs.service import AuditLogService
from app.modules.search_jobs.models import SearchJob, SearchRequest
from app.modules.search_jobs.repository import SearchJobRepository
from app.modules.search_jobs.schemas import SearchJobCreateRequest, SearchJobResponse
from app.shared.enums.jobs import SearchJobStatus, WebsitePreference


class SearchJobService:
    def __init__(self) -> None:
        self.repository = SearchJobRepository()
        self.audit_logs = AuditLogService()

    def create_search_job(
        self,
        db: Session,
        payload: SearchJobCreateRequest,
        *,
        workspace_id: int,
        requested_by_user_id: int,
    ) -> SearchJob:
        search_request = self.repository.add_request(
            db,
            SearchRequest(
                workspace_id=workspace_id,
                requested_by_user_id=requested_by_user_id,
                business_type=payload.business_type,
                city=payload.city,
                region=payload.region,
                radius_km=payload.radius_km,
                max_results=payload.max_results,
                min_rating=payload.min_rating,
                max_rating=payload.max_rating,
                min_reviews=payload.min_reviews,
                max_reviews=payload.max_reviews,
                website_preference=payload.website_preference.value,
                keyword_filter=payload.keyword_filter,
            ),
        )
        job = SearchJob(
            workspace_id=workspace_id,
            search_request_id=search_request.id,
            requested_by_user_id=requested_by_user_id,
            business_type=payload.business_type,
            city=payload.city,
            region=payload.region,
            radius_km=payload.radius_km,
            max_results=payload.max_results,
            min_rating=payload.min_rating,
            max_rating=payload.max_rating,
            min_reviews=payload.min_reviews,
            max_reviews=payload.max_reviews,
            website_preference=payload.website_preference.value,
            keyword_filter=payload.keyword_filter,
            status=SearchJobStatus.QUEUED.value,
        )
        saved = self.repository.add(db, job)
        self.audit_logs.record(
            db,
            workspace_id=workspace_id,
            actor_user_id=requested_by_user_id,
            event_name="search_job.created",
            details=(
                f"Queued search job {saved.public_id} for {saved.business_type} in {saved.city}"
                f"{f', {saved.region}' if saved.region else ''}"
                f"{f' with keyword {saved.keyword_filter!r}' if saved.keyword_filter else ''}."
            ),
        )
        return saved

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
            radius_km=job.radius_km,
            max_results=job.max_results,
            min_rating=job.min_rating,
            max_rating=job.max_rating,
            min_reviews=job.min_reviews,
            max_reviews=job.max_reviews,
            website_preference=WebsitePreference(job.website_preference),
            keyword_filter=job.keyword_filter,
            status=SearchJobStatus(job.status),
            queued_at=job.queued_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
            candidates_found=job.candidates_found,
            leads_upserted=job.leads_upserted,
            enriched_count=job.enriched_count,
            provider_error_count=job.provider_error_count,
        )
