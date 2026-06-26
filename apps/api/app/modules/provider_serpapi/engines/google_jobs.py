from __future__ import annotations

from typing import Any

from app.modules.provider_serpapi.client import ProviderCallResult, SerpApiClient

_MAX_QUERY_LENGTH = 220
_MAX_JOBS_RESULTS = 10


def _clean_query(value: str) -> str:
    return " ".join(value.split()).strip()[:_MAX_QUERY_LENGTH]


def build_google_jobs_params(
    *,
    query: str,
    location: str = "",
    hl: str = "en",
    gl: str = "us",
) -> dict[str, Any]:
    cleaned_query = _clean_query(query)
    if not cleaned_query:
        raise ValueError("SerpAPI Google Jobs query must not be empty.")

    params: dict[str, Any] = {
        "engine": "google_jobs",
        "q": cleaned_query,
        "hl": hl,
        "gl": gl,
    }
    if location and location.strip():
        params["location"] = " ".join(location.split()).strip()
    return params


def run_google_jobs(client: SerpApiClient, *, params: dict[str, Any]) -> ProviderCallResult:
    return client.search(params)


def extract_jobs_items(
    result: ProviderCallResult, *, max_items: int = _MAX_JOBS_RESULTS
) -> list[dict[str, Any]]:
    """
    Extract a flat list of job postings from a Google Jobs SerpAPI result.
    Each item: { title, company_name, location, via, description }
    Job postings signal company growth (hiring = expanding) — valuable for lead scoring.
    """
    if not result.ok or not result.payload:
        return []

    raw_results = result.payload.get("jobs_results", [])
    if not isinstance(raw_results, list):
        return []

    items: list[dict[str, Any]] = []
    for raw in raw_results[:max_items]:
        if not isinstance(raw, dict):
            continue
        items.append(
            {
                "title": raw.get("title", ""),
                "company_name": raw.get("company_name", ""),
                "location": raw.get("location", ""),
                "via": raw.get("via", ""),
                "description": (raw.get("description", "") or "")[:500],
            }
        )
    return items
