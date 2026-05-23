from __future__ import annotations

import json
import logging

import httpx
from pydantic import ValidationError as PydanticValidationError

from app.core.config import get_settings
from app.core.errors import ServiceUnavailableError
from app.modules.search_jobs.schemas import SearchJobCreateRequest

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You extract structured search parameters from a natural language query "
    "about local business lead discovery. Be conservative: only extract what "
    "the user explicitly stated. Use null for optional fields not mentioned. "
    "Default max_results to 25 if the user does not specify a number of results."
)


def _search_params_schema() -> dict:
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
        settings = get_settings()
        if not settings.has_openai_configured:
            raise ServiceUnavailableError(
                "Smart search requires OpenAI to be configured. Set OPENAI_API_KEY in your environment."
            )

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
