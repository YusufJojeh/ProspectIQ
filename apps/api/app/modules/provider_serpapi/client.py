from __future__ import annotations

import hashlib
import json
import random
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.config import get_settings
from app.modules.provider_serpapi.exceptions import ProviderConfigError, RetryableProviderError


@dataclass(frozen=True)
class ProviderCallResult:
    ok: bool
    status_code: int | None
    payload: dict[str, Any] | None
    error_message: str | None
    serpapi_search_id: str | None
    started_at: datetime
    finished_at: datetime


def fingerprint_params(params: dict[str, Any]) -> str:
    canonical = json.dumps(params, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class SerpApiClient:
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.serpapi_api_key or settings.serpapi_api_key == "<replace-me>":
            raise ProviderConfigError("SERPAPI_API_KEY is not configured.")
        self.api_key = settings.serpapi_api_key
        self.base_url = settings.serpapi_base_url
        self._client = httpx.Client(
            timeout=httpx.Timeout(20.0, connect=10.0), headers={"Accept": "application/json"}
        )

    def search(self, params: dict[str, Any], *, max_attempts: int = 3) -> ProviderCallResult:
        last_error: str | None = None
        last_status: int | None = None

        for attempt in range(1, max_attempts + 1):
            attempt_started = datetime.now(tz=UTC)
            try:
                response = self._client.get(
                    self.base_url, params={"api_key": self.api_key, **params}
                )
                last_status = response.status_code
                serpapi_search_id = None
                payload: dict[str, Any] | None = None
                try:
                    payload = response.json()
                    if isinstance(payload.get("search_metadata"), dict):
                        serpapi_search_id = str(payload["search_metadata"].get("id"))
                except Exception:
                    payload = None

                payload_error = self._extract_payload_error(payload)

                if response.status_code == 429 or 500 <= response.status_code <= 599:
                    last_error = f"Retryable HTTP status {response.status_code}"
                    self._sleep_backoff(attempt)
                    continue

                if payload_error is not None:
                    last_error = payload_error
                    if self._is_retryable_payload_error(payload_error):
                        self._sleep_backoff(attempt)
                        continue
                    return ProviderCallResult(
                        ok=False,
                        status_code=response.status_code,
                        payload=payload,
                        error_message=payload_error,
                        serpapi_search_id=serpapi_search_id,
                        started_at=attempt_started,
                        finished_at=datetime.now(tz=UTC),
                    )

                if response.status_code >= 400:
                    return ProviderCallResult(
                        ok=False,
                        status_code=response.status_code,
                        payload=payload,
                        error_message=f"Provider HTTP {response.status_code}",
                        serpapi_search_id=serpapi_search_id,
                        started_at=attempt_started,
                        finished_at=datetime.now(tz=UTC),
                    )

                return ProviderCallResult(
                    ok=True,
                    status_code=response.status_code,
                    payload=payload or {},
                    error_message=None,
                    serpapi_search_id=serpapi_search_id,
                    started_at=attempt_started,
                    finished_at=datetime.now(tz=UTC),
                )
            except httpx.TimeoutException:
                last_error = "Timeout"
                self._sleep_backoff(attempt)
            except httpx.HTTPError as exc:
                last_error = str(exc)
                self._sleep_backoff(attempt)

        raise RetryableProviderError(
            f"SerpAPI request failed after {max_attempts} attempts: {last_error} ({last_status})"
        )

    def _extract_payload_error(self, payload: dict[str, Any] | None) -> str | None:
        if not payload:
            return None
        error_value = payload.get("error")
        if isinstance(error_value, str) and error_value.strip():
            return error_value.strip()
        metadata = payload.get("search_metadata")
        if isinstance(metadata, dict):
            status_value = metadata.get("status")
            if isinstance(status_value, str) and status_value.lower() == "error":
                return "SerpAPI reported an error status."
        return None

    def _is_retryable_payload_error(self, error_message: str) -> bool:
        normalized = error_message.lower()
        return any(
            term in normalized
            for term in ("rate limit", "too many requests", "timeout", "temporarily unavailable")
        )

    def _sleep_backoff(self, attempt: int) -> None:
        base = 0.75 * (2 ** (attempt - 1))
        time.sleep(base + random.uniform(0, 0.25))
