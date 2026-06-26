from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import TYPE_CHECKING, Any

from app.enrichers.base import BaseLeadEnricher, EnrichmentPayload
from app.modules.provider_serpapi.client import SerpApiClient
from app.modules.provider_serpapi.engines.yelp import (
    build_yelp_params,
    extract_businesses,
    run_yelp,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.modules.leads.models import Lead

_NAME_MATCH_THRESHOLD = 0.85


def _digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def _name_ratio(left: str, right: str) -> float:
    return SequenceMatcher(None, left.casefold().strip(), right.casefold().strip()).ratio()


class YelpEnricher(BaseLeadEnricher):
    """Secondary discovery source. Attaches Yelp ratings to matched leads.

    New-lead creation from unmatched Yelp businesses is intentionally deferred.
    """

    name = "yelp"

    def __init__(self, client: SerpApiClient) -> None:
        self._client = client

    def enrich(self, lead: Lead, *, db: Session) -> EnrichmentPayload:
        find_desc = lead.category or lead.company_name
        find_loc = lead.city or ""
        params = build_yelp_params(find_desc=find_desc, find_loc=find_loc)
        result = run_yelp(self._client, params=params)
        businesses = extract_businesses(result)
        if not businesses:
            return EnrichmentPayload.empty(self.name)

        match = self._match(lead, businesses)
        if match is None:
            return EnrichmentPayload.empty(self.name)

        data: dict[str, Any] = {}
        rating = match.get("rating")
        if isinstance(rating, int | float):
            data["yelp_rating"] = float(rating)
        review_count = match.get("review_count")
        if isinstance(review_count, int):
            data["yelp_review_count"] = review_count
        url = match.get("url")
        if isinstance(url, str) and url:
            data["yelp_url"] = url

        if not data:
            return EnrichmentPayload.empty(self.name)
        return EnrichmentPayload(source=self.name, data=data)

    def _match(self, lead: Lead, businesses: list[dict[str, Any]]) -> dict[str, Any] | None:
        lead_phone = _digits(lead.phone)
        if lead_phone:
            for business in businesses:
                if _digits(str(business.get("phone", ""))) == lead_phone:
                    return business

        best: dict[str, Any] | None = None
        best_ratio = 0.0
        for business in businesses:
            ratio = _name_ratio(lead.company_name, str(business.get("name", "")))
            if ratio > best_ratio:
                best_ratio = ratio
                best = business
        if best is not None and best_ratio >= _NAME_MATCH_THRESHOLD:
            return best
        return None
