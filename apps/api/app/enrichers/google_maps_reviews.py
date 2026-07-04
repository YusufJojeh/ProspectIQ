from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.enrichers.base import BaseLeadEnricher, EnrichmentPayload
from app.modules.provider_serpapi.client import SerpApiClient
from app.modules.provider_serpapi.engines.google_maps_reviews import (
    build_google_maps_reviews_params,
    extract_place_summary,
    extract_reviews,
    run_google_maps_reviews,
)
from app.modules.provider_serpapi.repository import ProviderEvidenceRepository

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.modules.leads.models import Lead

_POSITIVE_TERMS = (
    "great",
    "excellent",
    "amazing",
    "love",
    "best",
    "friendly",
    "recommend",
    "perfect",
    "wonderful",
    "helpful",
)
_NEGATIVE_TERMS = (
    "bad",
    "poor",
    "terrible",
    "worst",
    "rude",
    "disappointed",
    "awful",
    "slow",
    "horrible",
    "never",
)


class GoogleMapsReviewsEnricher(BaseLeadEnricher):
    name = "google_maps_reviews"

    def __init__(
        self,
        client: SerpApiClient,
        *,
        evidence_repository: ProviderEvidenceRepository | None = None,
    ) -> None:
        self._client = client
        self._evidence_repository = evidence_repository or ProviderEvidenceRepository()

    def enrich(self, lead: Lead, *, db: Session) -> EnrichmentPayload:
        lookup = self._evidence_repository.get_best_place_lookup(db, lead.id)
        if lookup is None:
            return EnrichmentPayload.empty(self.name)

        if lookup.key_type == "place_id":
            params = build_google_maps_reviews_params(place_id=lookup.value)
        else:
            params = build_google_maps_reviews_params(data_id=lookup.value)

        result = run_google_maps_reviews(self._client, params=params)
        reviews = extract_reviews(result)
        summary = extract_place_summary(result)

        data: dict[str, Any] = {}
        if "rating" in summary:
            data["rating"] = summary["rating"]
        if "review_count" in summary:
            data["review_count"] = summary["review_count"]
        if reviews:
            data["sentiment_ratio"] = self._sentiment_ratio(reviews)

        if not data:
            return EnrichmentPayload.empty(self.name)
        return EnrichmentPayload(source=self.name, data=data)

    def _sentiment_ratio(self, reviews: list[dict[str, Any]]) -> dict[str, float]:
        positive = neutral = negative = 0
        for review in reviews:
            label = self._classify(review)
            if label == "positive":
                positive += 1
            elif label == "negative":
                negative += 1
            else:
                neutral += 1
        total = positive + neutral + negative
        if total == 0:
            return {"positive": 0.0, "neutral": 0.0, "negative": 0.0}
        return {
            "positive": round(positive / total, 3),
            "neutral": round(neutral / total, 3),
            "negative": round(negative / total, 3),
        }

    def _classify(self, review: dict[str, Any]) -> str:
        rating = review.get("rating")
        if isinstance(rating, int | float):
            if rating >= 4:
                return "positive"
            if rating <= 2:
                return "negative"
            return "neutral"
        snippet = str(review.get("snippet", "")).lower()
        pos = sum(1 for term in _POSITIVE_TERMS if term in snippet)
        neg = sum(1 for term in _NEGATIVE_TERMS if term in snippet)
        if pos > neg:
            return "positive"
        if neg > pos:
            return "negative"
        return "neutral"
