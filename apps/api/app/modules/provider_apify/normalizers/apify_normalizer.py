from __future__ import annotations

import re
from typing import Any

from app.modules.provider_serpapi.normalizers.shared import (
    clean_optional_text,
    compute_completeness,
    compute_domain,
    normalize_phone,
)

_PHONE_HINT_RE = re.compile(r"(\+?\d[\d\s().-]{7,}\d)")
_TEXT_FIELDS = ("text", "markdown", "description", "title")


class ApifyCrawlNormalizer:
    """Turns Apify Actor dataset items into curated facts.

    Dataset item shapes vary per Actor (a website-content-crawler item looks
    nothing like a reviews-crawler item), so every field is read
    defensively. Nothing here is fabricated when a field is absent -- it is
    simply left out of the resulting fact, matching how the SerpAPI/Tavily
    normalizers already behave.
    """

    def normalize(
        self, payload: dict[str, Any], *, actor_key: str, fallback_company_name: str
    ) -> list[dict[str, Any]]:
        items = payload.get("items")
        if not isinstance(items, list):
            return []

        results: list[dict[str, Any]] = []
        for raw_item in items:
            if not isinstance(raw_item, dict):
                continue
            fact = self._normalize_item(
                raw_item, actor_key=actor_key, fallback_company_name=fallback_company_name
            )
            if fact is not None:
                results.append(fact)
        return results

    def _normalize_item(
        self, item: dict[str, Any], *, actor_key: str, fallback_company_name: str
    ) -> dict[str, Any] | None:
        url = clean_optional_text(item.get("url") or item.get("startUrl"), max_length=512)
        domain = compute_domain(url)
        text_blob = " ".join(
            value.strip()
            for key in _TEXT_FIELDS
            if isinstance(value := item.get(key), str) and value.strip()
        )
        phone = normalize_phone(item.get("phone")) or self._phone_from_text(text_blob)
        category = clean_optional_text(item.get("category"), max_length=255)
        company_name = (
            clean_optional_text(item.get("title") or item.get("companyName"), max_length=255)
            or fallback_company_name
        )
        if not url and not phone and not text_blob:
            return None

        completeness = compute_completeness(
            address=None,
            phone=phone,
            website_domain=domain,
            rating=None,
            review_count=0,
            lat=None,
            lng=None,
            category=category,
        )
        return {
            "company_name": company_name,
            "category": category,
            "website_url": url,
            "website_domain": domain,
            "phone": phone,
            "completeness": completeness,
            "confidence": 0.65 if (phone or category) else 0.45,
            "facts": {
                "provider": "apify",
                "provider_shape": f"apify:{actor_key}",
                "source": "apify",
                "actor_key": actor_key,
                "evidence": {
                    "url": url,
                    "snippet": clean_optional_text(text_blob, max_length=600),
                    "provider": "apify",
                },
                "provider_fields_present": sorted(item.keys()),
                **self._business_evidence(item, actor_key=actor_key, text_blob=text_blob),
            },
        }

    def _business_evidence(
        self, item: dict[str, Any], *, actor_key: str, text_blob: str
    ) -> dict[str, Any]:
        """Retain bounded normalized evidence, never the actor's raw item."""
        evidence: dict[str, Any] = {}
        for key in (
            "online_booking",
            "has_ecommerce",
            "has_whatsapp",
            "mobile_responsive",
            "hiring",
        ):
            if isinstance(item.get(key), bool):
                evidence[key] = item[key]
        for key in ("branch_count", "location_count", "roles_count"):
            value = item.get(key)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                evidence[key] = value
        for key in (
            "services",
            "service_names",
            "social_links",
            "social_urls",
            "contact_channels",
            "open_roles",
            "jobs",
        ):
            values = item.get(key)
            if isinstance(values, list):
                evidence[key] = [
                    value.strip()[:255]
                    for value in values[:100]
                    if isinstance(value, str) and value.strip()
                ]
        social_presence = item.get("social_presence")
        if isinstance(social_presence, dict):
            evidence["social_presence"] = {
                key: value
                for key, value in social_presence.items()
                if key in {"instagram", "facebook", "linkedin"} and isinstance(value, bool)
            }
        reviews = item.get("reviews") or item.get("review_texts")
        if isinstance(reviews, list):
            evidence["reviews"] = self._review_texts(reviews)
        elif actor_key == "reviews_crawler" and text_blob:
            evidence["reviews"] = [text_blob[:600]]
        return evidence

    def _review_texts(self, reviews: list[Any]) -> list[str]:
        normalized: list[str] = []
        for review in reviews[:100]:
            value = review.get("text") if isinstance(review, dict) else review
            if isinstance(value, str) and value.strip():
                normalized.append(value.strip()[:600])
        return normalized

    def _phone_from_text(self, text: str) -> str | None:
        match = _PHONE_HINT_RE.search(text)
        return normalize_phone(match.group(1)) if match else None
