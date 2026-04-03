from __future__ import annotations

from typing import Protocol

from app.modules.scoring.schemas import ScoreBreakdownItem
from app.shared.dto.lead_facts import NormalizedLeadFacts


class ScoringStrategy(Protocol):
    key: str
    label: str

    def score(self, facts: NormalizedLeadFacts, weight: float) -> ScoreBreakdownItem: ...


class LocalTrustStrategy:
    key = "local_trust"
    label = "Local Trust"

    def score(self, facts: NormalizedLeadFacts, weight: float) -> ScoreBreakdownItem:
        rating = facts.rating or 0.0
        reviews = facts.review_count
        if reviews < 15:
            base_score = 90.0
            reason = "Low review volume suggests weak local proof."
        elif rating < 4.0:
            base_score = 80.0
            reason = (
                "Rating is below typical leaders in the market, leaving room for reputation work."
            )
        elif rating >= 4.5 and reviews >= 50:
            base_score = 30.0
            reason = "Strong rating and review count reduce immediate local-trust opportunity."
        else:
            base_score = 55.0
            reason = "Average local trust suggests optimization potential."
        return ScoreBreakdownItem(
            key=self.key,
            label=self.label,
            weight=weight,
            contribution=round(base_score * weight, 2),
            reason=reason,
        )


class WebsitePresenceStrategy:
    key = "website_presence"
    label = "Website Presence"

    def score(self, facts: NormalizedLeadFacts, weight: float) -> ScoreBreakdownItem:
        if facts.website_domain:
            base_score = 25.0
            reason = "A website was detected, so basic digital presence exists."
        else:
            base_score = 100.0
            reason = "No website detected, which is a direct service opportunity."
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
        confidence = facts.visibility_confidence
        source = facts.visibility_source or "unknown"
        if confidence is None:
            base_score = 70.0
            reason = "Search visibility is unknown; treat as moderate opportunity."
        elif confidence >= 0.7:
            base_score = 30.0
            reason = f"Website is discoverable via {source}, reducing visibility opportunity."
        elif confidence >= 0.5:
            base_score = 60.0
            reason = (
                f"Website is partially discoverable via {source}, suggesting room for improvement."
            )
        else:
            base_score = 90.0
            reason = f"Website is not strongly discoverable via {source}, indicating high visibility opportunity."
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
        completeness = max(0.0, min(1.0, facts.data_completeness))
        base_score = min(100.0, 30.0 + (1.0 - completeness) * 70.0)
        if not facts.website_domain:
            base_score = min(100.0, base_score + 10.0)
        reason = "Missing public business details and conversion signals imply agency opportunity."
        return ScoreBreakdownItem(
            key=self.key,
            label=self.label,
            weight=weight,
            contribution=round(base_score * weight, 2),
            reason=reason,
        )


class DataConfidenceStrategy:
    key = "data_confidence"
    label = "Data Confidence"

    def score(self, facts: NormalizedLeadFacts, weight: float) -> ScoreBreakdownItem:
        confidence = max(0.0, min(1.0, facts.data_confidence))
        base_score = confidence * 100.0
        reason = "Higher confidence indicates more reliable evidence and easier outreach targeting."
        return ScoreBreakdownItem(
            key=self.key,
            label=self.label,
            weight=weight,
            contribution=round(base_score * weight, 2),
            reason=reason,
        )
