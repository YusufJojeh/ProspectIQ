from __future__ import annotations

from typing import Any, cast

from app.modules.provider_serpapi.normalizers.shared import (
    clean_optional_text,
    coerce_float,
    coerce_int,
    compute_completeness,
    compute_domain,
    compute_identities,
    compute_simple_confidence,
    curated_maps_search_facts,
    extract_coordinates,
    guess_city_from_address,
    is_preferred_business_domain,
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
            item_dict = cast(dict[str, Any], item)
            title = item.get("title") or item.get("name")
            if not isinstance(title, str) or not title.strip():
                continue
            address = clean_optional_text(item.get("address"), max_length=512)
            phone = normalize_phone(item.get("phone")) if item.get("phone") else None
            raw_website = clean_optional_text(item.get("website"), max_length=512)
            raw_domain = compute_domain(raw_website)
            website = raw_website if is_preferred_business_domain(raw_domain) else None
            domain = raw_domain if website else None
            rating = coerce_float(item_dict.get("rating"))
            reviews = max(0, coerce_int(item_dict.get("reviews"), default=0))
            lat, lng = extract_coordinates(item_dict.get("gps_coordinates"))

            data_id = clean_optional_text(item.get("data_id"), max_length=128)
            data_cid = clean_optional_text(item.get("data_cid"), max_length=128)
            place_id = clean_optional_text(item.get("place_id"), max_length=128)
            city = (
                clean_optional_text(item.get("city"), max_length=128)
                or guess_city_from_address(address)
            )
            category = clean_optional_text(item.get("type"), max_length=255)

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
                    facts=curated_maps_search_facts(
                        item_dict,
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
                    ),
                    identities=[
                        LeadIdentityCandidate.model_validate(identity) for identity in identities
                    ],
                )
            )
        return candidates
