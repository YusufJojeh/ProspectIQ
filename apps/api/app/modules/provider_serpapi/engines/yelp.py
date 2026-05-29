from __future__ import annotations

from typing import Any

from app.modules.provider_serpapi.client import ProviderCallResult, SerpApiClient

_MAX_RESULTS = 20


def build_yelp_params(
    *,
    find_desc: str,
    find_loc: str,
) -> dict[str, Any]:
    desc = " ".join(find_desc.split()).strip()
    loc = " ".join(find_loc.split()).strip()
    if not desc:
        raise ValueError("Yelp search requires a non-empty find_desc.")
    params: dict[str, Any] = {"engine": "yelp", "find_desc": desc}
    if loc:
        params["find_loc"] = loc
    return params


def run_yelp(client: SerpApiClient, *, params: dict[str, Any]) -> ProviderCallResult:
    return client.search(params)


def extract_businesses(
    result: ProviderCallResult, *, max_items: int = _MAX_RESULTS
) -> list[dict[str, Any]]:
    """Flatten the `organic_results` array into matchable business dicts."""
    if not result.ok or not result.payload:
        return []
    raw_results = result.payload.get("organic_results", [])
    if not isinstance(raw_results, list):
        return []
    items: list[dict[str, Any]] = []
    for raw in raw_results[:max_items]:
        if not isinstance(raw, dict):
            continue
        items.append(
            {
                "name": raw.get("title") or raw.get("name") or "",
                "phone": raw.get("phone") or "",
                "rating": raw.get("rating"),
                "review_count": raw.get("reviews"),
                "url": raw.get("link") or raw.get("link_text") or "",
            }
        )
    return items
