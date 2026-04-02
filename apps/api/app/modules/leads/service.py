from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.errors import FeatureNotReadyError, NotFoundError
from app.modules.leads.models import Lead
from app.modules.leads.repository import LeadsRepository
from app.modules.leads.schemas import (
    LeadAnalysisResponse,
    LeadAssignRequest,
    LeadEvidenceResponse,
    LeadListResponse,
    LeadOutreachResponse,
    LeadResponse,
    LeadScoreBreakdownResponse,
    LeadStatusUpdateRequest,
)
from app.shared.enums.jobs import LeadScoreBand
from app.shared.pagination.schemas import PaginationMeta


class LeadsService:
    def __init__(self) -> None:
        self.repository = LeadsRepository()

    def list_leads(
        self,
        db: Session,
        *,
        workspace_id: int,
        page: int,
        page_size: int,
        status: str | None,
        search_job_id: str | None,
        has_website: bool | None,
    ) -> LeadListResponse:
        items, total = self.repository.list_paginated(
            db,
            workspace_id=workspace_id,
            page=page,
            page_size=page_size,
            status=status,
            search_job_public_id=search_job_id,
            has_website=has_website,
        )
        latest_scores = self.repository.get_latest_scores(db, [item.id for item in items])
        assignees = self._get_assignee_public_ids(db, items)
        return LeadListResponse(
            items=[
                self._to_response(item, latest_scores.get(item.id), assignees.get(item.assigned_to_user_id))
                for item in items
            ],
            pagination=PaginationMeta(page=page, page_size=page_size, total=total),
        )

    def get_lead(self, db: Session, workspace_id: int, lead_id: str) -> LeadResponse:
        lead = self._get_or_raise(db, lead_id)
        if lead.workspace_id != workspace_id:
            raise NotFoundError("Lead was not found.")
        latest = self.repository.get_latest_scores(db, [lead.id]).get(lead.id)
        assignee_public_id = None
        if lead.assigned_to_user_id is not None:
            assignee_public_id = self._get_assignee_public_ids(db, [lead]).get(lead.assigned_to_user_id)
        return self._to_response(lead, latest, assignee_public_id)

    def refresh_lead(self, db: Session, workspace_id: int, lead_id: str) -> LeadResponse:
        lead = self._get_or_raise(db, lead_id)
        if lead.workspace_id != workspace_id:
            raise NotFoundError("Lead was not found.")
        raise FeatureNotReadyError("Lead refresh will be enabled with the SerpAPI enrichment pipeline.")

    def analyze_lead(self, db: Session, workspace_id: int, lead_id: str) -> LeadAnalysisResponse:
        lead = self._get_or_raise(db, lead_id)
        if lead.workspace_id != workspace_id:
            raise NotFoundError("Lead was not found.")
        raise FeatureNotReadyError("AI analysis is not enabled in the foundation phase.")

    def generate_outreach(self, db: Session, workspace_id: int, lead_id: str) -> LeadOutreachResponse:
        lead = self._get_or_raise(db, lead_id)
        if lead.workspace_id != workspace_id:
            raise NotFoundError("Lead was not found.")
        raise FeatureNotReadyError("Outreach generation is not enabled in the foundation phase.")

    def update_status(
        self,
        db: Session,
        workspace_id: int,
        lead_id: str,
        payload: LeadStatusUpdateRequest,
    ) -> LeadResponse:
        lead = self._get_or_raise(db, lead_id)
        if lead.workspace_id != workspace_id:
            raise NotFoundError("Lead was not found.")
        lead.status = payload.status.value
        lead.updated_at = datetime.now(tz=UTC)
        saved = self.repository.save(db, lead)
        latest = self.repository.get_latest_scores(db, [saved.id]).get(saved.id)
        assignee_public_id = None
        if saved.assigned_to_user_id is not None:
            assignee_public_id = self._get_assignee_public_ids(db, [saved]).get(saved.assigned_to_user_id)
        return self._to_response(saved, latest, assignee_public_id)

    def assign(
        self,
        db: Session,
        workspace_id: int,
        lead_id: str,
        payload: LeadAssignRequest,
    ) -> LeadResponse:
        lead = self._get_or_raise(db, lead_id)
        if lead.workspace_id != workspace_id:
            raise NotFoundError("Lead was not found.")
        if payload.assignee_user_public_id is None:
            lead.assigned_to_user_id = None
        else:
            from app.modules.users.repository import UsersRepository  # local import
            from app.modules.users.models import User  # noqa: F401

            repo = UsersRepository()
            assignee = repo.get_by_public_id(db, workspace_id, payload.assignee_user_public_id)
            if assignee is None:
                raise NotFoundError("Assignee was not found.")
            lead.assigned_to_user_id = assignee.id
        lead.updated_at = datetime.now(tz=UTC)
        saved = self.repository.save(db, lead)
        latest = self.repository.get_latest_scores(db, [saved.id]).get(saved.id)
        assignee_public_id = None
        if saved.assigned_to_user_id is not None:
            assignee_public_id = self._get_assignee_public_ids(db, [saved]).get(saved.assigned_to_user_id)
        return self._to_response(saved, latest, assignee_public_id)

    def evidence(self, db: Session, workspace_id: int, lead_id: str) -> LeadEvidenceResponse:
        from app.modules.scoring.repository import ScoringRepository

        lead = self._get_or_raise(db, lead_id)
        if lead.workspace_id != workspace_id:
            raise NotFoundError("Lead was not found.")
        items = ScoringRepository().list_evidence_items(db, lead.id)
        return LeadEvidenceResponse(lead_id=lead.public_id, items=items)

    def score_breakdown(self, db: Session, workspace_id: int, lead_id: str) -> LeadScoreBreakdownResponse:
        from app.modules.scoring.repository import ScoringRepository

        lead = self._get_or_raise(db, lead_id)
        if lead.workspace_id != workspace_id:
            raise NotFoundError("Lead was not found.")
        return ScoringRepository().get_latest_score_breakdown(db, lead.id)

    def _get_or_raise(self, db: Session, lead_id: str) -> Lead:
        lead = self.repository.get_by_public_id(db, lead_id)
        if lead is None:
            raise NotFoundError("Lead was not found.")
        return lead

    def _to_response(self, lead: Lead, latest_score, assignee_public_id: str | None) -> LeadResponse:
        return LeadResponse(
            public_id=lead.public_id,
            company_name=lead.company_name,
            category=lead.category,
            address=lead.address,
            city=lead.city,
            phone=lead.phone,
            website_url=lead.website_url,
            website_domain=lead.website_domain,
            review_count=lead.review_count,
            rating=lead.rating,
            lat=lead.lat,
            lng=lead.lng,
            data_completeness=lead.data_completeness,
            data_confidence=lead.data_confidence,
            has_website=lead.has_website,
            status=lead.status,
            assigned_to_user_public_id=assignee_public_id,
            latest_score=float(latest_score.total_score) if latest_score else None,
            latest_band=LeadScoreBand(latest_score.band) if latest_score else None,
            created_at=lead.created_at,
            updated_at=lead.updated_at,
        )

    def _get_assignee_public_ids(self, db: Session, leads: list[Lead]) -> dict[int, str]:
        from sqlalchemy import select

        from app.modules.users.models import User

        ids = {lead.assigned_to_user_id for lead in leads if lead.assigned_to_user_id is not None}
        if not ids:
            return {}
        rows = db.execute(select(User.id, User.public_id).where(User.id.in_(list(ids)))).all()
        return {int(row[0]): str(row[1]) for row in rows}

    def _facts_from_lead(self, lead: Lead) -> NormalizedLeadFacts:
        from app.shared.dto.lead_facts import NormalizedLeadFacts

        return NormalizedLeadFacts(
            company_name=lead.company_name,
            category=lead.category,
            address=lead.address,
            city=lead.city,
            phone=lead.phone,
            website_url=lead.website_url,
            website_domain=lead.website_domain,
            review_count=lead.review_count,
            rating=lead.rating,
            lat=lead.lat,
            lng=lead.lng,
            data_completeness=lead.data_completeness,
            data_confidence=lead.data_confidence,
            has_website=lead.has_website,
        )
