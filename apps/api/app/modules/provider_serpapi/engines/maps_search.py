from __future__ import annotations

from typing import Any

from app.modules.provider_serpapi.client import ProviderCallResult, SerpApiClient


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
    query = f"{business_type} in {city}"
    if region:
        query = f"{query}, {region}"
    if radius_km is not None:
        query = f"{query} within {radius_km} km"
    if keyword_filter:
        query = f"{query} {keyword_filter}"

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
