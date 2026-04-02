from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.search_jobs.models import SearchJob


class SearchJobRepository:
    def add(self, db: Session, job: SearchJob) -> SearchJob:
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    def get_by_public_id(self, db: Session, public_id: str) -> SearchJob | None:
        return db.scalar(select(SearchJob).where(SearchJob.public_id == public_id))

    def list_for_workspace(self, db: Session, workspace_id: int, limit: int = 50) -> list[SearchJob]:
        statement = (
            select(SearchJob)
            .where(SearchJob.workspace_id == workspace_id)
            .order_by(SearchJob.queued_at.desc())
            .limit(limit)
        )
        return list(db.scalars(statement))

    def save(self, db: Session, job: SearchJob) -> SearchJob:
        db.add(job)
        db.commit()
        db.refresh(job)
        return job
