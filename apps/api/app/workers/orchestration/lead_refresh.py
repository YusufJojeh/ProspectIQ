from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.leads.models import Lead
from app.modules.provider_serpapi.service import SerpApiService
from app.modules.search_jobs.models import SearchJob
from app.shared.enums.jobs import ProviderFetchStatus, WebsitePreference
from app.workers.orchestration.lead_discovery import LeadDiscoveryOrchestrator


class LeadRefreshOrchestrator(LeadDiscoveryOrchestrator):
    def refresh(
        self,
        db: Session,
        *,
        lead: Lead,
        requested_by_user_id: int,
    ) -> Lead:
        if self.provider_service is None:
            self.provider_service = SerpApiService()

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
