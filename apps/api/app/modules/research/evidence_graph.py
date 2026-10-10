from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.provider_serpapi.models import ProviderFetch, ProviderNormalizedFact
from app.modules.research.business_intelligence import (
    BUSINESS_CLAIM_GROUPS,
    BusinessIntelligenceProjector,
    ClaimObservation,
    canonical_json,
)
from app.modules.signals.models import LeadSignal

# Source-quality weights, by provider fact "shape". A crawl of the lead's own
# official website is the most trustworthy source available; a generic
# directory listing is the least. These are fixed, deterministic weights --
# never LLM-generated -- so evidence confidence stays auditable.
_SOURCE_QUALITY_BY_SOURCE_TYPE: dict[str, float] = {
    "apify_company_website_crawler": 1.00,
    "maps_place": 0.95,
    "maps_search": 0.90,
    "apify_reviews_crawler": 0.80,
    "apify_business_directory_crawler": 0.70,
    "apify_social_public_profile_crawler": 0.65,
    "tavily_research": 0.60,
    "tavily_search": 0.55,
    "web_search": 0.55,
    "openai_web_search": 0.45,
}
_DEFAULT_SOURCE_QUALITY = 0.35

# Claim types this module resolves from ProviderNormalizedFact columns, and
# the group each belongs to for the "Evidence Graph" report the user reads.
_CLAIM_GROUPS: dict[str, str] = {
    "company_name": "business_identity",
    "category": "business_identity",
    "address": "business_identity",
    "website_url": "digital_presence",
    "website_domain": "digital_presence",
    "phone": "contactability",
    "rating": "reviews",
    "review_count": "reviews",
    **BUSINESS_CLAIM_GROUPS,
}
# Denominator for research_coverage: how many of these claim types have at
# least one supporting source.
_EXPECTED_CLAIM_TYPES = tuple(_CLAIM_GROUPS.keys())
_BASE_CLAIM_TYPES = tuple(
    claim_type for claim_type in _CLAIM_GROUPS if claim_type not in BUSINESS_CLAIM_GROUPS
)
_MERGED_LIST_CLAIMS = {"services", "contact_channels"}

# Real signal_type values from app.modules.signals.service.SIGNAL_TYPES,
# bucketed into the pain/opportunity/growth groups from the product roadmap.
_PAIN_SIGNAL_TYPES = {"no_website", "weak_website", "low_rating", "missing_phone", "poor_data_completeness"}
_OPPORTUNITY_SIGNAL_TYPES = {"high_local_visibility", "competitor_gap", "ready_for_outreach"}
_GROWTH_SIGNAL_TYPES = {"high_reviews"}


def source_quality(source_type: str) -> float:
    """Static, auditable weight for how much a source type should be trusted."""
    return _SOURCE_QUALITY_BY_SOURCE_TYPE.get(source_type, _DEFAULT_SOURCE_QUALITY)


def evidence_ref_for_fact(fact_id: int) -> str:
    return f"ev_{fact_id}"


class EvidenceSource(BaseModel):
    #: Citable id of the persisted observation ("ev_<fact id>"). The only
    #: form of lead evidence a final answer may reference.
    evidence_ref: str | None = None
    provider: str
    source_type: str
    url: str | None = None
    observed_at: datetime
    actor_run_id: str | None = None
    confidence: float
    source_quality: float


class ContradictingValue(BaseModel):
    value: str
    providers: list[str]
    sources: list[EvidenceSource] = Field(default_factory=list)


class CanonicalFact(BaseModel):
    claim_type: str
    value: str
    status: Literal["supported", "conflicting", "unknown"]
    confidence: float
    freshness_score: float
    source_quality: float
    sources: list[EvidenceSource] = Field(default_factory=list)
    contradicting_values: list[ContradictingValue] = Field(default_factory=list)


class EvidenceGroup(BaseModel):
    group: str
    facts: list[CanonicalFact] = Field(default_factory=list)


class EvidenceGraph(BaseModel):
    lead_id: str
    groups: list[EvidenceGroup] = Field(default_factory=list)
    evidence_confidence: float
    research_coverage: float
    generated_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))


class FactResolver:
    """Resolves one claim type's disagreeing provider facts into a single
    canonical value with a deterministic, auditable confidence score.

    confidence = source_quality x freshness x cross_source_agreement x
    evidence_completeness -- never LLM-generated, so "why does this lead show
    91 confidence" always has a traceable answer.
    """

    def resolve(
        self,
        claim_type: str,
        facts: list[ProviderNormalizedFact],
        fetches_by_id: dict[int, ProviderFetch],
    ) -> CanonicalFact | None:
        observations: list[ClaimObservation] = []
        for fact in facts:
            value = getattr(fact, claim_type, None)
            if value is None or (isinstance(value, str) and not value.strip()):
                continue
            observations.append(ClaimObservation(fact=fact, value=str(value)))
        return self.resolve_observations(claim_type, observations, fetches_by_id)

    def resolve_observations(
        self,
        claim_type: str,
        observations: list[ClaimObservation],
        fetches_by_id: dict[int, ProviderFetch],
    ) -> CanonicalFact | None:
        if claim_type in _MERGED_LIST_CLAIMS:
            return self._resolve_merged_list(claim_type, observations, fetches_by_id)
        groups: dict[str, list[ClaimObservation]] = defaultdict(list)
        for observation in observations:
            groups[observation.value.strip().casefold()].append(observation)
        if not groups:
            return None

        def _group_weight(members: list[ClaimObservation]) -> float:
            return sum(
                source_quality(member.fact.source_type) * member.fact.confidence for member in members
            )

        canonical_key = max(groups, key=lambda key: _group_weight(groups[key]))
        canonical_members = groups[canonical_key]
        all_providers = {
            self._provider_for(item.fact, fetches_by_id)
            for members in groups.values()
            for item in members
        }
        canonical_providers = {
            self._provider_for(item.fact, fetches_by_id) for item in canonical_members
        }

        best_quality = max(source_quality(item.fact.source_type) for item in canonical_members)
        freshness_values = [
            item.fact.freshness_score if item.fact.freshness_score is not None else 1.0
            for item in canonical_members
        ]
        avg_freshness = sum(freshness_values) / len(freshness_values)
        cross_source_agreement = (
            1.0 if len(all_providers) <= 1 else len(canonical_providers) / len(all_providers)
        )
        completeness_factor = 1.0 if len(canonical_members) > 1 else 0.75
        confidence = round(
            max(0.0, min(1.0, best_quality * avg_freshness * cross_source_agreement * completeness_factor)),
            4,
        )

        contradicting = [
            ContradictingValue(
                value=members[0].value,
                providers=sorted(
                    {self._provider_for(item.fact, fetches_by_id) for item in members}
                ),
                sources=[self._source(item.fact, fetches_by_id) for item in members],
            )
            for key, members in groups.items()
            if key != canonical_key
        ]

        return CanonicalFact(
            claim_type=claim_type,
            value=canonical_members[0].value,
            status="conflicting" if contradicting else "supported",
            confidence=confidence,
            freshness_score=round(avg_freshness, 4),
            source_quality=best_quality,
            sources=[
                self._source(item.fact, fetches_by_id) for item in canonical_members
            ],
            contradicting_values=contradicting,
        )

    def _provider_for(self, fact: ProviderNormalizedFact, fetches_by_id: dict[int, ProviderFetch]) -> str:
        fetch = fetches_by_id.get(fact.provider_fetch_id)
        return fetch.provider if fetch else "unknown"

    def _source(
        self, fact: ProviderNormalizedFact, fetches_by_id: dict[int, ProviderFetch]
    ) -> EvidenceSource:
        evidence = (fact.facts_json or {}).get("evidence")
        evidence_url = evidence.get("url") if isinstance(evidence, dict) else None
        return EvidenceSource(
            evidence_ref=evidence_ref_for_fact(fact.id),
            provider=self._provider_for(fact, fetches_by_id),
            source_type=fact.source_type,
            url=evidence_url if isinstance(evidence_url, str) else fact.website_url,
            observed_at=fact.created_at,
            actor_run_id=fact.actor_run_id,
            confidence=fact.confidence,
            source_quality=source_quality(fact.source_type),
        )

    def _resolve_merged_list(
        self,
        claim_type: str,
        observations: list[ClaimObservation],
        fetches_by_id: dict[int, ProviderFetch],
    ) -> CanonicalFact | None:
        merged: dict[str, str] = {}
        valid: list[ClaimObservation] = []
        for observation in observations:
            try:
                values = json.loads(observation.value)
            except (TypeError, ValueError):
                continue
            if not isinstance(values, list):
                continue
            valid.append(observation)
            for value in values:
                if isinstance(value, str) and value.strip():
                    merged.setdefault(value.strip().casefold(), value.strip())
        if not valid or not merged:
            return None
        freshness = sum(
            item.fact.freshness_score if item.fact.freshness_score is not None else 1.0
            for item in valid
        ) / len(valid)
        quality = max(source_quality(item.fact.source_type) for item in valid)
        confidence = round(
            min(1.0, quality * freshness * (1.0 if len(valid) > 1 else 0.75)), 4
        )
        return CanonicalFact(
            claim_type=claim_type,
            value=canonical_json(sorted(merged.values(), key=str.casefold)),
            status="supported",
            confidence=confidence,
            freshness_score=round(freshness, 4),
            source_quality=quality,
            sources=[self._source(item.fact, fetches_by_id) for item in valid],
        )


class EvidenceGraphBuilder:
    """Builds the canonical, groupable Evidence Graph for a lead from its
    ProviderNormalizedFact rows and LeadSignal rows -- the read model behind
    `GET /leads/{lead_id}/evidence-graph` and the research agent's
    `get_existing_evidence`/`compare_evidence` tools.
    """

    def __init__(
        self,
        resolver: FactResolver | None = None,
        projector: BusinessIntelligenceProjector | None = None,
    ) -> None:
        self._resolver = resolver or FactResolver()
        self._projector = projector or BusinessIntelligenceProjector()

    def build(
        self,
        *,
        lead_public_id: str,
        facts: list[ProviderNormalizedFact],
        fetches_by_id: dict[int, ProviderFetch],
        signals: list[LeadSignal],
    ) -> EvidenceGraph:
        resolved: dict[str, CanonicalFact] = {}
        for claim_type in _BASE_CLAIM_TYPES:
            canonical = self._resolver.resolve(claim_type, facts, fetches_by_id)
            if canonical is not None:
                resolved[claim_type] = canonical
        projected = self._projector.project(facts)
        for claim_type, observations in projected.items():
            canonical = self._resolver.resolve_observations(
                claim_type, observations, fetches_by_id
            )
            if canonical is not None:
                resolved[claim_type] = canonical
        maturity = self._digital_maturity(resolved, facts)
        if maturity is not None:
            resolved["digital_maturity"] = maturity
        if facts:
            for claim_type in BUSINESS_CLAIM_GROUPS:
                resolved.setdefault(
                    claim_type,
                    CanonicalFact(
                        claim_type=claim_type,
                        value="unknown",
                        status="unknown",
                        confidence=0.0,
                        freshness_score=0.0,
                        source_quality=0.0,
                    ),
                )

        groups_by_name: dict[str, list[CanonicalFact]] = defaultdict(list)
        for claim_type, canonical in resolved.items():
            groups_by_name[_CLAIM_GROUPS[claim_type]].append(canonical)

        for signal in signals:
            groups_by_name[self._signal_group(signal.signal_type)].append(
                CanonicalFact(
                    claim_type=signal.signal_type,
                    value=signal.evidence_text,
                    status="supported",
                    confidence=round(max(0.0, min(1.0, signal.signal_strength)), 4),
                    freshness_score=1.0,
                    source_quality=0.5,
                    sources=[
                        EvidenceSource(
                            provider="signals",
                            source_type=signal.signal_type,
                            url=signal.source_url,
                            observed_at=signal.detected_at,
                            confidence=signal.signal_strength,
                            source_quality=0.5,
                        )
                    ],
                )
            )

        groups = [
            EvidenceGroup(group=name, facts=facts_in_group)
            for name, facts_in_group in groups_by_name.items()
        ]
        supported_facts = [fact for fact in resolved.values() if fact.status != "unknown"]
        evidence_confidence = (
            round(sum(fact.confidence for fact in supported_facts) / len(supported_facts), 4)
            if supported_facts
            else 0.0
        )
        research_coverage = round(len(supported_facts) / len(_EXPECTED_CLAIM_TYPES), 4)

        return EvidenceGraph(
            lead_id=lead_public_id,
            groups=groups,
            evidence_confidence=evidence_confidence,
            research_coverage=research_coverage,
        )

    def _digital_maturity(
        self,
        resolved: dict[str, CanonicalFact],
        provider_facts: list[ProviderNormalizedFact],
    ) -> CanonicalFact | None:
        if not resolved:
            return None

        def _true(claim_type: str) -> bool:
            fact = resolved.get(claim_type)
            return fact is not None and fact.value == "true"

        social_count = 0
        contact_count = 0
        services_count = 0
        try:
            social = json.loads(resolved["social_presence"].value) if "social_presence" in resolved else {}
            social_count = sum(value is True for value in social.values()) if isinstance(social, dict) else 0
            contacts = json.loads(resolved["contact_channels"].value) if "contact_channels" in resolved else []
            contact_count = len(contacts) if isinstance(contacts, list) else 0
            services = json.loads(resolved["services"].value) if "services" in resolved else []
            services_count = len(services) if isinstance(services, list) else 0
        except (TypeError, ValueError):
            pass

        components = {
            "official_website": 20 if "website_url" in resolved else 0,
            "mobile_responsive": 10
            if any((fact.facts_json or {}).get("mobile_responsive") is True for fact in provider_facts)
            else 0,
            "online_booking": 15 if _true("online_booking") else 0,
            "ecommerce": 15 if _true("has_ecommerce") else 0,
            "whatsapp": 10 if _true("has_whatsapp") else 0,
            "social_presence": min(15, social_count * 5),
            "contact_channels": min(15, contact_count * 3),
            "review_volume": 5 if self._number(resolved.get("review_count")) >= 20 else 0,
            "structured_services": 5 if services_count > 0 else 0,
        }
        score = min(100, sum(components.values()))
        band = "high" if score >= 70 else "medium" if score >= 40 else "low"
        component_facts = [
            resolved[key]
            for key in ("website_url", "online_booking", "has_ecommerce", "has_whatsapp", "social_presence", "contact_channels", "review_count", "services")
            if key in resolved
        ]
        has_mobile_signal = any(
            (fact.facts_json or {}).get("mobile_responsive") is True for fact in provider_facts
        )
        if not component_facts and not has_mobile_signal:
            return None
        sources = [source for fact in component_facts for source in fact.sources]
        return CanonicalFact(
            claim_type="digital_maturity",
            value=canonical_json({"band": band, "components": components, "score": score}),
            status="conflicting" if any(fact.status == "conflicting" for fact in component_facts) else "supported",
            confidence=round(sum(fact.confidence for fact in component_facts) / len(component_facts), 4) if component_facts else 0.0,
            freshness_score=round(sum(fact.freshness_score for fact in component_facts) / len(component_facts), 4) if component_facts else 0.0,
            source_quality=max((fact.source_quality for fact in component_facts), default=0.0),
            sources=sources,
            contradicting_values=[],
        )

    def _number(self, fact: CanonicalFact | None) -> float:
        try:
            return float(fact.value) if fact is not None else 0.0
        except ValueError:
            return 0.0

    def _signal_group(self, signal_type: str) -> str:
        if signal_type in _PAIN_SIGNAL_TYPES:
            return "pain_signals"
        if signal_type in _OPPORTUNITY_SIGNAL_TYPES:
            return "opportunity_signals"
        if signal_type in _GROWTH_SIGNAL_TYPES:
            return "growth_signals"
        return "growth_signals"
