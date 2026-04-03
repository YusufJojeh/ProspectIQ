from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from typing import Any
from urllib.parse import urlparse

from app.modules.leads.models import Lead
from app.modules.provider_serpapi.models import ProviderNormalizedFact
from app.shared.dto.lead_facts import NormalizedLeadFacts

_STOPWORDS = {
    "and",
    "co",
    "company",
    "clinic",
    "dental",
    "group",
    "inc",
    "ltd",
    "llc",
    "marketing",
    "services",
    "solutions",
    "studio",
    "the",
}


class EvidenceFactBuilder:
    def build(self, lead: Lead, facts: Iterable[ProviderNormalizedFact]) -> NormalizedLeadFacts:
        fact_list = list(facts)
        by_source = self._group_by_source(fact_list)
        latest_web = by_source.get("web_search", [None])[0]

        phone_present = bool(lead.phone or any(item.phone for item in fact_list))
        address_present = bool(lead.address or any(item.address for item in fact_list))
        hours_present = any(
            self._has_hours(item.facts_json) for item in by_source.get("maps_place", [])
        )
        category_clarity = self._category_clarity(lead, fact_list)
        official_website_source, official_website_domain = self._official_website(by_source, lead)
        website_domain = lead.website_domain or official_website_domain
        official_site_position = self._official_site_position(latest_web)
        directory_results_before_official = self._directory_results_before_official(latest_web)
        knowledge_graph_present = self._knowledge_graph_present(latest_web)
        official_site_discoverability = self._official_site_discoverability(
            latest_web,
            official_site_position=official_site_position,
            official_website_source=official_website_source,
            official_website_found=bool(website_domain),
            knowledge_graph_present=knowledge_graph_present,
        )
        website_domain_matches_brand = self._domain_matches_brand(
            website_domain=website_domain,
            company_name=lead.company_name,
        )
        source_agreement = self._source_agreement(lead, fact_list)
        local_presence_signal = self._local_presence_signal(
            maps_search_present=bool(by_source.get("maps_search")),
            maps_place_present=bool(by_source.get("maps_place")),
            review_count=lead.review_count,
            knowledge_graph_present=knowledge_graph_present,
        )
        weak_website_signal = self._weak_website_signal(
            official_website_found=bool(website_domain),
            website_domain_matches_brand=website_domain_matches_brand,
            official_site_discoverability=official_site_discoverability,
            official_website_source=official_website_source,
        )
        digital_footprint_gap = self._digital_footprint_gap(
            lead=lead,
            phone_present=phone_present,
            address_present=address_present,
            hours_present=hours_present,
            official_site_discoverability=official_site_discoverability,
            weak_website_signal=weak_website_signal,
        )
        directory_dominance = self._directory_dominance(
            official_website_found=bool(website_domain),
            official_site_position=official_site_position,
            directory_results_before_official=directory_results_before_official,
            web_search_present=bool(by_source.get("web_search")),
        )
        website_values = {
            value.casefold()
            for value in [lead.website_domain, *(item.website_domain for item in fact_list)]
            if value
        }

        return NormalizedLeadFacts(
            company_name=lead.company_name,
            category=lead.category,
            address=lead.address,
            city=lead.city,
            phone=lead.phone,
            website_url=lead.website_url,
            website_domain=website_domain,
            review_count=lead.review_count,
            rating=lead.rating,
            lat=lead.lat,
            lng=lead.lng,
            data_completeness=lead.data_completeness,
            data_confidence=lead.data_confidence,
            has_website=bool(lead.has_website or website_domain),
            visibility_confidence=official_site_discoverability,
            visibility_source=official_website_source,
            phone_present=phone_present,
            address_present=address_present,
            hours_present=hours_present,
            maps_search_present=bool(by_source.get("maps_search")),
            maps_place_present=bool(by_source.get("maps_place")),
            web_search_present=bool(by_source.get("web_search")),
            evidence_sources_count=len(by_source),
            category_clarity=category_clarity,
            official_website_found=bool(website_domain),
            official_website_source=official_website_source,
            website_domain_matches_brand=website_domain_matches_brand,
            official_site_position=official_site_position,
            official_site_discoverability=official_site_discoverability,
            directory_results_before_official=directory_results_before_official,
            directory_dominance=directory_dominance,
            knowledge_graph_present=knowledge_graph_present,
            local_presence_signal=local_presence_signal,
            weak_website_signal=weak_website_signal,
            digital_footprint_gap=digital_footprint_gap,
            source_agreement=source_agreement,
            maps_reviews_present=lead.review_count > 0,
            website_evidence_consistent=len(website_values) <= 1 and bool(website_values),
        )

    def _group_by_source(
        self, facts: Iterable[ProviderNormalizedFact]
    ) -> dict[str, list[ProviderNormalizedFact]]:
        grouped: dict[str, list[ProviderNormalizedFact]] = defaultdict(list)
        for fact in facts:
            grouped[fact.source_type].append(fact)
        for items in grouped.values():
            items.sort(key=lambda item: (item.created_at, item.id), reverse=True)
        return dict(grouped)

    def _has_hours(self, facts: dict[str, Any]) -> bool:
        for key in ("hours", "opening_hours", "open_state", "hours_summary"):
            value = facts.get(key)
            if isinstance(value, str) and value.strip():
                return True
            if isinstance(value, list) and any(
                isinstance(item, str) and item.strip() for item in value
            ):
                return True
            if isinstance(value, dict) and value:
                return True
        return False

    def _category_clarity(self, lead: Lead, facts: list[ProviderNormalizedFact]) -> float:
        categories = {
            category.casefold().strip()
            for category in [lead.category, *(item.category for item in facts)]
            if category and category.strip()
        }
        if not categories:
            return 0.2
        if len(categories) == 1:
            return 1.0
        if len(categories) == 2:
            return 0.65
        return 0.4

    def _official_website(
        self,
        by_source: dict[str, list[ProviderNormalizedFact]],
        lead: Lead,
    ) -> tuple[str | None, str | None]:
        source_priority = ("maps_place", "maps_search", "web_search")
        for source_type in source_priority:
            for fact in by_source.get(source_type, []):
                if fact.website_domain:
                    return source_type, fact.website_domain
        if lead.website_domain:
            return "lead_record", lead.website_domain
        return None, None

    def _official_site_position(self, latest_web: ProviderNormalizedFact | None) -> int | None:
        if latest_web is None:
            return None
        position = latest_web.facts_json.get("position")
        return int(position) if isinstance(position, int) else None

    def _directory_results_before_official(self, latest_web: ProviderNormalizedFact | None) -> int:
        if latest_web is None:
            return 0
        value = latest_web.facts_json.get("directory_results_before_official")
        return int(value) if isinstance(value, int) else 0

    def _knowledge_graph_present(self, latest_web: ProviderNormalizedFact | None) -> bool:
        if latest_web is None:
            return False
        return bool(latest_web.facts_json.get("knowledge_graph_present"))

    def _official_site_discoverability(
        self,
        latest_web: ProviderNormalizedFact | None,
        *,
        official_site_position: int | None,
        official_website_source: str | None,
        official_website_found: bool,
        knowledge_graph_present: bool,
    ) -> float | None:
        if latest_web is None:
            return 0.45 if official_website_found else None
        raw_confidence = latest_web.facts_json.get("visibility_confidence")
        confidence = float(raw_confidence) if isinstance(raw_confidence, (int, float)) else None
        if confidence is not None:
            return max(0.0, min(1.0, confidence))
        if knowledge_graph_present:
            return 0.95
        if official_site_position is not None:
            if official_site_position <= 3:
                return 0.85
            if official_site_position <= 10:
                return 0.65
            return 0.45
        if official_website_source in {"maps_place", "maps_search"}:
            return 0.4
        return 0.0

    def _domain_matches_brand(self, *, website_domain: str | None, company_name: str) -> bool:
        if not website_domain:
            return False
        hostname = urlparse(f"https://{website_domain}").hostname or website_domain
        hostname = hostname.casefold()
        brand_tokens = [
            token
            for token in re.findall(r"[a-z0-9]+", company_name.casefold())
            if len(token) >= 4 and token not in _STOPWORDS
        ]
        return any(token in hostname for token in brand_tokens)

    def _local_presence_signal(
        self,
        *,
        maps_search_present: bool,
        maps_place_present: bool,
        review_count: int,
        knowledge_graph_present: bool,
    ) -> float:
        components = [
            1.0 if maps_search_present else 0.0,
            1.0 if maps_place_present else 0.0,
            1.0 if knowledge_graph_present else 0.0,
            min(1.0, review_count / 25.0),
        ]
        return round(sum(components) / len(components), 2)

    def _weak_website_signal(
        self,
        *,
        official_website_found: bool,
        website_domain_matches_brand: bool,
        official_site_discoverability: float | None,
        official_website_source: str | None,
    ) -> float:
        if not official_website_found:
            return 1.0
        if not website_domain_matches_brand:
            return 0.8
        if official_site_discoverability is None:
            return 0.6
        if official_site_discoverability < 0.45:
            return 0.7
        if official_website_source == "web_search":
            return 0.45
        return 0.15

    def _digital_footprint_gap(
        self,
        *,
        lead: Lead,
        phone_present: bool,
        address_present: bool,
        hours_present: bool,
        official_site_discoverability: float | None,
        weak_website_signal: float,
    ) -> float:
        components = [
            0.0 if phone_present else 1.0,
            0.0 if address_present else 1.0,
            0.0 if hours_present else 1.0,
            1.0 - max(0.0, min(1.0, lead.data_completeness)),
            weak_website_signal,
            1.0
            - (official_site_discoverability if official_site_discoverability is not None else 0.0),
        ]
        return round(sum(components) / len(components), 2)

    def _source_agreement(self, lead: Lead, facts: list[ProviderNormalizedFact]) -> float:
        fields: dict[str, list[str]] = defaultdict(list)
        for value in [lead.phone, *(item.phone for item in facts)]:
            normalized = self._normalize_text(value)
            if normalized:
                fields["phone"].append(normalized)
        for value in [lead.address, *(item.address for item in facts)]:
            normalized = self._normalize_text(value)
            if normalized:
                fields["address"].append(normalized)
        for value in [lead.city, *(item.city for item in facts)]:
            normalized = self._normalize_text(value)
            if normalized:
                fields["city"].append(normalized)
        for value in [lead.website_domain, *(item.website_domain for item in facts)]:
            normalized = self._normalize_text(value)
            if normalized:
                fields["website_domain"].append(normalized)

        if not fields:
            return max(0.35, min(1.0, lead.data_confidence))

        scores: list[float] = []
        for values in fields.values():
            unique_values = set(values)
            if len(unique_values) == 1:
                scores.append(1.0)
            elif len(unique_values) == 2:
                scores.append(0.55)
            else:
                scores.append(0.25)

        coverage_bonus = min(1.0, len(fields) / 4.0)
        return round(((sum(scores) / len(scores)) * 0.8) + (coverage_bonus * 0.2), 2)

    def _directory_dominance(
        self,
        *,
        official_website_found: bool,
        official_site_position: int | None,
        directory_results_before_official: int,
        web_search_present: bool,
    ) -> float:
        if not web_search_present:
            return 0.5 if official_website_found else 0.8
        if not official_website_found:
            return 1.0
        if official_site_position is None:
            return 0.75
        penalty = min(1.0, directory_results_before_official / 4.0)
        position_penalty = min(1.0, max(0, official_site_position - 1) / 9.0)
        return round(min(1.0, (penalty * 0.6) + (position_penalty * 0.4)), 2)

    def _normalize_text(self, value: str | None) -> str | None:
        if not value:
            return None
        return re.sub(r"\s+", " ", value.strip().casefold())
