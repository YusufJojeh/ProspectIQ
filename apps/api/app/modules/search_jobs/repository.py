from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.search_jobs.models import SearchJob, SearchRequest
from app.shared.enums.jobs import SearchJobStatus


class SearchJobRepository:
    def add_request(self, db: Session, search_request: SearchRequest) -> SearchRequest:
        db.add(search_request)
        db.commit()
        db.refresh(search_request)
        return search_request

    def add(self, db: Session, job: SearchJob) -> SearchJob:
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    def get_by_public_id(self, db: Session, public_id: str) -> SearchJob | None:
        return db.scalar(select(SearchJob).where(SearchJob.public_id == public_id))

    def get_by_public_id_for_workspace(
        self, db: Session, *, workspace_id: int, public_id: str
    ) -> SearchJob | None:
        return db.scalar(
            select(SearchJob).where(
                SearchJob.public_id == public_id,
                SearchJob.workspace_id == workspace_id,
            )
        )

    def list_for_workspace(
        self, db: Session, workspace_id: int, limit: int = 50
    ) -> list[SearchJob]:
        statement = (
            select(SearchJob)
            .where(SearchJob.workspace_id == workspace_id)
            .order_by(SearchJob.queued_at.desc())
            .limit(limit)
        )
        return list(db.scalars(statement))

    def list_stale_active_for_workspace(
        self, db: Session, *, workspace_id: int, cutoff: datetime
    ) -> list[SearchJob]:
        statement = select(SearchJob).where(
            SearchJob.workspace_id == workspace_id,
            SearchJob.status.in_(
                [SearchJobStatus.QUEUED.value, SearchJobStatus.RUNNING.value]
            ),
            (
                (SearchJob.started_at.is_not(None) & (SearchJob.started_at < cutoff))
                | (SearchJob.started_at.is_(None) & (SearchJob.queued_at < cutoff))
            ),
        )
        return list(db.scalars(statement))

    def save(self, db: Session, job: SearchJob) -> SearchJob:
        db.add(job)
        db.commit()
        db.refresh(job)
        return job
