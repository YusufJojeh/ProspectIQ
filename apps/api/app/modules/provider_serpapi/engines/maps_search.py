from __future__ import annotations

from typing import Any

from app.modules.provider_serpapi.client import ProviderCallResult, SerpApiClient

_MAX_QUERY_LENGTH = 220


def _clean_query_fragment(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = " ".join(value.split()).strip()
    return cleaned or None


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
    query_parts = [
        _clean_query_fragment(business_type),
        "in",
        _clean_query_fragment(city),
    ]
    if region:
        query_parts.append(_clean_query_fragment(region))
    if radius_km is not None:
        query_parts.extend(["within", str(radius_km), "km"])
    if keyword_filter:
        query_parts.append(_clean_query_fragment(keyword_filter))
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
