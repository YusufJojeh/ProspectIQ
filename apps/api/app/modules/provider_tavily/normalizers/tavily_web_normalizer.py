from __future__ import annotations

from typing import Any, cast

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
    "yellowpages.com",
    "linkedin.com",
}


class TavilyWebNormalizer:
    """Normalizes a Tavily `/search` response into the shared WebsiteDiscoveryResult shape.

    Facts carry Tavily-specific signal (answer presence, result relevance scores)
    so scoring can weigh Tavily evidence independently of SerpAPI web-search evidence.
    """

    def normalize(self, payload: dict[str, Any]) -> WebsiteDiscoveryResult:
        answer_value = payload.get("answer")
        answer_present = isinstance(answer_value, str) and bool(answer_value.strip())

        results_value = payload.get("results")
        results: list[dict[str, Any]] = (
            [cast(dict[str, Any], item) for item in results_value if isinstance(item, dict)]
            if isinstance(results_value, list)
            else []
        )

        directory_results_before_official = 0
        directory_domains: list[str] = []
        top_relevance_score = 0.0
        for index, item in enumerate(results):
            url_value = item.get("url")
            url = url_value if isinstance(url_value, str) else None
            domain = compute_domain(url)
            score = item.get("score")
            if index == 0 and isinstance(score, int | float):
                top_relevance_score = float(score)

            if self._is_directory_domain(domain) and domain:
                directory_results_before_official += 1
                directory_domains.append(domain)
                continue

            if url and is_preferred_business_domain(domain):
                return WebsiteDiscoveryResult(
                    website_url=url,
                    website_domain=domain,
                    confidence=self._position_confidence(index, score),
                    facts={
                        "source": "tavily",
                        "position": index,
                        "official_site_found": True,
                        "official_site_position": index,
                        "directory_results_before_official": directory_results_before_official,
                        "directory_domains": directory_domains,
                        "answer_present": answer_present,
                        "result_count": len(results),
                        "top_relevance_score": top_relevance_score,
                        "match_relevance_score": float(score) if isinstance(score, int | float) else None,
                        "local_results_present": False,
                        "knowledge_graph_present": False,
                    },
                )

        return WebsiteDiscoveryResult(
            website_url=None,
            website_domain=None,
            confidence=0.0,
            facts={
                "source": "tavily",
                "official_site_found": False,
                "official_site_position": None,
                "directory_results_before_official": directory_results_before_official,
                "directory_domains": directory_domains,
                "answer_present": answer_present,
                "result_count": len(results),
                "top_relevance_score": top_relevance_score,
                "match_relevance_score": None,
                "local_results_present": False,
                "knowledge_graph_present": False,
            },
        )

    def _is_directory_domain(self, domain: str | None) -> bool:
        if not domain:
            return False
        hostname = domain.casefold()
        return any(
            hostname == candidate or hostname.endswith(f".{candidate}")
            for candidate in _DIRECTORY_DOMAINS
        )

    def _position_confidence(self, position: int, score: object) -> float:
        base = 0.85 if position == 0 else (0.6 if position <= 2 else 0.4)
        if isinstance(score, int | float):
            return round(min(1.0, max(0.0, (base * 0.6) + (float(score) * 0.4))), 2)
        return base
