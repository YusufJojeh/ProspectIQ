from __future__ import annotations

from typing import Any

from app.modules.provider_serpapi.client import ProviderCallResult, SerpApiClient
from app.modules.provider_serpapi.schemas import PlaceLookupKey


def build_maps_place_params(
    *, lookup: PlaceLookupKey, hl: str, gl: str, google_domain: str
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "engine": "google_maps",
        "type": "place",
        "hl": hl,
        "gl": gl,
        "google_domain": google_domain,
    }
    params[lookup.key_type] = lookup.value
    return params


def run_maps_place(client: SerpApiClient, *, params: dict[str, Any]) -> ProviderCallResult:
    return client.search(params)
