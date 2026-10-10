from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.modules.icp.repository import IcpProfileRepository
from app.modules.leads.models import Lead
from app.modules.provider_serpapi.normalizers.shared import compute_domain
from app.modules.provider_serpapi.repository import ProviderEvidenceRepository
from app.modules.research.evidence_graph import EvidenceGraphBuilder, evidence_ref_for_fact
from app.modules.research.router import ResearchProviderRouter
from app.modules.research.schemas import ResearchStep
from app.modules.scoring.repository import ScoringRepository
from app.modules.signals.repository import LeadSignalRepository
from app.shared.enums.jobs import ProviderFetchStatus

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]

    def as_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


_NO_PARAMS: dict[str, Any] = {"type": "object", "properties": {}, "additionalProperties": False}

# Every tool the research agent can call. crawl_company_site/crawl_reviews take
# NO url or actor-id parameter -- the LLM only ever picks a tool *name*; the
# actual crawl target is always resolved server-side from evidence already
# discovered for this lead (ResearchToolExecutor._known_website_url), and the
# Apify Actor ID stays behind the existing allowlist (app.modules.provider_apify
# .allowlist). This is a structural guarantee, not a prompt instruction: there
# is no schema field the model could use to smuggle in an arbitrary URL or
# Actor ID even if it tried.
TOOL_DEFINITIONS: list[ToolSpec] = [
    ToolSpec(
        name="search_web_tavily",
        description=(
            "Fast, broad web search for the lead's business (name, city, category). "
            "Good first step to discover the official website and general presence."
        ),
        parameters=_NO_PARAMS,
    ),
    ToolSpec(
        name="search_google_serpapi",
        description=(
            "Google-oriented search as redundancy/cross-check against Tavily results. "
            "Use when Tavily's result is thin or you need a second source for agreement."
        ),
        parameters=_NO_PARAMS,
    ),
    ToolSpec(
        name="crawl_company_site",
        description=(
            "Deep-crawl the lead's own official website (already-discovered domain) for "
            "services, contact details, and booking/online-presence facts. Takes no URL "
            "parameter -- it always targets the site already found for this lead."
        ),
        parameters=_NO_PARAMS,
    ),
    ToolSpec(
        name="crawl_reviews",
        description=(
            "Deep-crawl review sources for this lead (requires a known Google Place "
            "identity). Takes no URL parameter -- the target is resolved server-side."
        ),
        parameters=_NO_PARAMS,
    ),
    ToolSpec(
        name="get_existing_evidence",
        description="List every normalized fact already stored for this lead, across all providers.",
        parameters=_NO_PARAMS,
    ),
    ToolSpec(
        name="get_previous_research",
        description="List deduplicated evidence items from prior research runs for this lead.",
        parameters=_NO_PARAMS,
    ),
    ToolSpec(
        name="get_lead_score_breakdown",
        description="Get the lead's latest fit/need/urgency/reachability score breakdown, if scored.",
        parameters=_NO_PARAMS,
    ),
    ToolSpec(
        name="get_icp_profile",
        description="Get the workspace's active Ideal Customer Profile definitions.",
        parameters=_NO_PARAMS,
    ),
    ToolSpec(
        name="resolve_company_domain",
        description=(
            "Extract the bare domain from a URL string already present in gathered evidence "
            "(pure string parsing, no network request is made)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "A URL already seen in tool results, e.g. from search results.",
                }
            },
            "required": ["url"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="compare_evidence",
        description=(
            "Resolve all gathered facts into the canonical Evidence Graph, surfacing any "
            "contradictions between providers and the current evidence_confidence/"
            "research_coverage scores. Call this before deciding whether enough evidence exists."
        ),
        parameters=_NO_PARAMS,
    ),
]


class ResearchToolExecutor:
    """Executes one named tool call for the bounded Research Agent Loop.

    Holds per-run state (the lead, and the best known website URL, which
    updates as search/crawl tools discover one) so crawl tools never need a
    URL parameter from the LLM. Every method returns a JSON-serializable dict;
    exceptions are caught and returned as {"error": ...} so a single failed
    tool call cannot crash the agent loop.
    """

    def __init__(
        self,
        db: Session,
        *,
        workspace_id: int,
        lead: Lead,
        router: ResearchProviderRouter | None = None,
        evidence_repository: ProviderEvidenceRepository | None = None,
        scoring_repository: ScoringRepository | None = None,
        icp_repository: IcpProfileRepository | None = None,
        signal_repository: LeadSignalRepository | None = None,
        evidence_graph_builder: EvidenceGraphBuilder | None = None,
    ) -> None:
        self.db = db
        self.workspace_id = workspace_id
        self.lead = lead
        self.router = router or ResearchProviderRouter()
        self.evidence_repository = evidence_repository or ProviderEvidenceRepository()
        self.scoring_repository = scoring_repository or ScoringRepository()
        self.icp_repository = icp_repository or IcpProfileRepository()
        self.signal_repository = signal_repository or LeadSignalRepository()
        self.evidence_graph_builder = evidence_graph_builder or EvidenceGraphBuilder()

        self.known_website_url: str | None = lead.website_url
        self.searches_performed = 0
        self.crawls_performed = 0
        self.sources_gathered = 0
        self.facts_created: list[Any] = []
        self.fetches_by_id: dict[int, Any] = {}

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        handler = self._handlers().get(name)
        if handler is None:
            return {"error": f"Unknown tool '{name}'."}
        try:
            return handler(arguments)
        except Exception as exc:  # noqa: BLE001
            logger.warning("research.tool.failed name=%s error=%s", name, exc)
            return {"error": str(exc)}

    def _handlers(self) -> dict[str, Callable[[dict[str, Any]], dict[str, Any]]]:
        return {
            "search_web_tavily": self._search_web_tavily,
            "search_google_serpapi": self._search_google_serpapi,
            "crawl_company_site": self._crawl_company_site,
            "crawl_reviews": self._crawl_reviews,
            "get_existing_evidence": self._get_existing_evidence,
            "get_previous_research": self._get_previous_research,
            "get_lead_score_breakdown": self._get_lead_score_breakdown,
            "get_icp_profile": self._get_icp_profile,
            "resolve_company_domain": self._resolve_company_domain,
            "compare_evidence": self._compare_evidence,
        }

    def _query(self) -> str:
        parts = [self.lead.company_name]
        if self.lead.city:
            parts.append(self.lead.city)
        if self.lead.category:
            parts.append(self.lead.category)
        parts.append("company services customers")
        return " ".join(parts)[:220]

    def _run_step(self, step: ResearchStep) -> dict[str, Any]:
        outcome = self.router.run_step(
            self.db,
            workspace_id=self.workspace_id,
            search_job_id=self.lead.search_job_id,
            lead=self.lead,
            query=self._query(),
            step=step,
            known_website_url=self.known_website_url,
        )
        self.fetches_by_id[outcome.fetch.id] = outcome.fetch
        if outcome.discovered_website_url:
            self.known_website_url = outcome.discovered_website_url

        if outcome.fetch.status != ProviderFetchStatus.OK.value:
            return {
                "ok": False,
                "provider": step.provider,
                "mode": step.mode,
                "error": outcome.fetch.error_message or "Provider call failed.",
            }

        persisted = [self._persist_fact(outcome.fetch.id, data) for data in outcome.normalized_facts]
        self.facts_created.extend(persisted)
        self.sources_gathered += len(persisted)
        return {
            "ok": True,
            "provider": step.provider,
            "mode": step.mode,
            "facts_found": len(persisted),
            "discovered_website_url": outcome.discovered_website_url,
            "facts": [self._fact_to_dict(fact) for fact in persisted],
        }

    def _persist_fact(self, provider_fetch_id: int, data: dict[str, Any]) -> Any:
        from app.modules.provider_serpapi.models import ProviderNormalizedFact

        fact = ProviderNormalizedFact(
            workspace_id=self.workspace_id,
            lead_id=self.lead.id,
            provider_fetch_id=provider_fetch_id,
            source_type=data.get("source_type", "research"),
            company_name=data.get("company_name") or self.lead.company_name,
            category=data.get("category"),
            address=data.get("address"),
            city=data.get("city") or self.lead.city,
            phone=data.get("phone"),
            website_url=data.get("website_url"),
            website_domain=data.get("website_domain"),
            rating=data.get("rating"),
            review_count=data.get("review_count", 0),
            confidence=data.get("confidence", 0.5),
            completeness=data.get("completeness", self.lead.data_completeness),
            facts_json=data.get("facts", {}),
            actor_run_id=data.get("actor_run_id"),
            freshness_score=1.0,
        )
        self.db.add(fact)
        self.db.commit()
        self.db.refresh(fact)
        return fact

    def _fact_to_dict(self, fact: Any) -> dict[str, Any]:
        return {
            "evidence_ref": evidence_ref_for_fact(fact.id),
            "source_type": fact.source_type,
            "company_name": fact.company_name,
            "phone": fact.phone,
            "website_url": fact.website_url,
            "website_domain": fact.website_domain,
            "rating": fact.rating,
            "review_count": fact.review_count,
            "confidence": fact.confidence,
        }

    def _search_web_tavily(self, _arguments: dict[str, Any]) -> dict[str, Any]:
        self.searches_performed += 1
        return self._run_step(ResearchStep(provider="tavily", mode="web_search", reason="agent"))

    def _search_google_serpapi(self, _arguments: dict[str, Any]) -> dict[str, Any]:
        self.searches_performed += 1
        return self._run_step(ResearchStep(provider="serpapi", mode="web_search", reason="agent"))

    def _crawl_company_site(self, _arguments: dict[str, Any]) -> dict[str, Any]:
        if not self.known_website_url:
            return {
                "ok": False,
                "error": "No website is known for this lead yet. Search first to discover one.",
            }
        self.crawls_performed += 1
        return self._run_step(
            ResearchStep(provider="apify", mode="company_website_crawler", reason="agent")
        )

    def _crawl_reviews(self, _arguments: dict[str, Any]) -> dict[str, Any]:
        place_lookup = self.evidence_repository.get_best_place_lookup(self.db, self.lead.id)
        if place_lookup is None:
            return {
                "ok": False,
                "error": "No Google Place identity is known for this lead yet.",
            }
        self.crawls_performed += 1
        return self._run_step(ResearchStep(provider="apify", mode="reviews_crawler", reason="agent"))

    def _get_existing_evidence(self, _arguments: dict[str, Any]) -> dict[str, Any]:
        facts = self.evidence_repository.list_normalized_facts_for_lead(self.db, self.lead.id)
        return {"facts": [self._fact_to_dict(fact) for fact in facts], "count": len(facts)}

    def _get_previous_research(self, _arguments: dict[str, Any]) -> dict[str, Any]:
        items = self.scoring_repository.list_evidence_items(self.db, self.lead.id)
        return {
            "items": [
                {
                    "source_type": item.source_type,
                    "company_name": item.company_name,
                    "phone": item.phone,
                    "website_url": item.website_url,
                    "confidence": item.confidence,
                    "created_at": item.created_at.isoformat(),
                }
                for item in items
            ],
            "count": len(items),
        }

    def _get_lead_score_breakdown(self, _arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            breakdown = self.scoring_repository.get_latest_score_breakdown(self.db, self.lead.id)
        except NotFoundError:
            return {"error": "Lead has not been scored yet."}
        return breakdown.model_dump(mode="json")

    def _get_icp_profile(self, _arguments: dict[str, Any]) -> dict[str, Any]:
        profiles = self.icp_repository.list_for_workspace(
            self.db, workspace_id=self.workspace_id, active_only=True
        )
        return {
            "profiles": [
                {
                    "name": profile.name,
                    "target_industries": profile.target_industries,
                    "target_cities": profile.target_cities,
                    "min_rating": profile.min_rating,
                    "min_reviews": profile.min_reviews,
                    "website_preference": profile.website_preference,
                    "required_signals": profile.required_signals,
                }
                for profile in profiles
            ]
        }

    def _load_fetches_for(self, facts: list[Any]) -> dict[int, Any]:
        from app.modules.provider_serpapi.models import ProviderFetch

        fetch_ids = {fact.provider_fetch_id for fact in facts}
        missing = fetch_ids - set(self.fetches_by_id)
        fetches_by_id = dict(self.fetches_by_id)
        if missing:
            for fetch in self.db.query(ProviderFetch).filter(ProviderFetch.id.in_(missing)):
                fetches_by_id[fetch.id] = fetch
        return fetches_by_id

    def _resolve_company_domain(self, arguments: dict[str, Any]) -> dict[str, Any]:
        url = arguments.get("url")
        if not isinstance(url, str) or not url:
            return {"error": "A non-empty 'url' string is required."}
        return {"domain": compute_domain(url)}

    def _compare_evidence(self, _arguments: dict[str, Any]) -> dict[str, Any]:
        facts = self.evidence_repository.list_normalized_facts_for_lead(self.db, self.lead.id)
        fetches_by_id = self._load_fetches_for(facts)
        signals = self.signal_repository.list_for_lead(
            self.db, workspace_id=self.workspace_id, lead_id=self.lead.id
        )
        graph = self.evidence_graph_builder.build(
            lead_public_id=self.lead.public_id,
            facts=facts,
            fetches_by_id=fetches_by_id,
            signals=signals,
        )
        return graph.model_dump(mode="json")
