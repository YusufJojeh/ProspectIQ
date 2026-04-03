from __future__ import annotations

from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.modules.leads.models import Lead, LeadNote, LeadStatusHistory
from app.modules.leads.schemas import LeadSortOption
from app.modules.scoring.models import LeadScore
from app.modules.users.models import User


class LeadsRepository:
    def _latest_scores_subquery(self) -> Any:
        latest_scored_at = (
            select(
                LeadScore.lead_id.label("lead_id"),
                func.max(LeadScore.scored_at).label("max_scored_at"),
            )
            .group_by(LeadScore.lead_id)
            .subquery()
        )
        return (
            select(
                LeadScore.lead_id.label("lead_id"),
                LeadScore.total_score.label("total_score"),
                LeadScore.band.label("band"),
                LeadScore.qualified.label("qualified"),
            )
            .join(
                latest_scored_at,
                and_(
                    LeadScore.lead_id == latest_scored_at.c.lead_id,
                    LeadScore.scored_at == latest_scored_at.c.max_scored_at,
                ),
            )
            .subquery()
        )

    def _filtered_statements(
        self,
        *,
        workspace_id: int,
        status: str | None,
        search_job_public_id: str | None,
        has_website: bool | None,
        q: str | None,
        city: str | None,
        band: str | None,
        category: str | None,
        min_score: float | None,
        max_score: float | None,
        qualified: bool | None,
        owner_public_id: str | None,
    ) -> tuple[Any, Any, Any]:
        from app.modules.search_jobs.models import SearchJob

        latest_scores = self._latest_scores_subquery()
        statement = (
            select(Lead)
            .select_from(Lead)
            .outerjoin(latest_scores, latest_scores.c.lead_id == Lead.id)
            .where(Lead.workspace_id == workspace_id)
        )
        count_statement = (
            select(func.count(Lead.id))
            .select_from(Lead)
            .outerjoin(latest_scores, latest_scores.c.lead_id == Lead.id)
            .where(Lead.workspace_id == workspace_id)
        )

        if status is not None:
            statement = statement.where(Lead.status == status)
            count_statement = count_statement.where(Lead.status == status)
        if search_job_public_id is not None:
            statement = statement.join(SearchJob).where(SearchJob.public_id == search_job_public_id)
            count_statement = count_statement.join(SearchJob).where(
                SearchJob.public_id == search_job_public_id
            )
        if has_website is not None:
            statement = statement.where(Lead.has_website == has_website)
            count_statement = count_statement.where(Lead.has_website == has_website)
        if q:
            pattern = f"%{q.strip()}%"
            query_filter = or_(
                Lead.company_name.ilike(pattern),
                Lead.city.ilike(pattern),
                Lead.address.ilike(pattern),
                Lead.website_domain.ilike(pattern),
            )
            statement = statement.where(query_filter)
            count_statement = count_statement.where(query_filter)
        if city:
            city_filter = Lead.city.ilike(f"%{city.strip()}%")
            statement = statement.where(city_filter)
            count_statement = count_statement.where(city_filter)
        if category:
            category_filter = Lead.category.ilike(f"%{category.strip()}%")
            statement = statement.where(category_filter)
            count_statement = count_statement.where(category_filter)
        if band:
            statement = statement.where(latest_scores.c.band == band)
            count_statement = count_statement.where(latest_scores.c.band == band)
        if min_score is not None:
            statement = statement.where(latest_scores.c.total_score >= min_score)
            count_statement = count_statement.where(latest_scores.c.total_score >= min_score)
        if max_score is not None:
            statement = statement.where(latest_scores.c.total_score <= max_score)
            count_statement = count_statement.where(latest_scores.c.total_score <= max_score)
        if qualified is not None:
            statement = statement.where(latest_scores.c.qualified == qualified)
            count_statement = count_statement.where(latest_scores.c.qualified == qualified)
        if owner_public_id:
            statement = statement.join(User, User.id == Lead.assigned_to_user_id).where(
                User.public_id == owner_public_id
            )
            count_statement = count_statement.join(User, User.id == Lead.assigned_to_user_id).where(
                User.public_id == owner_public_id
            )
        return statement, count_statement, latest_scores

    def list_paginated(
        self,
        db: Session,
        *,
        workspace_id: int,
        page: int,
        page_size: int,
        status: str | None,
        search_job_public_id: str | None,
        has_website: bool | None,
        q: str | None = None,
        city: str | None = None,
        band: str | None = None,
        category: str | None = None,
        min_score: float | None = None,
        max_score: float | None = None,
        qualified: bool | None = None,
        owner_public_id: str | None = None,
        sort: LeadSortOption = LeadSortOption.NEWEST,
    ) -> tuple[list[Lead], int]:
        statement, count_statement, latest_scores = self._filtered_statements(
            workspace_id=workspace_id,
            status=status,
            search_job_public_id=search_job_public_id,
            has_website=has_website,
            q=q,
            city=city,
            band=band,
            category=category,
            min_score=min_score,
            max_score=max_score,
            qualified=qualified,
            owner_public_id=owner_public_id,
        )
        statement = statement.order_by(*self._order_by(sort, latest_scores))
        statement = statement.offset((page - 1) * page_size).limit(page_size)
        return list(db.scalars(statement)), int(db.scalar(count_statement) or 0)

    def list_all(
        self,
        db: Session,
        *,
        workspace_id: int,
        status: str | None,
        search_job_public_id: str | None,
        has_website: bool | None,
        q: str | None = None,
        city: str | None = None,
        band: str | None = None,
        category: str | None = None,
        min_score: float | None = None,
        max_score: float | None = None,
        qualified: bool | None = None,
        owner_public_id: str | None = None,
        lead_public_ids: list[str] | None = None,
        sort: LeadSortOption = LeadSortOption.NEWEST,
    ) -> list[Lead]:
        statement, _, latest_scores = self._filtered_statements(
            workspace_id=workspace_id,
            status=status,
            search_job_public_id=search_job_public_id,
            has_website=has_website,
            q=q,
            city=city,
            band=band,
            category=category,
            min_score=min_score,
            max_score=max_score,
            qualified=qualified,
            owner_public_id=owner_public_id,
        )
        if lead_public_ids:
            statement = statement.where(Lead.public_id.in_(lead_public_ids))
        return list(db.scalars(statement.order_by(*self._order_by(sort, latest_scores))))

    def get_by_public_id(self, db: Session, public_id: str) -> Lead | None:
        return db.scalar(select(Lead).where(Lead.public_id == public_id))

    def get_by_public_id_for_workspace(
        self,
        db: Session,
        *,
        workspace_id: int,
        public_id: str,
    ) -> Lead | None:
        return db.scalar(
            select(Lead).where(
                Lead.public_id == public_id,
                Lead.workspace_id == workspace_id,
            )
        )

    def get_by_id_for_workspace(self, db: Session, *, workspace_id: int, lead_id: int) -> Lead | None:
        return db.scalar(
            select(Lead).where(
                Lead.id == lead_id,
                Lead.workspace_id == workspace_id,
            )
        )

    def save(self, db: Session, lead: Lead) -> Lead:
        db.add(lead)
        db.commit()
        db.refresh(lead)
        return lead

    def add_note(self, db: Session, note: LeadNote) -> LeadNote:
        db.add(note)
        db.commit()
        db.refresh(note)
        return note

    def list_notes(
        self, db: Session, lead_id: int
    ) -> list[tuple[LeadNote, str | None, str | None]]:
        statement = (
            select(LeadNote, User.public_id, User.full_name)
            .outerjoin(User, User.id == LeadNote.created_by_user_id)
            .where(LeadNote.lead_id == lead_id)
            .order_by(LeadNote.created_at.desc(), LeadNote.id.desc())
        )
        return [
            (note, actor_public_id, actor_full_name)
            for note, actor_public_id, actor_full_name in db.execute(statement).all()
        ]

    def list_status_history(
        self, db: Session, lead_id: int
    ) -> list[tuple[LeadStatusHistory, str | None, str | None]]:
        statement = (
            select(LeadStatusHistory, User.public_id, User.full_name)
            .outerjoin(User, User.id == LeadStatusHistory.changed_by_user_id)
            .where(LeadStatusHistory.lead_id == lead_id)
            .order_by(LeadStatusHistory.changed_at.desc(), LeadStatusHistory.id.desc())
        )
        return [
            (history, actor_public_id, actor_full_name)
            for history, actor_public_id, actor_full_name in db.execute(statement).all()
        ]

    def get_latest_scores(self, db: Session, lead_ids: list[int]) -> dict[int, LeadScore]:
        if not lead_ids:
            return {}
        subq = (
            select(LeadScore.lead_id, func.max(LeadScore.scored_at).label("max_scored_at"))
            .where(LeadScore.lead_id.in_(lead_ids))
            .group_by(LeadScore.lead_id)
            .subquery()
        )
        statement = select(LeadScore).join(
            subq,
            (LeadScore.lead_id == subq.c.lead_id) & (LeadScore.scored_at == subq.c.max_scored_at),
        )
        results = list(db.scalars(statement))
        return {item.lead_id: item for item in results}

    def _order_by(self, sort: LeadSortOption, latest_scores: Any) -> tuple[Any, ...]:
        if sort == LeadSortOption.SCORE_DESC:
            return (
                latest_scores.c.total_score.is_(None),
                latest_scores.c.total_score.desc(),
                Lead.updated_at.desc(),
            )
        if sort == LeadSortOption.REVIEWS_DESC:
            return (
                Lead.review_count.desc(),
                Lead.updated_at.desc(),
            )
        if sort == LeadSortOption.RATING_DESC:
            return (
                Lead.rating.is_(None),
                Lead.rating.desc(),
                Lead.updated_at.desc(),
            )
        return (Lead.created_at.desc(), Lead.updated_at.desc())
