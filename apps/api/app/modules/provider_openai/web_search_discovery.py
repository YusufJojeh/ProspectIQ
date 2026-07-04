from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.modules.provider_serpapi.normalizers.shared import (
    clean_optional_text,
    coerce_float,
    coerce_int,
    compute_completeness,
    compute_domain,
    compute_identities,
    normalize_phone,
)
from app.modules.provider_serpapi.schemas import LeadCandidate

logger = logging.getLogger(__name__)

_MAX_BUSINESSES = 25
_ARABIC_RE = re.compile(r"[؀-ۿ]")
# OpenAI exposes the hosted web-search tool under two type names depending on
# the model generation; try the broadly-available preview type first.
_WEB_SEARCH_TOOL_TYPES = ("web_search_preview", "web_search")


class OpenAIWebSearchDiscovery:
    """Fallback lead discovery backed by OpenAI's hosted web-search tool.

    Used when the primary provider (SerpAPI) cannot serve a request — most
    commonly an HTTP 429 because the account search quota is exhausted. It asks
    the model to find real local businesses matching the search criteria and
    returns normalized :class:`LeadCandidate` objects, so the downstream
    normalize → dedupe → score pipeline is identical to the SerpAPI path.
    """

    def is_available(self) -> bool:
        settings = get_settings()
        return settings.discovery_openai_fallback_enabled and settings.has_openai_configured

    def discover(
        self,
        *,
        business_type: str,
        city: str,
        region: str | None,
        max_results: int,
        min_rating: float | None,
        max_rating: float | None,
        min_reviews: int | None,
        max_reviews: int | None,
    ) -> list[LeadCandidate]:
        settings = get_settings()
        if not self.is_available():
            return []

        limit = max(1, min(max_results or _MAX_BUSINESSES, _MAX_BUSINESSES))
        prompt = self._build_prompt(
            business_type=business_type,
            city=city,
            region=region,
            limit=limit,
            min_rating=min_rating,
            max_rating=max_rating,
            min_reviews=min_reviews,
            max_reviews=max_reviews,
        )

        try:
            raw_text = self._call_responses_api(settings, prompt)
        except httpx.HTTPError as exc:
            logger.warning("openai_web_search.http_error error=%s", str(exc)[:200])
            return []
        except Exception:
            logger.warning("openai_web_search.unexpected_error", exc_info=True)
            return []

        businesses = self._parse_businesses(raw_text)
        candidates: list[LeadCandidate] = []
        for business in businesses:
            candidate = self._to_candidate(business, default_city=city)
            if candidate is not None:
                candidates.append(candidate)
        logger.info(
            "openai_web_search.discovered raw=%s candidates=%s",
            len(businesses),
            len(candidates),
        )
        return candidates[:limit]

    def _build_prompt(
        self,
        *,
        business_type: str,
        city: str,
        region: str | None,
        limit: int,
        min_rating: float | None,
        max_rating: float | None,
        min_reviews: int | None,
        max_reviews: int | None,
    ) -> str:
        location = ", ".join(part for part in (city, region) if part)
        is_arabic = bool(_ARABIC_RE.search(f"{business_type} {city} {region or ''}"))
        criteria: list[str] = []
        if min_rating is not None and max_rating is not None:
            criteria.append(f"a Google rating between {min_rating} and {max_rating}")
        elif min_rating is not None:
            criteria.append(f"a Google rating of {min_rating} or higher")
        elif max_rating is not None:
            criteria.append(f"a Google rating of {max_rating} or lower")
        if min_reviews is not None and max_reviews is not None:
            criteria.append(f"a review count between {min_reviews} and {max_reviews}")
        elif min_reviews is not None:
            criteria.append(f"at least {min_reviews} reviews")
        elif max_reviews is not None:
            criteria.append(f"at most {max_reviews} reviews")
        criteria_line = (
            f" Prefer businesses with {', and '.join(criteria)}." if criteria else ""
        )
        language_line = (
            " The query is in Arabic; search Arabic-language sources and return company "
            "names in their original language."
            if is_arabic
            else ""
        )

        return (
            f"Use web search to find up to {limit} real, currently-operating "
            f'"{business_type}" businesses located in {location}.{criteria_line}'
            f"{language_line}\n\n"
            "Return ONLY a JSON object with this exact shape and no prose:\n"
            '{"businesses": [{"company_name": string, "address": string|null, '
            '"city": string|null, "phone": string|null, "website_url": string|null, '
            '"rating": number|null, "review_count": integer|null, '
            '"category": string|null}]}\n'
            "Rules: include only businesses you can verify from search results; use null "
            "for any field you are unsure about; do not invent phone numbers, ratings, or "
            "websites; rating must be on a 0-5 scale."
        )

    def _call_responses_api(self, settings: Settings, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        url = f"{settings.openai_base_url.rstrip('/')}/responses"
        last_error: httpx.HTTPStatusError | None = None
        with httpx.Client(timeout=httpx.Timeout(90.0, connect=10.0), headers=headers) as client:
            for tool_type in _WEB_SEARCH_TOOL_TYPES:
                try:
                    response = client.post(
                        url,
                        json={
                            "model": settings.openai_model,
                            "tools": [{"type": tool_type}],
                            "input": prompt,
                        },
                    )
                    response.raise_for_status()
                    return self._extract_output_text(response.json())
                except httpx.HTTPStatusError as exc:
                    # A 400 usually means this model rejects this tool type name;
                    # fall through and try the alternate spelling.
                    last_error = exc
                    if exc.response.status_code != 400:
                        raise
                    logger.info(
                        "openai_web_search.tool_type_rejected type=%s body=%s",
                        tool_type,
                        exc.response.text[:160],
                    )
        if last_error is not None:
            raise last_error
        return ""

    @staticmethod
    def _extract_output_text(payload: dict[str, Any]) -> str:
        # The Responses API exposes an aggregated convenience field on some SDKs;
        # over raw HTTP we assemble it from output[].content[].text ourselves.
        aggregated = payload.get("output_text")
        if isinstance(aggregated, str) and aggregated.strip():
            return aggregated
        chunks: list[str] = []
        for item in payload.get("output", []) or []:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            for content in item.get("content", []) or []:
                if isinstance(content, dict) and content.get("type") == "output_text":
                    text = content.get("text")
                    if isinstance(text, str):
                        chunks.append(text)
        return "\n".join(chunks)

    @staticmethod
    def _parse_businesses(raw_text: str) -> list[dict[str, Any]]:
        if not raw_text or not raw_text.strip():
            return []
        text = raw_text.strip()
        # Strip ```json ... ``` fences if the model added them.
        fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if fenced:
            text = fenced.group(1).strip()
        # Isolate the first balanced JSON object/array.
        obj_match = re.search(r"\{.*\}", text, re.DOTALL)
        candidate_text = obj_match.group(0) if obj_match else text
        try:
            parsed = json.loads(candidate_text)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, dict):
            businesses = parsed.get("businesses")
        elif isinstance(parsed, list):
            businesses = parsed
        else:
            businesses = None
        if not isinstance(businesses, list):
            return []
        return [item for item in businesses if isinstance(item, dict)]

    @staticmethod
    def _to_candidate(business: dict[str, Any], *, default_city: str) -> LeadCandidate | None:
        name = clean_optional_text(business.get("company_name"), max_length=255)
        if not name:
            return None
        website_url = clean_optional_text(business.get("website_url"), max_length=512)
        domain = compute_domain(website_url)
        phone = normalize_phone(business.get("phone"))
        address = clean_optional_text(business.get("address"), max_length=512)
        city = clean_optional_text(business.get("city")) or default_city
        category = clean_optional_text(business.get("category"), max_length=128)
        rating = coerce_float(business.get("rating"))
        if rating is not None:
            rating = max(0.0, min(5.0, rating))
        review_count = coerce_int(business.get("review_count"))

        identities = compute_identities(
            data_cid=None,
            data_id=None,
            place_id=None,
            website_domain=domain,
            phone=phone,
            company_name=name,
            city=city,
            address=address,
            lat=None,
            lng=None,
        )
        if not identities:
            return None
        completeness = compute_completeness(
            address=address,
            phone=phone,
            website_domain=domain,
            rating=rating,
            review_count=review_count,
            lat=None,
            lng=None,
            category=category,
        )
        return LeadCandidate(
            company_name=name,
            category=category,
            address=address,
            city=city,
            phone=phone,
            website_url=website_url,
            website_domain=domain,
            rating=rating,
            review_count=review_count,
            confidence=0.5,
            completeness=completeness,
            facts={
                "source_engine": "openai",
                "source_mode": "web_search_discovery",
                "discovery_provider": "openai_web_search",
            },
            identities=identities,
        )
