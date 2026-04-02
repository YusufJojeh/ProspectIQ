from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy.orm import Session, sessionmaker

from app.core.database import get_session_factory
from app.modules.leads.models import Lead
from app.modules.provider_serpapi.models import ProviderNormalizedFact
from app.modules.provider_serpapi.normalizers.maps_local_normalizer import MapsLocalNormalizer
from app.modules.provider_serpapi.normalizers.maps_place_normalizer import MapsPlaceNormalizer
from app.modules.provider_serpapi.normalizers.web_search_normalizer import WebSearchNormalizer
from app.modules.provider_serpapi.repository import ProviderEvidenceRepository
from app.modules.provider_serpapi.schemas import LeadCandidate, WebsiteDiscoveryResult
from app.modules.provider_serpapi.service import SerpApiService
from app.modules.scoring.schemas import ScoringThresholds, ScoringWeights
from app.modules.scoring.service import ScoringConfigService, ScoringEngine, persist_lead_score
from app.modules.search_jobs.models import SearchJob
from app.modules.search_jobs.repository import SearchJobRepository
from app.shared.dto.lead_facts import NormalizedLeadFacts
from app.shared.enums.jobs import ProviderFetchStatus, SearchJobStatus

logger = logging.getLogger(__name__)


class ProviderServiceProtocol(Protocol):
    def get_settings(self, db: Session, workspace_id: int): ...

    def maps_search(
        self,
        db: Session,
        *,
        workspace_id: int,
        search_job_id: int,
        business_type: str,
        city: str,
        region: str | None,
        attempt: int = 1,
    ): ...

    def maps_place(
        self,
        db: Session,
        *,
        workspace_id: int,
        search_job_id: int | None,
        place_key: str,
        attempt: int = 1,
    ): ...

    def web_search(
        self,
        db: Session,
        *,
        workspace_id: int,
        search_job_id: int | None,
        query: str,
        attempt: int = 1,
    ): ...


class LeadDiscoveryOrchestrator:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] | None = None,
        provider_service: ProviderServiceProtocol | None = None,
        search_job_repository: SearchJobRepository | None = None,
        evidence_repository: ProviderEvidenceRepository | None = None,
        maps_local_normalizer: MapsLocalNormalizer | None = None,
        maps_place_normalizer: MapsPlaceNormalizer | None = None,
        web_search_normalizer: WebSearchNormalizer | None = None,
        scoring_engine: ScoringEngine | None = None,
        scoring_config_service: ScoringConfigService | None = None,
    ) -> None:
        self.session_factory = session_factory or get_session_factory()
        self.provider_service = provider_service
        self.search_job_repository = search_job_repository or SearchJobRepository()
        self.evidence_repository = evidence_repository or ProviderEvidenceRepository()
        self.maps_local_normalizer = maps_local_normalizer or MapsLocalNormalizer()
        self.maps_place_normalizer = maps_place_normalizer or MapsPlaceNormalizer()
        self.web_search_normalizer = web_search_normalizer or WebSearchNormalizer()
        self.scoring_engine = scoring_engine or ScoringEngine()
        self.scoring_config_service = scoring_config_service or ScoringConfigService()

    def run(self, job_public_id: str) -> None:
        if self.provider_service is None:
            self.provider_service = SerpApiService()
        with self.session_factory() as db:
            job = self.search_job_repository.get_by_public_id(db, job_public_id)
            if job is None:
                logger.warning("Search job '%s' was not found for orchestration.", job_public_id)
                return

            try:
                self._mark_running(db, job)
                lead_ids = self._discover_leads(db, job)
                if lead_ids:
                    self._enrich_top_candidates(db, job, lead_ids)
                    self._validate_web_presence(db, job, lead_ids)
                    self._score_leads(db, job, lead_ids)
                self._finalize_status(db, job)
            except Exception as exc:
                logger.exception("Lead discovery failed for search job '%s'.", job_public_id)
                self._mark_failed(db, job, str(exc))

    def _discover_leads(self, db: Session, job: SearchJob) -> list[int]:
        fetch, payload = self.provider_service.maps_search(
            db,
            workspace_id=job.workspace_id,
            search_job_id=job.id,
            business_type=job.business_type,
            city=job.city,
            region=job.region,
        )
        if fetch.status != ProviderFetchStatus.OK.value:
            job.provider_error_count += 1
        candidates = self.maps_local_normalizer.normalize(payload)[: job.max_results]
        job.candidates_found = len(candidates)
        self.search_job_repository.save(db, job)

        lead_ids: set[int] = set()
        for candidate in candidates:
            lead = self._upsert_candidate(
                db,
                job=job,
                candidate=candidate,
                source_type="maps_search",
                provider_fetch_id=fetch.id,
                priority=20,
                allow_source_promotion=True,
            )
            lead_ids.add(lead.id)

        job.leads_upserted = len(lead_ids)
        self.search_job_repository.save(db, job)
        self._score_leads(db, job, list(lead_ids))
        return list(lead_ids)

    def _enrich_top_candidates(self, db: Session, job: SearchJob, lead_ids: list[int]) -> None:
        settings = self.provider_service.get_settings(db, job.workspace_id)
        for lead in self._select_enrichment_targets(db, lead_ids, limit=settings.enrich_top_n):
            place_key = self.evidence_repository.get_best_place_key(db, lead.id)
            if not place_key:
                continue

            fetch, payload = self.provider_service.maps_place(
                db,
                workspace_id=job.workspace_id,
                search_job_id=job.id,
                place_key=place_key,
            )
            if fetch.status != ProviderFetchStatus.OK.value:
                job.provider_error_count += 1
                self.search_job_repository.save(db, job)
                continue

            candidate = self.maps_place_normalizer.normalize(payload)
            if candidate is None:
                continue

            self._upsert_candidate(
                db,
                job=job,
                candidate=candidate,
                source_type="maps_place",
                provider_fetch_id=fetch.id,
                priority=10,
                allow_source_promotion=True,
                existing_lead=lead,
            )
            job.enriched_count += 1
            self.search_job_repository.save(db, job)

    def _validate_web_presence(self, db: Session, job: SearchJob, lead_ids: list[int]) -> None:
        for lead in self._list_leads(db, lead_ids):
            if lead.website_domain:
                continue
            query = self._build_web_query(lead)
            fetch, payload = self.provider_service.web_search(
                db,
                workspace_id=job.workspace_id,
                search_job_id=job.id,
                query=query,
            )
            if fetch.status != ProviderFetchStatus.OK.value:
                job.provider_error_count += 1
                self.search_job_repository.save(db, job)
                continue

            discovery = self.web_search_normalizer.normalize(payload)
            self._persist_web_discovery(db, lead, fetch.id, discovery)

    def _score_leads(self, db: Session, job: SearchJob, lead_ids: list[int]) -> None:
        if not lead_ids:
            return
        version = self.scoring_config_service.ensure_active_version(
            db,
            job.workspace_id,
            created_by_user_id=job.requested_by_user_id,
        )
        weights = ScoringWeights.model_validate(version.weights_json)
        thresholds = ScoringThresholds.model_validate(version.thresholds_json)

        for lead in self._list_leads(db, lead_ids):
            visibility_confidence, visibility_source = self.evidence_repository.get_latest_visibility(db, lead.id)
            facts = NormalizedLeadFacts(
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
                visibility_confidence=visibility_confidence,
                visibility_source=visibility_source,
            )
            result = self.scoring_engine.evaluate(
                facts,
                weights=weights,
                thresholds=thresholds,
                is_qualified_candidate=self._qualifies(job, lead),
            )
            persist_lead_score(
                db,
                lead_id=lead.id,
                scoring_config_version_id=version.id,
                result=result,
            )

    def _upsert_candidate(
        self,
        db: Session,
        *,
        job: SearchJob,
        candidate: LeadCandidate,
        source_type: str,
        provider_fetch_id: int,
        priority: int,
        allow_source_promotion: bool,
        existing_lead: Lead | None = None,
    ) -> Lead:
        lead = existing_lead or self.evidence_repository.find_lead_by_identities(
            db,
            workspace_id=job.workspace_id,
            identities=candidate.identities,
        )
        if lead is None:
            lead = Lead(
                workspace_id=job.workspace_id,
                search_job_id=job.id,
                company_name=candidate.company_name,
                category=candidate.category,
                address=candidate.address,
                city=candidate.city,
                phone=candidate.phone,
                website_url=candidate.website_url,
                website_domain=candidate.website_domain,
                review_count=candidate.review_count,
                rating=candidate.rating,
                lat=candidate.lat,
                lng=candidate.lng,
                data_completeness=candidate.completeness,
                data_confidence=candidate.confidence,
                has_website=bool(candidate.website_url or candidate.website_domain),
            )
            lead = self.evidence_repository.save_lead(db, lead)
        else:
            self._merge_lead(
                lead,
                candidate=candidate,
                search_job_id=job.id,
                priority=priority,
                current_priority=self.evidence_repository.get_best_source_priority(db, lead.id),
                allow_source_promotion=allow_source_promotion,
            )
            lead = self.evidence_repository.save_lead(db, lead)

        self.evidence_repository.ensure_identities(
            db,
            workspace_id=job.workspace_id,
            lead_id=lead.id,
            identities=candidate.identities,
        )
        fact = self.evidence_repository.add_normalized_fact(
            db,
            ProviderNormalizedFact(
                workspace_id=job.workspace_id,
                lead_id=lead.id,
                provider_fetch_id=provider_fetch_id,
                source_type=source_type,
                data_cid=candidate.data_cid,
                data_id=candidate.data_id,
                place_id=candidate.place_id,
                company_name=candidate.company_name,
                category=candidate.category,
                address=candidate.address,
                city=candidate.city,
                phone=candidate.phone,
                website_url=candidate.website_url,
                website_domain=candidate.website_domain,
                rating=candidate.rating,
                review_count=candidate.review_count,
                lat=candidate.lat,
                lng=candidate.lng,
                confidence=candidate.confidence,
                completeness=candidate.completeness,
                facts_json=candidate.facts,
            ),
        )
        current_priority = self.evidence_repository.get_best_source_priority(db, lead.id)
        is_current = current_priority is None or priority <= current_priority
        self.evidence_repository.set_source_record(
            db,
            lead_id=lead.id,
            provider_normalized_fact_id=fact.id,
            priority=priority,
            is_current=is_current,
        )
        return lead

    def _persist_web_discovery(
        self,
        db: Session,
        lead: Lead,
        provider_fetch_id: int,
        discovery: WebsiteDiscoveryResult,
    ) -> None:
        fact = self.evidence_repository.add_normalized_fact(
            db,
            ProviderNormalizedFact(
                workspace_id=lead.workspace_id,
                lead_id=lead.id,
                provider_fetch_id=provider_fetch_id,
                source_type="web_search",
                data_cid=None,
                data_id=None,
                place_id=None,
                company_name=lead.company_name,
                category=lead.category,
                address=lead.address,
                city=lead.city,
                phone=lead.phone,
                website_url=discovery.website_url,
                website_domain=discovery.website_domain,
                rating=lead.rating,
                review_count=lead.review_count,
                lat=lead.lat,
                lng=lead.lng,
                confidence=discovery.confidence,
                completeness=lead.data_completeness,
                facts_json={
                    **discovery.facts,
                    "visibility_confidence": discovery.confidence,
                },
            ),
        )
        self.evidence_repository.set_source_record(
            db,
            lead_id=lead.id,
            provider_normalized_fact_id=fact.id,
            priority=30,
            is_current=False,
        )
        if discovery.website_domain and not lead.website_domain:
            lead.website_domain = discovery.website_domain
        if discovery.website_url and not lead.website_url:
            lead.website_url = discovery.website_url
        lead.has_website = bool(lead.website_domain or lead.website_url)
        lead.data_confidence = max(lead.data_confidence, discovery.confidence)
        lead.updated_at = datetime.now(tz=UTC)
        self.evidence_repository.save_lead(db, lead)

    def _merge_lead(
        self,
        lead: Lead,
        *,
        candidate: LeadCandidate,
        search_job_id: int,
        priority: int,
        current_priority: int | None,
        allow_source_promotion: bool,
    ) -> None:
        should_promote = allow_source_promotion and (
            current_priority is None
            or priority < current_priority
            or (priority == current_priority and candidate.completeness >= lead.data_completeness)
        )
        lead.search_job_id = search_job_id
        lead.company_name = candidate.company_name or lead.company_name
        lead.category = self._prefer(candidate.category, lead.category, should_promote)
        lead.address = self._prefer(candidate.address, lead.address, should_promote)
        lead.city = self._prefer(candidate.city, lead.city, should_promote)
        lead.phone = self._prefer(candidate.phone, lead.phone, should_promote)
        lead.website_url = self._prefer(candidate.website_url, lead.website_url, should_promote)
        lead.website_domain = self._prefer(candidate.website_domain, lead.website_domain, should_promote)
        lead.rating = self._prefer(candidate.rating, lead.rating, should_promote)
        lead.review_count = self._prefer_numeric(candidate.review_count, lead.review_count, should_promote)
        lead.lat = self._prefer(candidate.lat, lead.lat, should_promote)
        lead.lng = self._prefer(candidate.lng, lead.lng, should_promote)
        lead.data_completeness = max(lead.data_completeness, candidate.completeness)
        lead.data_confidence = max(lead.data_confidence, candidate.confidence)
        lead.has_website = bool(lead.website_domain or lead.website_url)
        lead.updated_at = datetime.now(tz=UTC)

    def _select_enrichment_targets(self, db: Session, lead_ids: list[int], *, limit: int) -> list[Lead]:
        if not lead_ids or limit <= 0:
            return []
        candidates = self._list_leads(db, lead_ids)
        ranked = sorted(
            candidates,
            key=lambda lead: (
                lead.data_completeness < 0.85,
                not lead.has_website,
                lead.review_count < 10,
                -(lead.data_confidence or 0.0),
            ),
            reverse=True,
        )
        return ranked[:limit]

    def _build_web_query(self, lead: Lead) -> str:
        terms = [lead.company_name]
        if lead.city:
            terms.append(lead.city)
        terms.append("official website")
        return " ".join(terms)

    def _qualifies(self, job: SearchJob, lead: Lead) -> bool:
        if job.min_rating is not None and (lead.rating or 0.0) < job.min_rating:
            return False
        if job.min_reviews is not None and lead.review_count < job.min_reviews:
            return False
        if job.require_website and not lead.has_website:
            return False
        return True

    def _list_leads(self, db: Session, lead_ids: list[int]) -> list[Lead]:
        from sqlalchemy import select

        if not lead_ids:
            return []
        statement = select(Lead).where(Lead.id.in_(lead_ids))
        return list(db.scalars(statement))

    def _mark_running(self, db: Session, job: SearchJob) -> None:
        job.status = SearchJobStatus.RUNNING.value
        job.started_at = datetime.now(tz=UTC)
        job.finished_at = None
        self.search_job_repository.save(db, job)

    def _finalize_status(self, db: Session, job: SearchJob) -> None:
        job.finished_at = datetime.now(tz=UTC)
        if job.provider_error_count > 0 and job.leads_upserted > 0:
            job.status = SearchJobStatus.PARTIALLY_COMPLETED.value
        elif job.leads_upserted > 0:
            job.status = SearchJobStatus.COMPLETED.value
        else:
            job.status = SearchJobStatus.FAILED.value
        self.search_job_repository.save(db, job)

    def _mark_failed(self, db: Session, job: SearchJob, error_message: str) -> None:
        logger.error("Search job '%s' failed: %s", job.public_id, error_message)
        job.finished_at = datetime.now(tz=UTC)
        job.status = SearchJobStatus.FAILED.value
        job.provider_error_count += 1
        self.search_job_repository.save(db, job)

    def _prefer(self, incoming, current, should_promote: bool):
        if incoming is None:
            return current
        if should_promote or current is None:
            return incoming
        return current

    def _prefer_numeric(self, incoming: int | float | None, current: int | float | None, should_promote: bool):
        if incoming is None:
            return current
        if current is None:
            return incoming
        if should_promote:
            return incoming
        return max(current, incoming)
