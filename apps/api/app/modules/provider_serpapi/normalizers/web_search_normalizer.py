from __future__ import annotations

from typing import Any, cast
from urllib.parse import urlparse

from app.modules.provider_serpapi.normalizers.shared import (
    compute_domain,
    is_preferred_business_domain,
)
from app.modules.provider_serpapi.schemas import WebsiteDiscoveryResult

_DIRECTORY_DOMAINS = {
    "facebook.com",
    "foursquare.com",
    "tripadvisor.com",
    "yelp.com",
}


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
        local_results_present = isinstance(payload.get("local_results"), list) and bool(
            payload.get("local_results")
        )
        if website and is_preferred_business_domain(website_domain):
            return WebsiteDiscoveryResult(
                website_url=website,
                website_domain=website_domain,
                confidence=0.75,
                facts={
                    "source": "knowledge_graph",
                    "knowledge_graph_present": True,
                    "official_site_found": True,
                    "official_site_position": 0,
                    "directory_results_before_official": 0,
                    "local_results_present": local_results_present,
                },
            )

        organic_results_value = payload.get("organic_results")
        if isinstance(organic_results_value, list):
            directory_results_before_official = 0
            directory_domains: list[str] = []
            for item in organic_results_value:
                if not isinstance(item, dict):
                    continue
                item_dict = cast(dict[str, Any], item)
                link_value = item_dict.get("link")
                link = link_value if isinstance(link_value, str) else None
                link_domain = compute_domain(link)
                if self._is_directory_domain(link_domain) and link_domain:
                    directory_results_before_official += 1
                    directory_domains.append(link_domain)
                if link and is_preferred_business_domain(link_domain):
                    position = item_dict.get("position")
                    return WebsiteDiscoveryResult(
                        website_url=link,
                        website_domain=link_domain,
                        confidence=self._position_confidence(position),
                        facts={
                            "source": "organic_results",
                            "position": position,
                            "official_site_found": True,
                            "official_site_position": position,
                            "directory_results_before_official": directory_results_before_official,
                            "directory_domains": directory_domains,
                            "knowledge_graph_present": bool(knowledge_graph),
                            "local_results_present": local_results_present,
                        },
                    )

        return WebsiteDiscoveryResult(
            website_url=None,
            website_domain=None,
            confidence=0.0,
            facts={
                "source": "none",
                "official_site_found": False,
                "official_site_position": None,
                "directory_results_before_official": directory_results_before_official
                if isinstance(organic_results_value, list)
                else 0,
                "knowledge_graph_present": bool(knowledge_graph),
                "local_results_present": local_results_present,
            },
        )

    def _is_directory_domain(self, link_domain: str | None) -> bool:
        if not link_domain:
            return False
        hostname = urlparse(f"https://{link_domain}").hostname or link_domain
        hostname = hostname.casefold()
        return any(
            hostname == domain or hostname.endswith(f".{domain}") for domain in _DIRECTORY_DOMAINS
        )

    def _position_confidence(self, position: object) -> float:
        if not isinstance(position, int):
            return 0.45
        if position <= 3:
            return 0.85
        if position <= 10:
            return 0.6
        return 0.35
