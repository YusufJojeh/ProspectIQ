from __future__ import annotations

import re
from typing import Any

from app.modules.provider_serpapi.client import ProviderCallResult, SerpApiClient

_MAX_QUERY_LENGTH = 220
_ARABIC_RE = re.compile(r"[\u0600-\u06FF]")


def _clean_query_fragment(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = " ".join(value.split()).strip()
    return cleaned or None


def _contains_arabic(*values: str | None) -> bool:
    return any(value and _ARABIC_RE.search(value) for value in values)


def _contains_fragment(value: str | None, fragment: str | None) -> bool:
    if not value or not fragment:
        return False
    return fragment.casefold() in value.casefold()


def build_maps_search_params(
    *,
    business_type: str,
    city: str,
    region: str | None,
    radius_km: int | None,
    keyword_filter: str | None,
    hl: str,
    gl: str,
    google_domain: str,
    page: int = 1,
) -> dict[str, Any]:
    cleaned_business_type = _clean_query_fragment(business_type)
    cleaned_city = _clean_query_fragment(city)
    cleaned_region = _clean_query_fragment(region)
    cleaned_keyword = _clean_query_fragment(keyword_filter)
    is_arabic_query = _contains_arabic(
        cleaned_business_type,
        cleaned_city,
        cleaned_region,
        cleaned_keyword,
    )
    in_token = "\u0641\u064a" if is_arabic_query else "in"
    within_parts = (
        ["\u0636\u0645\u0646", str(radius_km), "\u0643\u0645"]
        if is_arabic_query
        else ["within", str(radius_km), "km"]
    )
    query_parts = [
        cleaned_business_type,
    ]
    if cleaned_city and not _contains_fragment(cleaned_business_type, cleaned_city):
        query_parts.extend([in_token, cleaned_city])
    if cleaned_region and not _contains_fragment(cleaned_business_type, cleaned_region):
        query_parts.append(cleaned_region)
    if radius_km is not None:
        query_parts.extend(within_parts)
    if cleaned_keyword and not _contains_fragment(cleaned_business_type, cleaned_keyword):
        query_parts.append(cleaned_keyword)
    query = " ".join(part for part in query_parts if part)[:_MAX_QUERY_LENGTH]

    params: dict[str, Any] = {
        "engine": "google_maps",
        "type": "search",
        "q": query,
        "hl": hl,
        "gl": gl,
        "google_domain": google_domain,
    }
    if page > 1:
        params["start"] = (page - 1) * 20
    return params


def run_maps_search(client: SerpApiClient, *, params: dict[str, Any]) -> ProviderCallResult:
    return client.search(params)
