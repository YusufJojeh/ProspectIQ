from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.leads.models import Lead
from app.modules.provider_apify.demo_service import DemoApifyService
from app.modules.provider_apify.normalizers.apify_normalizer import ApifyCrawlNormalizer
from app.modules.provider_apify.service import ApifyService
from app.modules.provider_serpapi.demo_service import DemoSerpApiService
from app.modules.provider_serpapi.models import ProviderFetch
from app.modules.provider_serpapi.service import SerpApiService
from app.modules.provider_tavily.demo_service import DemoTavilyService
from app.modules.provider_tavily.normalizers.tavily_web_normalizer import TavilyWebNormalizer
from app.modules.provider_tavily.service import TavilyService
from app.modules.research.schemas import ResearchStep
from app.shared.enums.jobs import ProviderFetchStatus

logger = logging.getLogger(__name__)


@dataclass
class StepOutcome:
    step: ResearchStep
    fetch: ProviderFetch
    payload: dict[str, Any]
    normalized_facts: list[dict[str, Any]] = field(default_factory=list)
    discovered_website_url: str | None = None


class ResearchProviderRouter:
    """Executes one planned ResearchStep against the right provider service.

    Live/demo selection reuses each provider's own runtime switch
    (tavily_runtime / discovery_runtime / apify_runtime), so research never
    calls a live provider during tests or explicit demo mode.
    """

    def run_step(
        self,
        db: Session,
        *,
        workspace_id: int,
        search_job_id: int | None,
        lead: Lead,
        query: str,
        step: ResearchStep,
        known_website_url: str | None,
    ) -> StepOutcome:
        if step.provider == "tavily":
            return self._run_tavily(
                db,
                workspace_id=workspace_id,
                search_job_id=search_job_id,
                lead=lead,
                query=query,
                step=step,
            )
        if step.provider == "serpapi":
            return self._run_serpapi(
                db, workspace_id=workspace_id, search_job_id=search_job_id, query=query, step=step
            )
        if step.provider == "apify":
            return self._run_apify(
                db,
                workspace_id=workspace_id,
                search_job_id=search_job_id,
                lead=lead,
                step=step,
                known_website_url=known_website_url,
            )
        raise ValueError(f"Unsupported research provider '{step.provider}'.")

    def _run_tavily(
        self,
        db: Session,
        *,
        workspace_id: int,
        search_job_id: int | None,
        lead: Lead,
        query: str,
        step: ResearchStep,
    ) -> StepOutcome:
        settings = get_settings()
        service = (
            DemoTavilyService() if settings.tavily_runtime in {"demo", "stub"} else TavilyService()
        )
        fetch, payload = service.web_search(
            db, workspace_id=workspace_id, search_job_id=search_job_id, query=query
        )

        normalized_facts: list[dict[str, Any]] = []
        website_url: str | None = None
        if fetch.status == ProviderFetchStatus.OK.value:
            discovered = TavilyWebNormalizer().normalize(payload)
            if discovered.website_url:
                website_url = discovered.website_url
                normalized_facts.append(
                    {
                        "source_type": "tavily_research",
                        "company_name": lead.company_name,
                        "category": lead.category,
                        "website_url": discovered.website_url,
                        "website_domain": discovered.website_domain,
                        "confidence": discovered.confidence,
                        "completeness": lead.data_completeness,
                        "facts": {"provider": "tavily", **discovered.facts},
                    }
                )
        return StepOutcome(
            step=step,
            fetch=fetch,
            payload=payload,
            normalized_facts=normalized_facts,
            discovered_website_url=website_url,
        )

    def _run_serpapi(
        self,
        db: Session,
        *,
        workspace_id: int,
        search_job_id: int | None,
        query: str,
        step: ResearchStep,
    ) -> StepOutcome:
        settings = get_settings()
        service = (
            DemoSerpApiService()
            if settings.discovery_runtime in {"demo", "stub"}
            else SerpApiService()
        )
        fetch, payload = service.web_search(
            db, workspace_id=workspace_id, search_job_id=search_job_id, query=query
        )
        return StepOutcome(step=step, fetch=fetch, payload=payload)

    def _run_apify(
        self,
        db: Session,
        *,
        workspace_id: int,
        search_job_id: int | None,
        lead: Lead,
        step: ResearchStep,
        known_website_url: str | None,
    ) -> StepOutcome:
        settings = get_settings()
        target_url = known_website_url or lead.website_url
        run_input: dict[str, Any] = {"startUrls": [{"url": target_url}]} if target_url else {}
        service = DemoApifyService() if settings.apify_runtime in {"demo", "stub"} else ApifyService()
        fetch, payload = service.crawl(
            db,
            workspace_id=workspace_id,
            search_job_id=search_job_id,
            actor_key=step.mode,
            run_input=run_input,
        )

        normalized_facts: list[dict[str, Any]] = []
        if fetch.status == ProviderFetchStatus.OK.value:
            crawled = ApifyCrawlNormalizer().normalize(
                payload, actor_key=step.mode, fallback_company_name=lead.company_name
            )
            apify_run_id = payload.get("apify_run_id")
            for item in crawled:
                normalized_facts.append(
                    {"source_type": f"apify_{step.mode}", "actor_run_id": apify_run_id, **item}
                )
        return StepOutcome(step=step, fetch=fetch, payload=payload, normalized_facts=normalized_facts)
