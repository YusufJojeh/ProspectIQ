from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.modules.audit_logs.service import AuditLogService
from app.modules.leads.models import Lead
from app.modules.leads.repository import LeadsRepository
from app.modules.search_jobs.models import SearchJob
from app.shared.enums.jobs import ProviderFetchStatus, WebsitePreference
from app.workers.orchestration.lead_discovery import LeadDiscoveryOrchestrator

logger = logging.getLogger(__name__)


class LeadRefreshOrchestrator(LeadDiscoveryOrchestrator):
    def refresh(
        self,
        db: Session,
        *,
        lead: Lead,
        requested_by_user_id: int,
    ) -> Lead:
        if self.provider_service is None:
            self.provider_service = self._get_provider_service()

        refreshed_lead = lead
        job = self._job_context(db, lead, requested_by_user_id)

        lookup = self.evidence_repository.get_best_place_lookup(db, refreshed_lead.id)
        if lookup is not None:
            fetch, payload = self.provider_service.maps_place(
                db,
                workspace_id=refreshed_lead.workspace_id,
                search_job_id=refreshed_lead.search_job_id,
                lookup=lookup,
            )
            if fetch.status == ProviderFetchStatus.OK.value:
                candidate = self.maps_place_normalizer.normalize(payload)
                if candidate is not None:
                    refreshed_lead = self._upsert_candidate(
                        db,
                        job=job,
                        candidate=candidate,
                        source_type="maps_place",
                        provider_fetch_id=fetch.id,
                        priority=10,
                        allow_source_promotion=True,
                        existing_lead=refreshed_lead,
                    )

        if not refreshed_lead.website_domain:
            fetch, payload = self.provider_service.web_search(
                db,
                workspace_id=refreshed_lead.workspace_id,
                search_job_id=refreshed_lead.search_job_id,
                query=self._build_web_query(refreshed_lead),
            )
            if fetch.status == ProviderFetchStatus.OK.value:
                discovery = self.web_search_normalizer.normalize(payload)
                self._persist_web_discovery(db, refreshed_lead, fetch.id, discovery)
                db.refresh(refreshed_lead)

        self._score_leads(db, job, [refreshed_lead.id])
        db.refresh(refreshed_lead)
        return refreshed_lead

    def run_for_lead(
        self,
        *,
        workspace_id: int,
        lead_public_id: str,
        actor_user_id: int,
    ) -> None:
        """Run refresh in a dedicated session (not the HTTP request session)."""
        audit = AuditLogService()
        leads_repo = LeadsRepository()
        try:
            with self.session_factory() as db:
                lead = leads_repo.get_by_public_id_for_workspace(
                    db,
                    workspace_id=workspace_id,
                    public_id=lead_public_id,
                )
                if lead is None:
                    logger.warning(
                        "Background refresh skipped: lead %s not in workspace %s.",
                        lead_public_id,
                        workspace_id,
                    )
                    return
                refreshed = self.refresh(db, lead=lead, requested_by_user_id=actor_user_id)
                audit.record(
                    db,
                    workspace_id=workspace_id,
                    actor_user_id=actor_user_id,
                    event_name="lead.refreshed",
                    details=f"Refreshed provider evidence and rescored lead {refreshed.public_id}.",
                )
        except Exception:
            logger.exception(
                "Background refresh failed for lead %s in workspace %s.",
                lead_public_id,
                workspace_id,
            )
            try:
                with self.session_factory() as db:
                    audit.record(
                        db,
                        workspace_id=workspace_id,
                        actor_user_id=actor_user_id,
                        event_name="lead.refresh_failed",
                        details=f"Background refresh failed for lead {lead_public_id}.",
                    )
            except Exception:
                logger.exception(
                    "Failed to record refresh failure audit for lead %s.",
                    lead_public_id,
                )

    def _job_context(self, db: Session, lead: Lead, requested_by_user_id: int) -> SearchJob:
        if lead.search_job_id is not None:
            search_job = db.get(SearchJob, lead.search_job_id)
            if search_job is not None and search_job.workspace_id == lead.workspace_id:
                return search_job

        return SearchJob(
            workspace_id=lead.workspace_id,
            requested_by_user_id=requested_by_user_id,
            business_type=lead.category or "Local business",
            city=lead.city or "Unknown",
            max_results=1,
            website_preference=WebsitePreference.ANY.value,
        )
