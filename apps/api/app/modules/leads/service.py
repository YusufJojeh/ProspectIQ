from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.modules.ai_analysis.service import AIAnalysisService
from app.modules.audit_logs.service import AuditLogService
from app.modules.billing.service import BillingService
from app.modules.leads.models import Lead, LeadNote, LeadStatusHistory
from app.modules.leads.repository import LeadsRepository
from app.modules.leads.schemas import (
    LeadActivityEntry,
    LeadActivityResponse,
    LeadAnalysisResponse,
    LeadAssignRequest,
    LeadEvidenceResponse,
    LeadListResponse,
    LeadNoteCreateRequest,
    LeadNoteResponse,
    LeadOutreachResponse,
    LeadResponse,
    LeadScoreBreakdownResponse,
    LeadSortOption,
    LeadStatusUpdateRequest,
)
from app.modules.outreach.schemas import OutreachGenerateRequest
from app.modules.outreach.service import OutreachGenerationService
from app.modules.scoring.models import LeadScore
from app.modules.scoring.repository import ScoringRepository
from app.modules.users.models import User
from app.shared.enums.jobs import LeadScoreBand, LeadStatus
from app.shared.pagination.schemas import PaginationMeta
from app.shared.services.lead_intelligence import LeadIntelligenceService
from app.workers.orchestration.lead_refresh import LeadRefreshOrchestrator


class LeadsService:
    def __init__(self) -> None:
        self.repository = LeadsRepository()
        self.analysis_service = AIAnalysisService()
        self.outreach_service = OutreachGenerationService()
        self.audit_logs = AuditLogService()
        self.billing = BillingService()
        self.scoring_repository = ScoringRepository()
        self.lead_intelligence = LeadIntelligenceService()

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
        q: str | None = None,
        city: str | None = None,
        band: str | None = None,
        category: str | None = None,
        min_score: float | None = None,
        max_score: float | None = None,
        qualified: bool | None = None,
        owner_user_id: str | None = None,
        lead_public_ids: list[str] | None = None,
        sort: LeadSortOption = LeadSortOption.NEWEST,
    ) -> LeadListResponse:
        items, total = self.repository.list_paginated(
            db,
            workspace_id=workspace_id,
            page=page,
            page_size=page_size,
            status=status,
            search_job_public_id=search_job_id,
            has_website=has_website,
            q=q,
            city=city,
            band=band,
            category=category,
            min_score=min_score,
            max_score=max_score,
            qualified=qualified,
            owner_public_id=owner_user_id,
            lead_public_ids=lead_public_ids,
            sort=sort,
        )
        latest_scores = self.repository.get_latest_scores(db, [item.id for item in items])
        assignees = self._get_assignee_public_ids(db, items)
        return LeadListResponse(
            items=[
                self._to_response(
                    item,
                    latest_scores.get(item.id),
                    self._lookup_cached_assignee_public_id(item, assignees),
                )
                for item in items
            ],
            pagination=PaginationMeta(page=page, page_size=page_size, total=total),
        )

    def get_lead(self, db: Session, workspace_id: int, lead_id: str) -> LeadResponse:
        lead = self._get_or_raise(db, workspace_id, lead_id)
        latest = self.repository.get_latest_scores(db, [lead.id]).get(lead.id)
        assignee_public_id = self._lookup_assignee_public_id(db, lead)
        return self._to_response(lead, latest, assignee_public_id)

    def list_activity(self, db: Session, workspace_id: int, lead_id: str) -> LeadActivityResponse:
        lead = self._get_or_raise(db, workspace_id, lead_id)

        items: list[LeadActivityEntry] = []
        for history, actor_public_id, actor_full_name in self.repository.list_status_history(
            db, lead.id
        ):
            items.append(
                LeadActivityEntry(
                    entry_id=f"status_{history.id}",
                    entry_type="status_change",
                    actor_user_public_id=actor_public_id,
                    actor_full_name=actor_full_name,
                    created_at=history.changed_at,
                    from_status=LeadStatus(history.from_status) if history.from_status else None,
                    to_status=LeadStatus(history.to_status),
                )
            )
        for note, actor_public_id, actor_full_name in self.repository.list_notes(db, lead.id):
            items.append(
                LeadActivityEntry(
                    entry_id=note.public_id,
                    entry_type="note",
                    actor_user_public_id=actor_public_id,
                    actor_full_name=actor_full_name,
                    created_at=note.created_at,
                    note=note.note,
                )
            )

        items.sort(key=lambda item: (item.created_at, item.entry_id), reverse=True)
        return LeadActivityResponse(lead_id=lead.public_id, items=items)

    def refresh_lead(
        self,
        db: Session,
        workspace_id: int,
        lead_id: str,
        *,
        current_user: User,
    ) -> LeadResponse:
        lead = self._get_or_raise(db, workspace_id, lead_id)
        refreshed = LeadRefreshOrchestrator().refresh(
            db,
            lead=lead,
            requested_by_user_id=current_user.id,
        )
        self.audit_logs.record(
            db,
            workspace_id=workspace_id,
            actor_user_id=current_user.id,
            event_name="lead.refreshed",
            details=f"Refreshed provider evidence and rescored lead {refreshed.public_id}.",
        )
        latest = self.repository.get_latest_scores(db, [refreshed.id]).get(refreshed.id)
        assignee_public_id = self._lookup_assignee_public_id(db, refreshed)
        return self._to_response(refreshed, latest, assignee_public_id)

    def analyze_lead(
        self,
        db: Session,
        workspace_id: int,
        lead_id: str,
        *,
        current_user: User,
    ) -> LeadAnalysisResponse:
        self.billing.enforce_usage(
            db,
            workspace_id=workspace_id,
            metric_key="ai_scoring_runs_per_month",
            actor_user_id=current_user.id,
        )
        lead = self._get_or_raise(db, workspace_id, lead_id)
        context = self.lead_intelligence.build(db, lead=lead)
        _, result = self.analysis_service.analyze(
            db,
            workspace_id=workspace_id,
            lead=lead,
            facts=context.facts,
            created_by_user_id=current_user.id,
            score_context=context.score_context,
        )
        self.audit_logs.record(
            db,
            workspace_id=workspace_id,
            actor_user_id=current_user.id,
            event_name="lead.analyzed",
            details=f"Generated an assistive analysis for lead {lead.public_id}.",
        )
        self.billing.record_usage(db, workspace_id=workspace_id, metric_key="ai_scoring_runs_per_month")
        return LeadAnalysisResponse(lead_id=lead.public_id, analysis=result)

    def create_note(
        self,
        db: Session,
        workspace_id: int,
        lead_id: str,
        payload: LeadNoteCreateRequest,
        *,
        current_user: User,
    ) -> LeadNoteResponse:
        lead = self._get_or_raise(db, workspace_id, lead_id)
        note = self.repository.add_note(
            db,
            LeadNote(
                lead_id=lead.id,
                note=payload.note,
                created_by_user_id=current_user.id,
            ),
        )
        self.audit_logs.record(
            db,
            workspace_id=workspace_id,
            actor_user_id=current_user.id,
            event_name="lead.note_added",
            details=f"Added a note to lead {lead.public_id}.",
        )
        return LeadNoteResponse(
            public_id=note.public_id,
            note=note.note,
            actor_user_public_id=current_user.public_id,
            actor_full_name=current_user.full_name,
            created_at=note.created_at,
        )

    def generate_outreach(
        self,
        db: Session,
        workspace_id: int,
        lead_id: str,
        *,
        payload: OutreachGenerateRequest,
        current_user: User,
    ) -> LeadOutreachResponse:
        self.billing.enforce_usage(
            db,
            workspace_id=workspace_id,
            metric_key="outreach_generations_per_month",
            actor_user_id=current_user.id,
        )
        lead = self._get_or_raise(db, workspace_id, lead_id)
        context = self.lead_intelligence.build(db, lead=lead)
        snapshot, analysis = self.analysis_service.analyze(
            db,
            workspace_id=workspace_id,
            lead=lead,
            facts=context.facts,
            created_by_user_id=current_user.id,
            score_context=context.score_context,
        )
        message = self.outreach_service.generate(
            db,
            lead=lead,
            snapshot=snapshot,
            analysis=analysis,
            created_by_user_id=current_user.id,
            tone=payload.tone,
            regenerate=payload.regenerate,
        )
        self.audit_logs.record(
            db,
            workspace_id=workspace_id,
            actor_user_id=current_user.id,
            event_name="lead.outreach_generated",
            details=f"Generated a {payload.tone.value} outreach draft for lead {lead.public_id}.",
        )
        self.billing.record_usage(
            db,
            workspace_id=workspace_id,
            metric_key="outreach_generations_per_month",
        )
        return LeadOutreachResponse(lead_id=lead.public_id, message=message)

    def update_status(
        self,
        db: Session,
        workspace_id: int,
        lead_id: str,
        payload: LeadStatusUpdateRequest,
        *,
        current_user: User,
    ) -> LeadResponse:
        lead = self._get_or_raise(db, workspace_id, lead_id)
        previous_status = lead.status
        lead.status = payload.status.value
        lead.updated_at = datetime.now(tz=UTC)
        saved = self.repository.save(db, lead)
        db.add(
            LeadStatusHistory(
                lead_id=saved.id,
                from_status=previous_status,
                to_status=saved.status,
                changed_by_user_id=current_user.id,
            )
        )
        if payload.note:
            db.add(
                LeadNote(
                    lead_id=saved.id,
                    note=payload.note,
                    created_by_user_id=current_user.id,
                )
            )
        db.commit()
        self.audit_logs.record(
            db,
            workspace_id=workspace_id,
            actor_user_id=current_user.id,
            event_name="lead.status_updated",
            details=f"Updated lead {saved.public_id} status from {previous_status} to {saved.status}.",
        )
        latest = self.repository.get_latest_scores(db, [saved.id]).get(saved.id)
        assignee_public_id = self._lookup_assignee_public_id(db, saved)
        return self._to_response(saved, latest, assignee_public_id)

    def assign(
        self,
        db: Session,
        workspace_id: int,
        lead_id: str,
        payload: LeadAssignRequest,
        *,
        current_user: User,
    ) -> LeadResponse:
        lead = self._get_or_raise(db, workspace_id, lead_id)
        if payload.assignee_user_public_id is None:
            lead.assigned_to_user_id = None
        else:
            from app.modules.users.repository import UsersRepository

            repo = UsersRepository()
            assignee = repo.get_by_public_id(db, workspace_id, payload.assignee_user_public_id)
            if assignee is None:
                raise NotFoundError("Assignee was not found.")
            lead.assigned_to_user_id = assignee.id
        lead.updated_at = datetime.now(tz=UTC)
        saved = self.repository.save(db, lead)
        self.audit_logs.record(
            db,
            workspace_id=workspace_id,
            actor_user_id=current_user.id,
            event_name="lead.assigned",
            details=(
                f"Assigned lead {saved.public_id} to {payload.assignee_user_public_id}."
                if payload.assignee_user_public_id
                else f"Cleared assignee for lead {saved.public_id}."
            ),
        )
        latest = self.repository.get_latest_scores(db, [saved.id]).get(saved.id)
        assignee_public_id = self._lookup_assignee_public_id(db, saved)
        return self._to_response(saved, latest, assignee_public_id)

    def evidence(self, db: Session, workspace_id: int, lead_id: str) -> LeadEvidenceResponse:
        lead = self._get_or_raise(db, workspace_id, lead_id)
        items = self.scoring_repository.list_evidence_items(db, lead.id)
        return LeadEvidenceResponse(lead_id=lead.public_id, items=items)

    def score_breakdown(
        self, db: Session, workspace_id: int, lead_id: str
    ) -> LeadScoreBreakdownResponse:
        lead = self._get_or_raise(db, workspace_id, lead_id)
        return self.scoring_repository.get_latest_score_breakdown(db, lead.id)

    def _get_or_raise(self, db: Session, workspace_id: int, lead_id: str) -> Lead:
        lead = self.repository.get_by_public_id_for_workspace(
            db,
            workspace_id=workspace_id,
            public_id=lead_id,
        )
        if lead is None:
            raise NotFoundError("Lead was not found.")
        return lead

    def _to_response(
        self,
        lead: Lead,
        latest_score: LeadScore | None,
        assignee_public_id: str | None,
    ) -> LeadResponse:
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
            status=LeadStatus(lead.status),
            assigned_to_user_public_id=assignee_public_id,
            latest_score=float(latest_score.total_score) if latest_score else None,
            latest_band=LeadScoreBand(latest_score.band) if latest_score else None,
            latest_qualified=bool(latest_score.qualified) if latest_score else None,
            created_at=lead.created_at,
            updated_at=lead.updated_at,
        )

    def _get_assignee_public_ids(self, db: Session, leads: list[Lead]) -> dict[int, str]:
        from sqlalchemy import select

        ids = {lead.assigned_to_user_id for lead in leads if lead.assigned_to_user_id is not None}
        if not ids:
            return {}
        rows = db.execute(select(User.id, User.public_id).where(User.id.in_(list(ids)))).all()
        return {int(row[0]): str(row[1]) for row in rows}

    def _lookup_assignee_public_id(self, db: Session, lead: Lead) -> str | None:
        assigned_to_user_id = lead.assigned_to_user_id
        if assigned_to_user_id is None:
            return None
        return self._get_assignee_public_ids(db, [lead]).get(assigned_to_user_id)

    def _lookup_cached_assignee_public_id(
        self,
        lead: Lead,
        assignees: dict[int, str],
    ) -> str | None:
        assigned_to_user_id = lead.assigned_to_user_id
        if assigned_to_user_id is None:
            return None
        return assignees.get(assigned_to_user_id)
