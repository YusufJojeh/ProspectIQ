from __future__ import annotations

from typing import Any, cast

from app.modules.provider_serpapi.normalizers.shared import (
    compute_completeness,
    compute_domain,
    compute_identities,
    compute_simple_confidence,
    guess_city_from_address,
    is_preferred_business_domain,
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
        place_dict = cast(dict[str, Any], place)
        address = place.get("address") if isinstance(place.get("address"), str) else None
        phone = normalize_phone(place.get("phone")) if place.get("phone") else None
        raw_website = place.get("website") if isinstance(place.get("website"), str) else None
        raw_domain = compute_domain(raw_website)
        website = raw_website if is_preferred_business_domain(raw_domain) else None
        domain = raw_domain if website else None
        rating_value = place_dict.get("rating")
        rating: float | None = (
            float(rating_value) if isinstance(rating_value, (int, float)) else None
        )
        reviews_value = place_dict.get("reviews")
        reviews: int = reviews_value if isinstance(reviews_value, int) else 0
        gps_value = place_dict.get("gps_coordinates")
        gps: dict[str, Any] = cast(dict[str, Any], gps_value) if isinstance(gps_value, dict) else {}
        latitude_value = gps.get("latitude")
        longitude_value = gps.get("longitude")
        lat: float | None = (
            float(latitude_value) if isinstance(latitude_value, (int, float)) else None
        )
        lng: float | None = (
            float(longitude_value) if isinstance(longitude_value, (int, float)) else None
        )

        data_id = place.get("data_id") if isinstance(place.get("data_id"), str) else None
        data_cid = place.get("data_cid") if isinstance(place.get("data_cid"), str) else None
        place_id = place.get("place_id") if isinstance(place.get("place_id"), str) else None
        city = (
            place.get("city")
            if isinstance(place.get("city"), str)
            else guess_city_from_address(address)
        )
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
            facts=place_dict,
            identities=[LeadIdentityCandidate.model_validate(identity) for identity in identities],
        )
