from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, cast

from app.modules.provider_serpapi.normalizers.shared import (
    clean_optional_text,
    compute_completeness,
    compute_domain,
    compute_identities,
    is_preferred_business_domain,
)
from app.modules.provider_serpapi.schemas import LeadCandidate

_TITLE_SEPARATOR_RE = re.compile(r"\s+(?:[-|:]\s+|\u2013\s+|\u2014\s+)")
_OFFICIAL_RE = re.compile(r"\b(official\s+(site|website)|homepage)\b", re.IGNORECASE)


class TavilyLeadDiscoveryNormalizer:
    """Turns Tavily Search results into the shared LeadCandidate model."""

    def normalize(
        self,
        payload: dict[str, Any],
        *,
        business_type: str,
        city: str,
        query: str,
        extracted_by_url: dict[str, str] | None = None,
    ) -> list[LeadCandidate]:
        extracted = extracted_by_url or {}
        results = self._result_items(payload)
        seen_domains: set[str] = set()
        seen_urls: set[str] = set()
        candidates: list[LeadCandidate] = []
        captured_at = datetime.now(tz=UTC).isoformat()

        for position, item in enumerate(results):
            url = clean_optional_text(item.get("url"), max_length=512)
            title = clean_optional_text(item.get("title"), max_length=255)
            if not url or not title:
                continue
            domain = compute_domain(url)
            if not is_preferred_business_domain(domain):
                continue
            dedupe_domain = domain.casefold() if domain else ""
            dedupe_url = url.casefold().rstrip("/")
            if dedupe_domain in seen_domains or dedupe_url in seen_urls:
                continue
            seen_domains.add(dedupe_domain)
            seen_urls.add(dedupe_url)

            content = clean_optional_text(item.get("content"), max_length=1200)
            extracted_content = clean_optional_text(extracted.get(url), max_length=1800)
            score = self._numeric_score(item.get("score"))
            confidence = self._confidence(position, score, bool(extracted_content or content))
            company_name = self._company_name_from_title(title, domain)
            completeness = compute_completeness(
                address=None,
                phone=None,
                website_domain=domain,
                rating=None,
                review_count=0,
                lat=None,
                lng=None,
                category=business_type,
            )
            facts: dict[str, Any] = {
                "provider": "tavily",
                "provider_shape": "tavily_search_result",
                "source": "tavily",
                "source_type": "tavily_search",
                "source_priority": 35,
                "evidence": {
                    "title": title,
                    "url": url,
                    "snippet": content,
                    "provider": "tavily",
                    "timestamp": captured_at,
                    "confidence": confidence,
                    "raw_metadata": {
                        "score": score,
                        "position": position,
                        "favicon": clean_optional_text(item.get("favicon"), max_length=512),
                        "published_date": clean_optional_text(
                            item.get("published_date"),
                            max_length=64,
                        ),
                    },
                },
                "query": query,
                "position": position,
                "result_count": len(results),
                "answer_present": False,
                "top_relevance_score": score,
                "visibility_confidence": confidence,
                "extracted_content": extracted_content,
                "provider_fields_present": sorted(item.keys()),
            }
            candidates.append(
                LeadCandidate(
                    company_name=company_name,
                    category=business_type,
                    city=city,
                    website_url=url,
                    website_domain=domain,
                    confidence=confidence,
                    completeness=completeness,
                    facts=facts,
                    identities=compute_identities(
                        data_cid=None,
                        data_id=None,
                        place_id=None,
                        website_domain=domain,
                        phone=None,
                        company_name=company_name,
                        city=city,
                        address=None,
                        lat=None,
                        lng=None,
                    ),
                )
            )

        return candidates

    def high_value_urls(self, payload: dict[str, Any], *, limit: int) -> list[str]:
        if limit <= 0:
            return []
        urls: list[str] = []
        seen_domains: set[str] = set()
        for item in self._result_items(payload):
            url = clean_optional_text(item.get("url"), max_length=512)
            domain = compute_domain(url)
            if not url or not is_preferred_business_domain(domain):
                continue
            dedupe_domain = domain.casefold() if domain else ""
            if dedupe_domain in seen_domains:
                continue
            seen_domains.add(dedupe_domain)
            urls.append(url)
            if len(urls) >= limit:
                break
        return urls

    def extracted_content_by_url(self, payload: dict[str, Any]) -> dict[str, str]:
        output: dict[str, str] = {}
        for item in self._extract_items(payload):
            url = clean_optional_text(item.get("url"), max_length=512)
            content = clean_optional_text(
                item.get("raw_content") or item.get("content"),
                max_length=1800,
            )
            if url and content:
                output[url] = content
        return output

    def _result_items(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        results = payload.get("results")
        if not isinstance(results, list):
            return []
        return [cast(dict[str, Any], item) for item in results if isinstance(item, dict)]

    def _extract_items(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        results = payload.get("results")
        if not isinstance(results, list):
            return []
        return [cast(dict[str, Any], item) for item in results if isinstance(item, dict)]

    def _company_name_from_title(self, title: str, domain: str | None) -> str:
        first_segment = _TITLE_SEPARATOR_RE.split(title, maxsplit=1)[0].strip()
        cleaned = _OFFICIAL_RE.sub("", first_segment).strip(" -|:")
        if cleaned:
            return cleaned[:255]
        if domain:
            return domain.split(".")[0].replace("-", " ").title()[:255]
        return title[:255]

    def _numeric_score(self, value: object) -> float | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int | float):
            return float(value)
        return None

    def _confidence(self, position: int, score: float | None, has_content: bool) -> float:
        relevance = max(0.0, min(score if score is not None else 0.5, 1.0))
        position_bonus = 0.12 if position == 0 else (0.08 if position <= 2 else 0.03)
        content_bonus = 0.08 if has_content else 0.0
        return round(min(0.95, 0.45 + relevance * 0.35 + position_bonus + content_bonus), 3)
