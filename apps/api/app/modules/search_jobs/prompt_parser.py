from __future__ import annotations

import json
import logging
import re

import httpx
from pydantic import ValidationError as PydanticValidationError

from app.core.config import get_settings
from app.core.errors import ServiceUnavailableError
from app.modules.search_jobs.schemas import SearchJobCreateRequest
from app.shared.enums.jobs import WebsitePreference

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You extract structured search parameters from a natural language query "
    "about local business lead discovery. Be conservative: only extract what "
    "the user explicitly stated. Use null for optional fields not mentioned. "
    "Default max_results to 25 if the user does not specify a number of results."
)


def _search_params_schema() -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "business_type",
            "city",
            "region",
            "radius_km",
            "max_results",
            "min_rating",
            "max_rating",
            "min_reviews",
            "max_reviews",
            "website_preference",
            "keyword_filter",
        ],
        "properties": {
            "business_type": {"type": "string"},
            "city": {"type": "string"},
            "region": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "radius_km": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
            "max_results": {"type": "integer"},
            "min_rating": {"anyOf": [{"type": "number"}, {"type": "null"}]},
            "max_rating": {"anyOf": [{"type": "number"}, {"type": "null"}]},
            "min_reviews": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
            "max_reviews": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
            "website_preference": {
                "type": "string",
                "enum": ["any", "must_have", "must_be_missing"],
            },
            "keyword_filter": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        },
    }


class SearchPromptParser:
    async def parse(self, prompt: str) -> SearchJobCreateRequest:
        local_parse = _parse_prompt_locally(prompt)
        settings = get_settings()
        if not settings.has_openai_configured:
            if local_parse is not None:
                return local_parse
            raise ServiceUnavailableError(_LOCAL_PARSE_ERROR)

        try:
            return await self._parse_with_openai(prompt)
        except ServiceUnavailableError:
            if local_parse is not None:
                logger.info("search_prompt_parser.fell_back_to_local_parser")
                return local_parse
            raise

    async def _parse_with_openai(self, prompt: str) -> SearchJobCreateRequest:
        settings = get_settings()
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
            ) as client:
                response = await client.post(
                    f"{settings.openai_base_url.rstrip('/')}/chat/completions",
                    json={
                        "model": settings.openai_model,
                        "messages": [
                            {"role": "system", "content": _SYSTEM_PROMPT},
                            {"role": "user", "content": prompt},
                        ],
                        "response_format": {
                            "type": "json_schema",
                            "json_schema": {
                                "name": "search_params",
                                "strict": True,
                                "schema": _search_params_schema(),
                            },
                        },
                    },
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "search_prompt_parser.openai_http_error status=%s body=%s",
                exc.response.status_code,
                exc.response.text[:200],
            )
            raise ServiceUnavailableError(
                "OpenAI returned an error while parsing the search prompt."
            ) from exc
        except httpx.RequestError as exc:
            raise ServiceUnavailableError(
                "Could not reach OpenAI to parse the search prompt."
            ) from exc

        payload = response.json()
        try:
            raw = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ServiceUnavailableError(
                "OpenAI response was missing the expected message content."
            ) from exc

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ServiceUnavailableError(
                "OpenAI returned non-JSON content for the search prompt."
            ) from exc

        try:
            return SearchJobCreateRequest(**parsed)
        except PydanticValidationError as exc:
            raise ServiceUnavailableError(
                f"AI-extracted parameters failed validation: {exc}"
            ) from exc


_LOCAL_PARSE_ERROR = (
    "Smart search could not understand the prompt. Include a business type and city, "
    "or configure OpenAI for richer natural-language parsing."
)


_LEADING_VERBS_RE = re.compile(
    (
        r"^(?:find|search\s+for|show\s+me|get|discover|look\s+for|list|"
        r"\u0627\u0628\u062d\u062b\s+\u0639\u0646|"
        r"\u0627\u0639\u062b\u0631\s+\u0639\u0644\u0649|"
        r"\u0627\u0639\u0631\u0636|"
        r"\u062c\u062f)\s+"
    ),
    re.IGNORECASE,
)
_BUSINESS_PLACE_RE = re.compile(
    (
        r"^(?P<business>.+?)\s+"
        r"(?:in|near|around|within|\u0641\u064a|\u0642\u0631\u0628|"
        r"\u062d\u0648\u0644|\u0636\u0645\u0646)\s+(?P<place>.+)$"
    ),
    re.IGNORECASE,
)
_PLACE_STOP_RE = re.compile(
    (
        r"\s+(?:with|who|that|having|where|which|and|but|radius|within|"
        r"\u0645\u0639|\u0628\u062f\u0648\u0646|\u0644\u062f\u064a\u0647\u0627|"
        r"\u0644\u062f\u064a\u0647|"
        # \u0628\u0639\u062f\u062f (with a count of) / \u0639\u062f\u062f (count)
        r"\u0628?\u0639\u062f\u062f|"
        # reviews root with optional and/with prefix: (\u0648)(\u0628)\u0645\u0631\u0627\u062c\u0639...
        r"\u0648?\u0628?\u0645\u0631\u0627\u062c\u0639\u0627?\u062a?|"
        # rating with optional and/with prefix: (\u0648)(\u0628)\u062a\u0642\u064a\u064a\u0645
        r"\u0648?\u0628?\u062a\u0642\u064a\u064a\u0645|"
        r"\u0636\u0645\u0646|\u0646\u0637\u0627\u0642)\s+|[,;]|\s+(?=\d)"
    ),
    re.IGNORECASE,
)
_BUSINESS_STOP_RE = re.compile(
    (
        r"\s+(?:with|who|that|having|where|which|"
        r"\u0645\u0639|\u0628\u062f\u0648\u0646|\u0644\u062f\u064a\u0647\u0627|"
        r"\u0644\u062f\u064a\u0647)\s+"
    ),
    re.IGNORECASE,
)


def _parse_prompt_locally(prompt: str) -> SearchJobCreateRequest | None:
    text = " ".join(prompt.strip().split())
    if not text:
        return None

    business_type, city, region = _extract_business_and_place(text)
    if business_type is None or city is None:
        return None

    try:
        return SearchJobCreateRequest(
            business_type=business_type,
            city=city,
            region=region,
            radius_km=_extract_int(text, _RADIUS_PATTERNS),
            max_results=_extract_int(text, _MAX_RESULTS_PATTERNS) or 25,
            min_rating=_extract_float(text, _MIN_RATING_PATTERNS),
            max_rating=_extract_float(text, _MAX_RATING_PATTERNS),
            min_reviews=_extract_int(text, _MIN_REVIEWS_PATTERNS),
            max_reviews=_extract_int(text, _MAX_REVIEWS_PATTERNS),
            website_preference=_extract_website_preference(text),
            keyword_filter=_extract_keyword_filter(text),
        )
    except PydanticValidationError:
        return None


def _extract_business_and_place(text: str) -> tuple[str | None, str | None, str | None]:
    normalized = _LEADING_VERBS_RE.sub("", text).strip()
    match = _BUSINESS_PLACE_RE.search(normalized)
    if not match:
        return None, None, None

    raw_business = _BUSINESS_STOP_RE.split(match.group("business"), maxsplit=1)[0]
    raw_place = _PLACE_STOP_RE.split(match.group("place"), maxsplit=1)[0]
    business_type = _clean_phrase(raw_business)
    place = _clean_phrase(raw_place)
    if business_type is None or place is None:
        return None, None, None

    if "," in place:
        city, region = [_clean_phrase(part) for part in place.split(",", maxsplit=1)]
        return business_type, city, region
    return business_type, place, None


def _clean_phrase(value: str) -> str | None:
    cleaned = value.strip(" .,:;\"'")
    cleaned = re.sub(r"\b(?:businesses|companies|leads)\b$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned if len(cleaned) >= 2 else None


_RADIUS_PATTERNS = (
    re.compile(r"(?:within|radius\s+of)\s+(\d{1,3})\s*(?:km|kilometers?)\b", re.IGNORECASE),
    re.compile(r"\b(\d{1,3})\s*(?:km|kilometers?)\s+radius\b", re.IGNORECASE),
    re.compile(r"(?:\u0636\u0645\u0646|\u0646\u0637\u0627\u0642)\s+(\d{1,3})\s*\u0643\u0645"),
)
_MAX_RESULTS_PATTERNS = (
    re.compile(r"\b(?:top|first|max(?:imum)?|limit(?:ed)?\s+to)\s+(\d{1,3})\b", re.IGNORECASE),
    re.compile(r"\b(\d{1,3})\s+(?:results|leads|businesses|companies)\b", re.IGNORECASE),
    re.compile(
        r"(?:\u0623\u0648\u0644|\u0623\u0641\u0636\u0644|\u062d\u062f\s+\u0623\u0642\u0635\u0649)\s+(\d{1,3})"
    ),
    re.compile(r"(\d{1,3})\s+(?:\u0646\u062a\u064a\u062c\u0629|\u0639\u0645\u064a\u0644)"),
)
_MIN_RATING_PATTERNS = (
    re.compile(r"\b(\d(?:\.\d)?)\s*\+\s*(?:stars?|rating)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:at\s+least|min(?:imum)?)\s+(\d(?:\.\d)?)\s*(?:stars?|rating)\b",
        re.IGNORECASE,
    ),
    # English "above/over/higher than 4 stars" (stars/rating keyword required to
    # avoid colliding with review-count phrases like "more than 50 reviews")
    re.compile(
        r"\b(?:above|over|higher\s+than|greater\s+than)\s+"
        r"(\d(?:\.\d)?)\s*(?:stars?|rating)\b",
        re.IGNORECASE,
    ),
    # Arabic "تقييم أعلى من 4" / "تقييم أكثر من 4" (rating higher than 4)
    re.compile(r"تقييم\s+(?:أعلى|أكثر)\s+من\s+(\d(?:\.\d)?)"),
    # Arabic "أعلى من 4 نجوم" (higher than 4 stars) — star/rating word required
    re.compile(
        r"(?:أعلى|أكثر)\s+من\s+(\d(?:\.\d)?)\s*"
        r"(?:نجوم|نجمة|نجمات|تقييم)"
    ),
    re.compile(
        r"(?:\u062a\u0642\u064a\u064a\u0645|"
        r"\u0628\u062a\u0642\u064a\u064a\u0645)\s+(\d(?:\.\d)?)\s*"
        r"(?:\+|\u0623\u0648\s+\u0623\u0643\u062b\u0631)?"
    ),
    re.compile(
        r"(\d(?:\.\d)?)\s*"
        r"(?:\u0646\u062c\u0648\u0645?|\u062a\u0642\u064a\u064a\u0645)\s*"
        r"(?:\+|\u0623\u0648\s+\u0623\u0643\u062b\u0631)"
    ),
)
_MAX_RATING_PATTERNS = (
    re.compile(
        r"\b(?:under|below|max(?:imum)?|up\s+to)\s+(\d(?:\.\d)?)\s*(?:stars?|rating)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:\u0623\u0642\u0644\s+\u0645\u0646|\u062d\u062f\s+\u0623\u0642\u0635\u0649)\s+"
        r"(\d(?:\.\d)?)\s*(?:\u0646\u062c\u0648\u0645?|\u062a\u0642\u064a\u064a\u0645)"
    ),
)
_MIN_REVIEWS_PATTERNS = (
    # English range: "between 20 and 150 reviews" / "20 to 150 reviews"
    re.compile(
        r"\b(?:between\s+)?(\d{1,6})\s*(?:and|to|-|–)\s*\d{1,6}\s+reviews?\b",
        re.IGNORECASE,
    ),
    # Arabic range: "(عدد) مراجعات بين 20 و150" -> min is the first number
    re.compile(
        r"(?:مراجع|عدد)\S*\s+"
        r"بين\s+(\d{1,6})\s*و\s*\d{1,6}"
    ),
    # Arabic range, number-first: "بين 20 و150 مراجعة"
    re.compile(
        r"بين\s+(\d{1,6})\s*و\s*\d{1,6}\s*"
        r"(?:مراجع|تقييم)"
    ),
    re.compile(r"\b(\d{1,6})\s*\+\s*reviews?\b", re.IGNORECASE),
    re.compile(r"\b(?:at\s+least|min(?:imum)?)\s+(\d{1,6})\s+reviews?\b", re.IGNORECASE),
    re.compile(r"(\d{1,6})\s*\+\s*(?:\u0645\u0631\u0627\u062c\u0639\u0629|\u062a\u0642\u064a\u064a\u0645)"),
    re.compile(
        r"(\d{1,6})\s*(?:\u0645\u0631\u0627\u062c\u0639\u0629|\u062a\u0642\u064a\u064a\u0645)\s*"
        r"(?:\u0623\u0648\s+\u0623\u0643\u062b\u0631|\u0639\u0644\u0649\s+\u0627\u0644\u0623\u0642\u0644)"
    ),
    re.compile(
        r"(?:\u0639\u0644\u0649\s+\u0627\u0644\u0623\u0642\u0644|"
        r"\u0644\u0627\s+\u064a\u0642\u0644\s+\u0639\u0646)\s+(\d{1,6})\s+"
        r"(?:\u0645\u0631\u0627\u062c\u0639\u0629|\u062a\u0642\u064a\u064a\u0645)"
    ),
)
_MAX_REVIEWS_PATTERNS = (
    # English range: "between 20 and 150 reviews" / "20 to 150 reviews" -> max is second number
    re.compile(
        r"\b(?:between\s+)?\d{1,6}\s*(?:and|to|-|–)\s*(\d{1,6})\s+reviews?\b",
        re.IGNORECASE,
    ),
    # Arabic range: "(عدد) مراجعات بين 20 و150" -> max is the second number
    re.compile(
        r"(?:مراجع|عدد)\S*\s+"
        r"بين\s+\d{1,6}\s*و\s*(\d{1,6})"
    ),
    # Arabic range, number-first: "بين 20 و150 مراجعة"
    re.compile(
        r"بين\s+\d{1,6}\s*و\s*(\d{1,6})\s*"
        r"(?:مراجع|تقييم)"
    ),
    re.compile(r"\b(?:under|below|max(?:imum)?|up\s+to)\s+(\d{1,6})\s+reviews?\b", re.IGNORECASE),
    re.compile(
        r"(?:\u0623\u0642\u0644\s+\u0645\u0646|\u062d\u062f\s+\u0623\u0642\u0635\u0649)\s+"
        r"(\d{1,6})\s+(?:\u0645\u0631\u0627\u062c\u0639\u0629|\u062a\u0642\u064a\u064a\u0645)"
    ),
)


def _extract_int(text: str, patterns: tuple[re.Pattern[str], ...]) -> int | None:
    value = _extract_number(text, patterns)
    return int(value) if value is not None else None


def _extract_float(text: str, patterns: tuple[re.Pattern[str], ...]) -> float | None:
    return _extract_number(text, patterns)


def _extract_number(text: str, patterns: tuple[re.Pattern[str], ...]) -> float | None:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return float(match.group(1))
    return None


def _extract_website_preference(text: str) -> WebsitePreference:
    lowered = text.lower()
    missing_website_phrases = (
        "no website",
        "without website",
        "missing website",
        "\u0628\u062f\u0648\u0646 \u0645\u0648\u0642\u0639",
        "\u0644\u0627 \u064a\u0645\u0644\u0643 \u0645\u0648\u0642\u0639",
        "\u0644\u064a\u0633 \u0644\u062f\u064a\u0647 \u0645\u0648\u0642\u0639",
        "\u0639\u062f\u0645 \u0648\u062c\u0648\u062f \u0645\u0648\u0642\u0639",
    )
    has_website_phrases = (
        "with website",
        "has website",
        "must have website",
        "\u0644\u062f\u064a\u0647 \u0645\u0648\u0642\u0639",
        "\u0644\u062f\u064a\u0647\u0627 \u0645\u0648\u0642\u0639",
        "\u0645\u0639 \u0645\u0648\u0642\u0639",
    )
    if any(phrase in lowered for phrase in missing_website_phrases):
        return WebsitePreference.MUST_BE_MISSING
    if any(phrase in lowered for phrase in has_website_phrases):
        return WebsitePreference.MUST_HAVE
    return WebsitePreference.ANY


def _extract_keyword_filter(text: str) -> str | None:
    patterns = (
        re.compile(r"\b(?:keyword|service|special(?:ty|izing\s+in))[:\s]+([^,;.]+)", re.IGNORECASE),
        re.compile(r"\b(?:for|about)\s+([^,;.]+)\s+(?:service|services|work)\b", re.IGNORECASE),
    )
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return _clean_phrase(match.group(1))
    return None
