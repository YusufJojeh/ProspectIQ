from __future__ import annotations

from typing import Any, cast

from app.modules.provider_serpapi.normalizers.shared import (
    compute_domain,
    is_preferred_business_domain,
)
from app.modules.provider_serpapi.schemas import WebsiteDiscoveryResult


class WebSearchNormalizer:
    def normalize(self, payload: dict[str, Any]) -> WebsiteDiscoveryResult:
        knowledge_graph_value = payload.get("knowledge_graph")
        knowledge_graph: dict[str, Any] = (
            cast(dict[str, Any], knowledge_graph_value)
            if isinstance(knowledge_graph_value, dict)
            else {}
        )
        website_value = knowledge_graph.get("website")
        website = website_value if isinstance(website_value, str) else None
        website_domain = compute_domain(website)
        if website and is_preferred_business_domain(website_domain):
            return WebsiteDiscoveryResult(
                website_url=website,
                website_domain=website_domain,
                confidence=0.75,
                facts={"source": "knowledge_graph"},
            )

        organic_results_value = payload.get("organic_results")
        if isinstance(organic_results_value, list):
            for item in organic_results_value:
                if not isinstance(item, dict):
                    continue
                item_dict = cast(dict[str, Any], item)
                link_value = item_dict.get("link")
                link = link_value if isinstance(link_value, str) else None
                link_domain = compute_domain(link)
                if link and is_preferred_business_domain(link_domain):
                    return WebsiteDiscoveryResult(
                        website_url=link,
                        website_domain=link_domain,
                        confidence=0.55,
                        facts={
                            "source": "organic_results",
                            "position": item_dict.get("position"),
                        },
                    )

        return WebsiteDiscoveryResult(
            website_url=None, website_domain=None, confidence=0.0, facts={"source": "none"}
        )
