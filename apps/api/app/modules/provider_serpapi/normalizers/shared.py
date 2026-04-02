from __future__ import annotations

import re
from urllib.parse import urlparse

from app.modules.provider_serpapi.schemas import LeadIdentityCandidate

_PHONE_RE = re.compile(r"[^\d+]+")


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
    if data_cid:
        identities.append(LeadIdentityCandidate(identity_type="data_cid", identity_value=data_cid))
    if data_id:
        identities.append(LeadIdentityCandidate(identity_type="data_id", identity_value=data_id))
    if place_id:
        identities.append(LeadIdentityCandidate(identity_type="place_id", identity_value=place_id))
    if website_domain:
        identities.append(LeadIdentityCandidate(identity_type="website_domain", identity_value=website_domain))
    if phone:
        identities.append(LeadIdentityCandidate(identity_type="phone", identity_value=phone))
    fingerprint = build_fingerprint(company_name=company_name, city=city, address=address, lat=lat, lng=lng)
    if fingerprint:
        identities.append(LeadIdentityCandidate(identity_type="fingerprint", identity_value=fingerprint))
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

