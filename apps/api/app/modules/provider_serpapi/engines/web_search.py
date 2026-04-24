from __future__ import annotations

from typing import Any

from app.modules.provider_serpapi.client import ProviderCallResult, SerpApiClient

_MAX_QUERY_LENGTH = 220


def _clean_query(value: str) -> str:
    return " ".join(value.split()).strip()[:_MAX_QUERY_LENGTH]


def build_web_search_params(*, query: str, hl: str, gl: str, google_domain: str) -> dict[str, Any]:
    return {
        "engine": "google",
        "q": _clean_query(query),
        "hl": hl,
        "gl": gl,
        "google_domain": google_domain,
    }


def run_web_search(client: SerpApiClient, *, params: dict[str, Any]) -> ProviderCallResult:
    return client.search(params)
