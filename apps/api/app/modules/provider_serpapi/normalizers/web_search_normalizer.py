from __future__ import annotations

from typing import Any

from app.modules.provider_serpapi.normalizers.shared import compute_domain
from app.modules.provider_serpapi.schemas import WebsiteDiscoveryResult


class WebSearchNormalizer:
    def normalize(self, payload: dict[str, Any]) -> WebsiteDiscoveryResult:
        knowledge_graph = payload.get("knowledge_graph") if isinstance(payload.get("knowledge_graph"), dict) else {}
        website = knowledge_graph.get("website") if isinstance(knowledge_graph.get("website"), str) else None
        if website:
            return WebsiteDiscoveryResult(
                website_url=website,
                website_domain=compute_domain(website),
                confidence=0.75,
                facts={"source": "knowledge_graph"},
            )

        organic_results = payload.get("organic_results")
        if isinstance(organic_results, list):
            for item in organic_results:
                if not isinstance(item, dict):
                    continue
                link = item.get("link") if isinstance(item.get("link"), str) else None
                if link:
                    return WebsiteDiscoveryResult(
                        website_url=link,
                        website_domain=compute_domain(link),
                        confidence=0.55,
                        facts={"source": "organic_results"},
                    )

        return WebsiteDiscoveryResult(website_url=None, website_domain=None, confidence=0.0, facts={"source": "none"})

