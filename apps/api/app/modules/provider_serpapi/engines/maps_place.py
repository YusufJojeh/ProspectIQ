from __future__ import annotations

from typing import Any

from app.modules.provider_serpapi.client import ProviderCallResult, SerpApiClient


def build_maps_place_params(*, place_key: str, hl: str, gl: str, google_domain: str) -> dict[str, Any]:
    return {
        "engine": "google_maps",
        "type": "place",
        "data": place_key,
        "hl": hl,
        "gl": gl,
        "google_domain": google_domain,
    }


def run_maps_place(client: SerpApiClient, *, params: dict[str, Any]) -> ProviderCallResult:
    return client.search(params)
