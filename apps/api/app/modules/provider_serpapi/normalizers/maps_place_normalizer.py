from __future__ import annotations

from typing import Any

from app.modules.provider_serpapi.normalizers.shared import (
    compute_completeness,
    compute_domain,
    compute_identities,
    compute_simple_confidence,
    guess_city_from_address,
    normalize_phone,
)
from app.modules.provider_serpapi.schemas import LeadCandidate, LeadIdentityCandidate


class MapsPlaceNormalizer:
    def normalize(self, payload: dict[str, Any]) -> LeadCandidate | None:
        place = payload.get("place_results")
        if not isinstance(place, dict):
            return None
        title = place.get("title") or place.get("name")
        if not isinstance(title, str) or not title.strip():
            return None
        address = place.get("address") if isinstance(place.get("address"), str) else None
        phone = normalize_phone(place.get("phone")) if place.get("phone") else None
        website = place.get("website") if isinstance(place.get("website"), str) else None
        domain = compute_domain(website)
        rating = place.get("rating") if isinstance(place.get("rating"), (int, float)) else None
        reviews = place.get("reviews") if isinstance(place.get("reviews"), int) else 0
        gps = place.get("gps_coordinates") if isinstance(place.get("gps_coordinates"), dict) else {}
        lat = gps.get("latitude") if isinstance(gps.get("latitude"), (int, float)) else None
        lng = gps.get("longitude") if isinstance(gps.get("longitude"), (int, float)) else None

        data_id = place.get("data_id") if isinstance(place.get("data_id"), str) else None
        data_cid = place.get("data_cid") if isinstance(place.get("data_cid"), str) else None
        place_id = place.get("place_id") if isinstance(place.get("place_id"), str) else None
        city = place.get("city") if isinstance(place.get("city"), str) else guess_city_from_address(address)
        category = place.get("type") if isinstance(place.get("type"), str) else None

        identities = compute_identities(
            data_cid=data_cid,
            data_id=data_id,
            place_id=place_id,
            website_domain=domain,
            phone=phone,
            company_name=title,
            city=city,
            address=address,
            lat=lat,
            lng=lng,
        )
        completeness = compute_completeness(
            address=address,
            phone=phone,
            website_domain=domain,
            rating=rating,
            review_count=reviews,
            lat=lat,
            lng=lng,
            category=category,
        )
        confidence = compute_simple_confidence(
            data_cid=data_cid,
            data_id=data_id,
            place_id=place_id,
            completeness=completeness,
        )
        return LeadCandidate(
            data_cid=data_cid,
            data_id=data_id,
            place_id=place_id,
            company_name=title.strip(),
            category=category,
            address=address,
            city=city,
            phone=phone,
            website_url=website,
            website_domain=domain,
            rating=rating,
            review_count=reviews,
            lat=lat,
            lng=lng,
            confidence=confidence,
            completeness=completeness,
            facts=place,
            identities=[LeadIdentityCandidate.model_validate(identity) for identity in identities],
        )

