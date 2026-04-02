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


class MapsLocalNormalizer:
    def normalize(self, payload: dict[str, Any]) -> list[LeadCandidate]:
        local_results = payload.get("local_results")
        if not isinstance(local_results, list):
            return []
        candidates: list[LeadCandidate] = []
        for item in local_results:
            if not isinstance(item, dict):
                continue
            title = item.get("title") or item.get("name")
            if not isinstance(title, str) or not title.strip():
                continue
            address = item.get("address") if isinstance(item.get("address"), str) else None
            phone = normalize_phone(item.get("phone")) if item.get("phone") else None
            website = item.get("website") if isinstance(item.get("website"), str) else None
            domain = compute_domain(website)
            rating = item.get("rating") if isinstance(item.get("rating"), (int, float)) else None
            reviews = item.get("reviews") if isinstance(item.get("reviews"), int) else 0
            gps = item.get("gps_coordinates") if isinstance(item.get("gps_coordinates"), dict) else {}
            lat = gps.get("latitude") if isinstance(gps.get("latitude"), (int, float)) else None
            lng = gps.get("longitude") if isinstance(gps.get("longitude"), (int, float)) else None

            data_id = item.get("data_id") if isinstance(item.get("data_id"), str) else None
            data_cid = item.get("data_cid") if isinstance(item.get("data_cid"), str) else None
            place_id = item.get("place_id") if isinstance(item.get("place_id"), str) else None
            city = item.get("city") if isinstance(item.get("city"), str) else guess_city_from_address(address)
            category = item.get("type") if isinstance(item.get("type"), str) else None

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

            candidates.append(
                LeadCandidate(
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
                    facts=item,
                    identities=[LeadIdentityCandidate.model_validate(identity) for identity in identities],
                )
            )
        return candidates

