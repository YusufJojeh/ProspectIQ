from __future__ import annotations

from typing import Any

from app.modules.provider_serpapi.client import ProviderCallResult, SerpApiClient

_MAX_QUERY_LENGTH = 220
_MAX_NEWS_RESULTS = 10


def _clean_query(value: str) -> str:
    return " ".join(value.split()).strip()[:_MAX_QUERY_LENGTH]


def build_google_news_params(
    *,
    query: str,
    hl: str = "en",
    gl: str = "us",
) -> dict[str, Any]:
    cleaned_query = _clean_query(query)
    if not cleaned_query:
        raise ValueError("SerpAPI Google News query must not be empty.")

    return {
        "engine": "google_news",
        "q": cleaned_query,
        "hl": hl,
        "gl": gl,
    }


def run_google_news(client: SerpApiClient, *, params: dict[str, Any]) -> ProviderCallResult:
    return client.search(params)


def extract_news_items(
    result: ProviderCallResult, *, max_items: int = _MAX_NEWS_RESULTS
) -> list[dict[str, Any]]:
    """
    Extract a flat list of news items from a Google News SerpAPI result.
    Each item: { title, link, source, date, snippet }
    """
    if not result.ok or not result.payload:
        return []

    raw_results = result.payload.get("news_results", [])
    if not isinstance(raw_results, list):
        return []

    items: list[dict[str, Any]] = []
    for raw in raw_results[:max_items]:
        if not isinstance(raw, dict):
            continue
        source_info = raw.get("source") or {}
        source_name = source_info.get("name") if isinstance(source_info, dict) else str(source_info)
        items.append(
            {
                "title": raw.get("title", ""),
                "link": raw.get("link", ""),
                "source": source_name or "",
                "date": raw.get("date", ""),
                "snippet": raw.get("snippet", ""),
            }
        )
    return items
