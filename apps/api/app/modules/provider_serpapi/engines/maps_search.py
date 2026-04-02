from __future__ import annotations

from typing import Any

from app.modules.provider_serpapi.client import ProviderCallResult, SerpApiClient


def build_maps_search_params(
    *,
    business_type: str,
    city: str,
    region: str | None,
    hl: str,
    gl: str,
    google_domain: str,
) -> dict[str, Any]:
    query = f"{business_type} in {city}"
    if region:
        query = f"{query}, {region}"
    return {
        "engine": "google_maps",
        "type": "search",
        "q": query,
        "hl": hl,
        "gl": gl,
        "google_domain": google_domain,
    }


def run_maps_search(client: SerpApiClient, *, params: dict[str, Any]) -> ProviderCallResult:
    return client.search(params)
