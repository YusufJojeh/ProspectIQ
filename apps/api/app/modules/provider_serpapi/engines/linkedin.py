from __future__ import annotations

from typing import Any

from app.modules.provider_serpapi.client import ProviderCallResult, SerpApiClient

_MAX_QUERY_LENGTH = 220
_MAX_RESULTS = 10
_COMPANY_MARKER = "linkedin.com/company/"


def _clean_query(value: str) -> str:
    return " ".join(value.split()).strip()[:_MAX_QUERY_LENGTH]


def build_linkedin_company_params(
    *,
    company_name: str,
    city: str | None = None,
    hl: str = "en",
    gl: str = "us",
) -> dict[str, Any]:
    name = company_name.strip()
    if not name:
        raise ValueError("SerpAPI LinkedIn lookup requires a company name.")
    location = f" {city.strip()}" if city and city.strip() else ""
    query = _clean_query(f'site:linkedin.com/company "{name}"{location}')
    return {
        "engine": "google",
        "q": query,
        "hl": hl,
        "gl": gl,
        "num": _MAX_RESULTS,
    }


def run_linkedin_company(client: SerpApiClient, *, params: dict[str, Any]) -> ProviderCallResult:
    return client.search(params)


def extract_company_url(result: ProviderCallResult) -> str | None:
    """Return the first LinkedIn company URL from organic results, if any."""
    if not result.ok or not result.payload:
        return None
    organic = result.payload.get("organic_results", [])
    if not isinstance(organic, list):
        return None
    for raw in organic:
        if not isinstance(raw, dict):
            continue
        link = raw.get("link")
        if isinstance(link, str) and _COMPANY_MARKER in link.lower():
            return link
    return None
