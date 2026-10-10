from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.modules.leads.models import Lead
from app.modules.provider_serpapi.models import ProviderFetch, ProviderNormalizedFact
from app.modules.provider_serpapi.repository import ProviderEvidenceRepository
from app.modules.research.contradiction import ContradictionDetector
from app.modules.research.planner import ResearchPlanner
from app.modules.research.repository import ResearchRepository
from app.modules.research.router import ResearchProviderRouter
from app.modules.research.schemas import ResearchDepth, ResearchRunResult
from app.shared.enums.jobs import ProviderFetchStatus

logger = logging.getLogger(__name__)


class ResearchOrchestrator:
    """Ties ResearchPlanner, ResearchProviderRouter, and ContradictionDetector
    together for a single lead research request.

    Steps run in the order the planner returns them, and later steps see the
    website URL discovered by an earlier one (e.g. Tavily finds the official
    site, then the Apify company-website crawl targets it). A
    company_website_crawler step is skipped -- not run as a failed fetch --
    when no website URL is known by the time it is reached, since crawling
    nothing is a planning no-op, not a provider failure.
    """

    def __init__(self) -> None:
        self.planner = ResearchPlanner()
        self.router = ResearchProviderRouter()
        self.contradiction_detector = ContradictionDetector()
        self.evidence_repository = ProviderEvidenceRepository()
        self.research_repository = ResearchRepository()

    def run(
        self, db: Session, *, workspace_id: int, lead: Lead, depth: ResearchDepth
    ) -> ResearchRunResult:
        settings = get_settings()
        available_providers = self._available_providers(settings)
        place_lookup = self.evidence_repository.get_best_place_lookup(db, lead.id)

        plan = self.planner.plan(
            depth=depth,
            has_place_identity=place_lookup is not None,
            available_providers=available_providers,
        )

        if not plan.steps:
            return ResearchRunResult(
                depth=depth,
                status=ProviderFetchStatus.ERROR.value,
                message="No research providers are configured for this depth.",
            )

        query = self._build_query(lead)
        providers_used: list[str] = []
        facts_created: list[ProviderNormalizedFact] = []
        fetches_by_id: dict[int, ProviderFetch] = {}
        known_website_url = lead.website_url
        last_fetch_public_id: str | None = None
        any_step_ok = False

        for step in plan.steps:
            if (
                step.provider == "apify"
                and step.mode == "company_website_crawler"
                and not known_website_url
            ):
                logger.info(
                    "research.step.skipped reason=no_known_website lead_id=%s depth=%s",
                    lead.id,
                    depth,
                )
                continue

            outcome = self.router.run_step(
                db,
                workspace_id=workspace_id,
                search_job_id=lead.search_job_id,
                lead=lead,
                query=query,
                step=step,
                known_website_url=known_website_url,
            )
            providers_used.append(outcome.step.provider)
            fetches_by_id[outcome.fetch.id] = outcome.fetch
            last_fetch_public_id = outcome.fetch.public_id
            if outcome.discovered_website_url:
                known_website_url = outcome.discovered_website_url

            if outcome.fetch.status == ProviderFetchStatus.OK.value:
                any_step_ok = True
                for fact_data in outcome.normalized_facts:
                    facts_created.append(
                        self._persist_fact(
                            db,
                            workspace_id=workspace_id,
                            lead=lead,
                            provider_fetch_id=outcome.fetch.id,
                            data=fact_data,
                        )
                    )

        contradictions = self.contradiction_detector.detect(facts_created, fetches_by_id)
        self.research_repository.save_contradictions(
            db, workspace_id=workspace_id, lead_id=lead.id, contradictions=contradictions
        )

        status = ProviderFetchStatus.OK.value if any_step_ok else ProviderFetchStatus.ERROR.value
        message = (
            f"Research completed at depth={depth} using {len(providers_used)} provider step(s)."
            if any_step_ok
            else "Research steps ran but no provider call succeeded."
        )
        return ResearchRunResult(
            depth=depth,
            providers_used=providers_used,
            steps_executed=len(providers_used),
            facts_created=len(facts_created),
            contradictions=contradictions,
            status=status,
            message=message,
            last_provider_fetch_public_id=last_fetch_public_id,
        )

    def _available_providers(self, settings: Settings) -> set[str]:
        available: set[str] = set()
        if settings.discovery_runtime != "blocked":
            available.add("serpapi")
        if settings.tavily_runtime != "blocked":
            available.add("tavily")
        if settings.apify_runtime != "blocked":
            available.add("apify")
        return available

    def _persist_fact(
        self,
        db: Session,
        *,
        workspace_id: int,
        lead: Lead,
        provider_fetch_id: int,
        data: dict[str, Any],
    ) -> ProviderNormalizedFact:
        fact = ProviderNormalizedFact(
            workspace_id=workspace_id,
            lead_id=lead.id,
            provider_fetch_id=provider_fetch_id,
            source_type=data.get("source_type", "research"),
            company_name=data.get("company_name") or lead.company_name,
            category=data.get("category"),
            address=data.get("address"),
            city=data.get("city") or lead.city,
            phone=data.get("phone"),
            website_url=data.get("website_url"),
            website_domain=data.get("website_domain"),
            rating=data.get("rating"),
            review_count=data.get("review_count", 0),
            confidence=data.get("confidence", 0.5),
            completeness=data.get("completeness", lead.data_completeness),
            facts_json=data.get("facts", {}),
            actor_run_id=data.get("actor_run_id"),
            freshness_score=1.0,
        )
        db.add(fact)
        db.commit()
        db.refresh(fact)
        return fact

    def _build_query(self, lead: Lead) -> str:
        parts = [lead.company_name]
        if lead.city:
            parts.append(lead.city)
        if lead.category:
            parts.append(lead.category)
        parts.append("company services customers")
        return " ".join(parts)[:220]
