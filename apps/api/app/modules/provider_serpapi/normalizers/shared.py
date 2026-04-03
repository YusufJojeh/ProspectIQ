from __future__ import annotations

import re
from urllib.parse import urlparse

from app.modules.provider_serpapi.schemas import LeadIdentityCandidate

_PHONE_RE = re.compile(r"[^\d+]+")
_NON_BUSINESS_DOMAIN_SUFFIXES = (
    "google.com",
    "g.page",
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "x.com",
    "twitter.com",
    "yelp.com",
    "tripadvisor.com",
    "foursquare.com",
    "yellowpages.com",
    "mapquest.com",
    "nicelocal.com",
)


def normalize_phone(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = _PHONE_RE.sub("", value).strip()
    return cleaned or None


def compute_domain(url: str | None) -> str | None:
    if not url:
        return None
    try:
        parsed = urlparse(url)
        host = parsed.netloc or parsed.path
        host = host.lower()
        if host.startswith("www."):
            host = host[4:]
        return host or None
    except Exception:
        return None


def is_preferred_business_domain(domain: str | None) -> bool:
    if not domain:
        return False
    normalized = domain.lower().strip(".")
    return not any(
        normalized == blocked or normalized.endswith(f".{blocked}")
        for blocked in _NON_BUSINESS_DOMAIN_SUFFIXES
    )


def guess_city_from_address(address: str | None) -> str | None:
    if not address:
        return None
    parts = [part.strip() for part in address.split(",") if part.strip()]
    if len(parts) >= 2:
        return parts[-2]
    return None


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def build_fingerprint(
    *,
    company_name: str | None,
    city: str | None,
    address: str | None,
    lat: float | None,
    lng: float | None,
) -> str | None:
    if not company_name:
        return None
    normalized_name = normalize_text(company_name)
    normalized_city = normalize_text(city or "")
    if lat is not None and lng is not None:
        return f"{normalized_name}|{normalized_city}|{round(lat, 5)}|{round(lng, 5)}"
    if address:
        return f"{normalized_name}|{normalized_city}|{normalize_text(address)[:64]}"
    return f"{normalized_name}|{normalized_city}"


def compute_identities(
    *,
    data_cid: str | None,
    data_id: str | None,
    place_id: str | None,
    website_domain: str | None,
    phone: str | None,
    company_name: str | None,
    city: str | None,
    address: str | None,
    lat: float | None,
    lng: float | None,
) -> list[LeadIdentityCandidate]:
    identities: list[LeadIdentityCandidate] = []
    seen: set[tuple[str, str]] = set()

    def add_identity(identity_type: str, identity_value: str | None) -> None:
        if not identity_value:
            return
        key = (identity_type, identity_value)
        if key in seen:
            return
        seen.add(key)
        identities.append(
            LeadIdentityCandidate(identity_type=identity_type, identity_value=identity_value)
        )

    if data_cid:
        add_identity("data_cid", data_cid)
    if data_id:
        add_identity("data_id", data_id)
    if place_id:
        add_identity("place_id", place_id)
    if is_preferred_business_domain(website_domain):
        add_identity("website_domain", website_domain)
    if phone:
        add_identity("phone", phone)
    fingerprint = build_fingerprint(
        company_name=company_name, city=city, address=address, lat=lat, lng=lng
    )
    if fingerprint:
        add_identity("fingerprint", fingerprint)
    return identities


def compute_completeness(
    *,
    address: str | None,
    phone: str | None,
    website_domain: str | None,
    rating: float | None,
    review_count: int,
    lat: float | None,
    lng: float | None,
    category: str | None,
) -> float:
    fields = [
        bool(address),
        bool(phone),
        bool(website_domain),
        rating is not None,
        bool(review_count),
        lat is not None and lng is not None,
        bool(category),
    ]
    return round(sum(1 for item in fields if item) / len(fields), 3)


def compute_simple_confidence(
    *,
    data_cid: str | None,
    data_id: str | None,
    place_id: str | None,
    completeness: float,
) -> float:
    base = 0.35 + completeness * 0.45
    if data_cid or data_id or place_id:
        base += 0.15
    return round(min(1.0, base), 3)
