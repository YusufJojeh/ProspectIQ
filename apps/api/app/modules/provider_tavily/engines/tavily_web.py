from __future__ import annotations

from typing import Any

from app.modules.provider_tavily.client import TavilyCallResult, TavilyClient

_MAX_QUERY_LENGTH = 400


def _clean_query(value: str) -> str:
    return " ".join(value.split()).strip()[:_MAX_QUERY_LENGTH]


def build_tavily_web_params(
    *,
    query: str,
    max_results: int = 5,
    search_depth: str = "basic",
    include_answer: bool = True,
) -> dict[str, Any]:
    cleaned_query = _clean_query(query)
    if not cleaned_query:
        raise ValueError("Tavily web search query must not be empty.")

    return {
        "query": cleaned_query,
        "search_depth": search_depth,
        "max_results": max(1, min(max_results, 20)),
        "include_answer": include_answer,
        "include_raw_content": False,
    }


def run_tavily_web(client: TavilyClient, *, params: dict[str, Any]) -> TavilyCallResult:
    return client.search(params)
