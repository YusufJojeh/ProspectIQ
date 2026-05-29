from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.enrichers.base import BaseLeadEnricher, EnrichmentPayload
from app.modules.provider_serpapi.client import SerpApiClient
from app.modules.provider_serpapi.engines.google_news import (
    build_google_news_params,
    extract_news_items,
    run_google_news,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.modules.leads.models import Lead

_HEADLINE_MAX_LENGTH = 120


class GoogleNewsEnricher(BaseLeadEnricher):
    name = "google_news"

    def __init__(self, client: SerpApiClient) -> None:
        self._client = client

    def enrich(self, lead: Lead, *, db: Session) -> EnrichmentPayload:
        query = " ".join(part for part in (lead.company_name, lead.city) if part)
        params = build_google_news_params(query=query)
        result = run_google_news(self._client, params=params)
        items = extract_news_items(result)

        mention_count = len(items)
        data: dict[str, Any] = {
            "mention_count": mention_count,
            "news_present": mention_count > 0,
        }
        if items:
            latest = items[0]
            data["latest_headline"] = str(latest.get("title", ""))[:_HEADLINE_MAX_LENGTH]
            data["latest_date"] = str(latest.get("date", ""))
        return EnrichmentPayload(source=self.name, data=data)
