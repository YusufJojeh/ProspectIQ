from __future__ import annotations

from typing import Any

from app.modules.provider_serpapi.client import ProviderCallResult, SerpApiClient


def build_web_search_params(*, query: str, hl: str, gl: str, google_domain: str) -> dict[str, Any]:
    return {
        "engine": "google",
        "q": query,
        "hl": hl,
        "gl": gl,
        "google_domain": google_domain,
    }


def run_web_search(client: SerpApiClient, *, params: dict[str, Any]) -> ProviderCallResult:
    return client.search(params)
