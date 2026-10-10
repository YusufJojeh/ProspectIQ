from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from app.modules.provider_serpapi.models import ProviderNormalizedFact

BUSINESS_CLAIM_GROUPS: dict[str, str] = {
    "online_booking": "digital_presence",
    "branch_count": "business_identity",
    "services": "business_intelligence",
    "social_presence": "digital_presence",
    "contact_channels": "contactability",
    "has_ecommerce": "digital_presence",
    "has_whatsapp": "contactability",
    "review_sentiment": "reviews",
    "recurring_review_pain_points": "reviews",
    "hiring_signal": "growth_signals",
    "digital_maturity": "digital_presence",
}

_BOOKING_RE = re.compile(
    r"(?:book(?:ing)?|appointment|schedule)(?:\s+(?:now|online|an appointment))?|"
    r"(?:calendly\.com|acuityscheduling\.com|setmore\.com|booksy\.com|fresha\.com)",
    re.IGNORECASE,
)
_ECOMMERCE_RE = re.compile(
    r"(?:/shop(?:/|\b)|/cart(?:/|\b)|/checkout(?:/|\b)|add to cart|buy now|online store)",
    re.IGNORECASE,
)
_WHATSAPP_RE = re.compile(r"(?:wa\.me/|api\.whatsapp\.com/|whatsapp)", re.IGNORECASE)
_HIRING_RE = re.compile(
    r"(?:/careers?(?:/|\b)|/jobs?(?:/|\b)|we(?:'re| are) hiring|open positions?|join our team)",
    re.IGNORECASE,
)
_BRANCH_RE = re.compile(r"\b(\d{1,4})\s+(?:branches|locations|offices|stores)\b", re.IGNORECASE)
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_CONTACT_FORM_RE = re.compile(r"(?:contact form|/contact(?:/|\b)|contact us)", re.IGNORECASE)
_POSITIVE_WORDS = {"excellent", "great", "friendly", "helpful", "professional", "recommend", "fast", "amazing"}
_NEGATIVE_WORDS = {"bad", "poor", "rude", "slow", "delay", "expensive", "overpriced", "wait", "unresponsive"}
_PAIN_PATTERNS: dict[str, re.Pattern[str]] = {
    "slow response": re.compile(r"slow (?:response|reply)|unresponsive|no response", re.IGNORECASE),
    "pricing complaints": re.compile(r"expensive|overpriced|pricing|hidden (?:fee|cost)", re.IGNORECASE),
    "waiting time": re.compile(r"long wait|waiting time|waited", re.IGNORECASE),
    "delivery delay": re.compile(r"late delivery|delivery delay|delayed (?:order|delivery)", re.IGNORECASE),
}
_SOCIAL_DOMAINS = {
    "instagram": "instagram.com",
    "facebook": "facebook.com",
    "linkedin": "linkedin.com",
}


@dataclass(frozen=True)
class ClaimObservation:
    fact: ProviderNormalizedFact
    value: str


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


class BusinessIntelligenceProjector:
    """Projects explicit provider evidence into deterministic business claims."""

    def project(
        self, facts: list[ProviderNormalizedFact]
    ) -> dict[str, list[ClaimObservation]]:
        projected: dict[str, list[ClaimObservation]] = {
            claim_type: [] for claim_type in BUSINESS_CLAIM_GROUPS if claim_type != "digital_maturity"
        }
        review_evidence: list[tuple[ProviderNormalizedFact, str]] = []
        for fact in facts:
            text = self._evidence_text(fact)
            structured = fact.facts_json or {}
            self._append_boolean(projected["online_booking"], fact, structured, "online_booking")
            if not self._has_key(structured, "online_booking") and _BOOKING_RE.search(text):
                projected["online_booking"].append(ClaimObservation(fact, "true"))

            branch_count = self._branch_count(structured, text)
            if branch_count is not None:
                projected["branch_count"].append(ClaimObservation(fact, str(branch_count)))

            services = self._string_list(structured, "services", "service_names")
            if services:
                projected["services"].append(ClaimObservation(fact, canonical_json(services)))

            social = self._social_presence(structured, text)
            if social:
                projected["social_presence"].append(ClaimObservation(fact, canonical_json(social)))

            channels = self._contact_channels(fact, structured, text, social)
            if channels:
                projected["contact_channels"].append(ClaimObservation(fact, canonical_json(channels)))

            self._append_boolean(projected["has_ecommerce"], fact, structured, "has_ecommerce")
            if not self._has_key(structured, "has_ecommerce") and _ECOMMERCE_RE.search(text):
                projected["has_ecommerce"].append(ClaimObservation(fact, "true"))

            self._append_boolean(projected["has_whatsapp"], fact, structured, "has_whatsapp")
            if not self._has_key(structured, "has_whatsapp") and _WHATSAPP_RE.search(text):
                projected["has_whatsapp"].append(ClaimObservation(fact, "true"))

            reviews = self._review_texts(structured)
            review_evidence.extend((fact, review) for review in reviews)

            hiring = self._hiring_signal(structured, text)
            if hiring is not None:
                projected["hiring_signal"].append(ClaimObservation(fact, canonical_json(hiring)))
        review_texts = [review for _, review in review_evidence]
        sentiment = self._review_sentiment(review_texts)
        if sentiment is not None:
            for fact in dict.fromkeys(fact for fact, _ in review_evidence):
                projected["review_sentiment"].append(ClaimObservation(fact, sentiment))
        pain_points = self._pain_points(
            review_texts,
            sorted(
                {
                    source_url
                    for fact, _ in review_evidence
                    if (source_url := self._source_url(fact)) is not None
                }
            ),
        )
        if pain_points and review_evidence:
            projected["recurring_review_pain_points"].append(
                ClaimObservation(review_evidence[0][0], canonical_json(pain_points))
            )
        return projected

    def _append_boolean(
        self,
        target: list[ClaimObservation],
        fact: ProviderNormalizedFact,
        values: dict[str, Any],
        key: str,
    ) -> None:
        value = values.get(key)
        if isinstance(value, bool):
            target.append(ClaimObservation(fact, str(value).lower()))

    def _has_key(self, values: dict[str, Any], key: str) -> bool:
        return isinstance(values.get(key), bool)

    def _evidence_text(self, fact: ProviderNormalizedFact) -> str:
        text_values: list[str] = [fact.website_url or ""]
        structured = fact.facts_json or {}
        evidence = structured.get("evidence")
        if isinstance(evidence, dict):
            text_values.extend(str(evidence.get(key) or "") for key in ("url", "snippet"))
        for key in ("url", "link", "snippet", "content", "extracted_content", "text", "markdown"):
            value = structured.get(key)
            if isinstance(value, str):
                text_values.append(value)
        return " ".join(text_values)

    def _branch_count(self, values: dict[str, Any], text: str) -> int | None:
        for key in ("branch_count", "location_count", "locations_count"):
            value = values.get(key)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                return value
        locations = values.get("locations")
        if isinstance(locations, list):
            return len(locations)
        match = _BRANCH_RE.search(text)
        return int(match.group(1)) if match else None

    def _string_list(self, values: dict[str, Any], *keys: str) -> list[str]:
        found: dict[str, str] = {}
        for key in keys:
            raw = values.get(key)
            candidates = raw if isinstance(raw, list) else []
            for item in candidates:
                if isinstance(item, str) and item.strip():
                    found.setdefault(item.strip().casefold(), item.strip())
        return sorted(found.values(), key=str.casefold)

    def _social_presence(self, values: dict[str, Any], text: str) -> dict[str, bool]:
        result: dict[str, bool] = {}
        raw = values.get("social_presence")
        if isinstance(raw, dict):
            for network in _SOCIAL_DOMAINS:
                if isinstance(raw.get(network), bool):
                    result[network] = raw[network]
        social_urls = self._string_list(values, "social_urls", "social_links")
        haystack = " ".join([text, *social_urls]).casefold()
        for network, domain in _SOCIAL_DOMAINS.items():
            if domain in haystack:
                result[network] = True
        return dict(sorted(result.items()))

    def _contact_channels(
        self,
        fact: ProviderNormalizedFact,
        values: dict[str, Any],
        text: str,
        social: dict[str, bool],
    ) -> list[str]:
        channels = set(self._string_list(values, "contact_channels"))
        allowed = {"phone", "email", "whatsapp", "instagram", "facebook", "linkedin", "contact_form", "online_booking"}
        channels.intersection_update(allowed)
        if fact.phone:
            channels.add("phone")
        if _EMAIL_RE.search(text) or isinstance(values.get("email"), str):
            channels.add("email")
        if _WHATSAPP_RE.search(text):
            channels.add("whatsapp")
        if values.get("has_whatsapp") is True:
            channels.add("whatsapp")
        if _CONTACT_FORM_RE.search(text):
            channels.add("contact_form")
        if _BOOKING_RE.search(text):
            channels.add("online_booking")
        if values.get("online_booking") is True:
            channels.add("online_booking")
        channels.update(network for network, present in social.items() if present)
        return sorted(channels)

    def _review_texts(self, values: dict[str, Any]) -> list[str]:
        reviews: list[str] = []
        for key in ("reviews", "review_texts"):
            raw = values.get(key)
            if not isinstance(raw, list):
                continue
            for item in raw:
                text = item.get("text") if isinstance(item, dict) else item
                if isinstance(text, str) and text.strip():
                    reviews.append(text.strip())
        return reviews

    def _review_sentiment(self, reviews: list[str]) -> str | None:
        if len(reviews) < 3:
            return None
        score = 0
        for review in reviews:
            words = set(re.findall(r"[a-z]+", review.casefold()))
            score += len(words & _POSITIVE_WORDS) - len(words & _NEGATIVE_WORDS)
        if score > 0:
            return "positive"
        if score < 0:
            return "negative"
        return "mixed"

    def _pain_points(
        self, reviews: list[str], source_urls: list[str]
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for category, pattern in _PAIN_PATTERNS.items():
            count = sum(bool(pattern.search(review)) for review in reviews)
            if count >= 2:
                result.append(
                    {"category": category, "count": count, "source_references": source_urls}
                )
        return result

    def _hiring_signal(self, values: dict[str, Any], text: str) -> dict[str, Any] | None:
        active = values.get("hiring")
        roles = self._string_list(values, "open_roles", "jobs", "roles")
        roles_count = values.get("roles_count")
        if not isinstance(roles_count, int) or isinstance(roles_count, bool):
            roles_count = len(roles)
        if isinstance(active, bool) or roles_count > 0 or _HIRING_RE.search(text):
            return {"active": bool(active is True or roles_count > 0 or _HIRING_RE.search(text)), "roles_count": max(0, roles_count)}
        return None

    def _source_url(self, fact: ProviderNormalizedFact) -> str | None:
        evidence = (fact.facts_json or {}).get("evidence")
        evidence_url = evidence.get("url") if isinstance(evidence, dict) else None
        if isinstance(evidence_url, str):
            return evidence_url
        return fact.website_url
