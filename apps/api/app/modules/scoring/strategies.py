from __future__ import annotations

from typing import Protocol

from app.modules.scoring.schemas import ScoreBreakdownItem
from app.shared.dto.lead_facts import NormalizedLeadFacts


class ScoringStrategy(Protocol):
    key: str
    label: str

    def score(self, facts: NormalizedLeadFacts, weight: float) -> ScoreBreakdownItem: ...


def _clamp(value: float, *, lower: float = 0.0, upper: float = 100.0) -> float:
    return max(lower, min(upper, value))


class LocalTrustStrategy:
    key = "local_trust"
    label = "Local Trust"

    def score(self, facts: NormalizedLeadFacts, weight: float) -> ScoreBreakdownItem:
        rating_score = self._rating_score(facts.rating)
        review_score = self._review_score(facts.review_count)
        completeness_score = (
            (20 if facts.phone_present else 0)
            + (20 if facts.address_present else 0)
            + (20 if facts.hours_present else 0)
            + (facts.category_clarity * 40)
        )
        base_score = _clamp(
            (rating_score * 0.4) + (review_score * 0.3) + (completeness_score * 0.3)
        )
        reason = (
            f"Rating contributes {rating_score:.0f}/100, review depth contributes {review_score:.0f}/100, "
            f"and listing completeness contributes {completeness_score:.0f}/100 "
            f"(phone={'yes' if facts.phone_present else 'no'}, address={'yes' if facts.address_present else 'no'}, "
            f"hours={'yes' if facts.hours_present else 'no'}, category clarity={round(facts.category_clarity * 100)}%)."
        )
        return ScoreBreakdownItem(
            key=self.key,
            label=self.label,
            weight=weight,
            contribution=round(base_score * weight, 2),
            reason=reason,
        )

    def _rating_score(self, rating: float | None) -> float:
        if rating is None:
            return 40.0
        if rating >= 4.7:
            return 95.0
        if rating >= 4.5:
            return 88.0
        if rating >= 4.2:
            return 74.0
        if rating >= 4.0:
            return 60.0
        if rating >= 3.7:
            return 42.0
        return 25.0

    def _review_score(self, review_count: int) -> float:
        if review_count >= 80:
            return 95.0
        if review_count >= 40:
            return 82.0
        if review_count >= 15:
            return 68.0
        if review_count >= 5:
            return 45.0
        return 20.0


class WebsitePresenceStrategy:
    key = "website_presence"
    label = "Website Presence"

    def score(self, facts: NormalizedLeadFacts, weight: float) -> ScoreBreakdownItem:
        if not facts.official_website_found:
            base_score = 0.0
            reason = "No official website was confirmed in maps or web-search evidence."
        else:
            source_score = {
                "maps_place": 95.0,
                "maps_search": 85.0,
                "web_search": 72.0,
                "lead_record": 60.0,
            }.get(facts.official_website_source or "", 60.0)
            brand_bonus = 10.0 if facts.website_domain_matches_brand else -12.0
            consistency_bonus = 8.0 if facts.website_evidence_consistent else -8.0
            base_score = _clamp(source_score + brand_bonus + consistency_bonus)
            reason = (
                f"An official website was found via {facts.official_website_source or 'stored lead facts'}. "
                f"Brand/domain consistency is {'strong' if facts.website_domain_matches_brand else 'weak'}, "
                f"and cross-source website agreement is {'present' if facts.website_evidence_consistent else 'missing'}."
            )
        return ScoreBreakdownItem(
            key=self.key,
            label=self.label,
            weight=weight,
            contribution=round(base_score * weight, 2),
            reason=reason,
        )


class SearchVisibilityStrategy:
    key = "search_visibility"
    label = "Search Visibility"

    def score(self, facts: NormalizedLeadFacts, weight: float) -> ScoreBreakdownItem:
        discoverability = (facts.official_site_discoverability or 0.0) * 100
        local_presence = facts.local_presence_signal * 100
        directory_penalty = facts.directory_dominance * 35
        knowledge_bonus = 10 if facts.knowledge_graph_present else 0
        base_score = _clamp(
            (discoverability * 0.6) + (local_presence * 0.25) + knowledge_bonus - directory_penalty
        )
        reason = (
            f"Official-site discoverability is {round(discoverability)}%, local presence is {round(local_presence)}%, "
            f"directory dominance is {round(facts.directory_dominance * 100)}%, and "
            f"knowledge presence is {'present' if facts.knowledge_graph_present else 'not detected'}."
        )
        return ScoreBreakdownItem(
            key=self.key,
            label=self.label,
            weight=weight,
            contribution=round(base_score * weight, 2),
            reason=reason,
        )


class OpportunityStrategy:
    key = "opportunity"
    label = "Opportunity Signals"

    def score(self, facts: NormalizedLeadFacts, weight: float) -> ScoreBreakdownItem:
        website_gap = facts.weak_website_signal * 100
        review_gap = self._review_gap_score(facts.review_count)
        visibility_gap = (1 - (facts.official_site_discoverability or 0.0)) * 100
        footprint_gap = facts.digital_footprint_gap * 100
        base_score = _clamp(
            (website_gap * 0.35)
            + (review_gap * 0.2)
            + (visibility_gap * 0.2)
            + (footprint_gap * 0.25)
        )
        reason = (
            f"Opportunity is driven by website gap {round(website_gap)}%, review gap {round(review_gap)}%, "
            f"visibility gap {round(visibility_gap)}%, and digital-footprint gap {round(footprint_gap)}%."
        )
        return ScoreBreakdownItem(
            key=self.key,
            label=self.label,
            weight=weight,
            contribution=round(base_score * weight, 2),
            reason=reason,
        )

    def _review_gap_score(self, review_count: int) -> float:
        if review_count < 5:
            return 95.0
        if review_count < 15:
            return 80.0
        if review_count < 40:
            return 55.0
        if review_count < 80:
            return 35.0
        return 15.0


class DataConfidenceStrategy:
    key = "data_confidence"
    label = "Data Confidence"

    def score(self, facts: NormalizedLeadFacts, weight: float) -> ScoreBreakdownItem:
        data_confidence = facts.data_confidence * 100
        source_agreement = facts.source_agreement * 100
        coverage = min(100.0, (facts.evidence_sources_count / 3) * 100)
        base_score = _clamp((data_confidence * 0.55) + (source_agreement * 0.3) + (coverage * 0.15))
        reason = (
            f"Stored evidence confidence is {round(data_confidence)}%, source agreement is {round(source_agreement)}%, "
            f"and source coverage is {round(coverage)}% across {facts.evidence_sources_count} normalized source types."
        )
        return ScoreBreakdownItem(
            key=self.key,
            label=self.label,
            weight=weight,
            contribution=round(base_score * weight, 2),
            reason=reason,
        )
