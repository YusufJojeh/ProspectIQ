from __future__ import annotations

from typing import Any

from app.modules.provider_serpapi.client import ProviderCallResult, SerpApiClient

_MAX_REVIEWS = 20


def build_google_maps_reviews_params(
    *,
    data_id: str | None = None,
    place_id: str | None = None,
    hl: str = "en",
) -> dict[str, Any]:
    if not data_id and not place_id:
        raise ValueError("google_maps_reviews requires a data_id or place_id.")
    params: dict[str, Any] = {"engine": "google_maps_reviews", "hl": hl}
    if data_id:
        params["data_id"] = data_id
    if place_id:
        params["place_id"] = place_id
    return params


def run_google_maps_reviews(client: SerpApiClient, *, params: dict[str, Any]) -> ProviderCallResult:
    return client.search(params)


def extract_reviews(
    result: ProviderCallResult, *, max_items: int = _MAX_REVIEWS
) -> list[dict[str, Any]]:
    """Flatten the `reviews` array into { rating, snippet } dicts."""
    if not result.ok or not result.payload:
        return []
    raw_reviews = result.payload.get("reviews", [])
    if not isinstance(raw_reviews, list):
        return []
    items: list[dict[str, Any]] = []
    for raw in raw_reviews[:max_items]:
        if not isinstance(raw, dict):
            continue
        items.append(
            {
                "rating": raw.get("rating"),
                "snippet": raw.get("snippet") or raw.get("text") or "",
            }
        )
    return items


def extract_place_summary(result: ProviderCallResult) -> dict[str, Any]:
    """Pull aggregate rating + review_count from the `place_info` block."""
    if not result.ok or not result.payload:
        return {}
    place_info = result.payload.get("place_info")
    if not isinstance(place_info, dict):
        return {}
    summary: dict[str, Any] = {}
    rating = place_info.get("rating")
    if isinstance(rating, int | float):
        summary["rating"] = float(rating)
    reviews = place_info.get("reviews")
    if isinstance(reviews, int):
        summary["review_count"] = reviews
    return summary
