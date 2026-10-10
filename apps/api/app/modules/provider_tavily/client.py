from __future__ import annotations

import hashlib
import json
import logging
import random
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock
from typing import Any, Protocol, cast

from app.core.config import get_settings
from app.modules.provider_tavily.exceptions import ProviderConfigError

TavilySdkClient: Any
try:  # pragma: no cover - exercised by the guarded live smoke when installed.
    from tavily import (  # type: ignore[import-not-found,import-untyped,no-redef,unused-ignore]
        TavilyClient as TavilySdkClient,
    )
except ImportError:  # pragma: no cover - dependency installation is validated by gates.
    TavilySdkClient = None

logger = logging.getLogger(__name__)

SleepFn = Callable[[float], None]
ClockFn = Callable[[], float]


class TavilySdkClientProtocol(Protocol):
    def search(self, **kwargs: Any) -> object: ...

    def extract(self, **kwargs: Any) -> object: ...

    def research(self, **kwargs: Any) -> object: ...

    def get_research(self, request_id: str, **kwargs: Any) -> object: ...


@dataclass(frozen=True)
class TavilyCallResult:
    ok: bool
    status_code: int | None
    payload: dict[str, Any] | None
    error_message: str | None
    tavily_request_id: str | None
    started_at: datetime
    finished_at: datetime


def fingerprint_params(params: dict[str, Any]) -> str:
    canonical = json.dumps(params, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class TavilyTokenBucket:
    """Small process-local token bucket used before calling Tavily's SDK.

    This is deliberately conservative and per-process. It protects local
    workers from bursts; Tavily's own account-level limits still remain the
    source of truth.
    """

    def __init__(
        self,
        *,
        rpm: int,
        sleep_fn: SleepFn = time.sleep,
        clock: ClockFn = time.monotonic,
    ) -> None:
        self.capacity = max(1, int(rpm))
        self.refill_per_second = self.capacity / 60.0
        self._tokens = float(self.capacity)
        self._updated_at = clock()
        self._sleep = sleep_fn
        self._clock = clock
        self._lock = Lock()

    def acquire(self) -> None:
        while True:
            wait_seconds = self._try_consume()
            if wait_seconds <= 0:
                return
            self._sleep(wait_seconds)

    def _try_consume(self) -> float:
        with self._lock:
            now = self._clock()
            elapsed = max(0.0, now - self._updated_at)
            if elapsed > 0:
                self._tokens = min(
                    float(self.capacity),
                    self._tokens + elapsed * self.refill_per_second,
                )
                self._updated_at = now

            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return 0.0

            missing = 1.0 - self._tokens
            return max(0.01, missing / self.refill_per_second)


class TavilyClient:
    """SDK-backed Tavily client with local rate limiting and safe failures."""

    def __init__(
        self,
        *,
        sdk_client: TavilySdkClientProtocol | None = None,
        rate_limiter: TavilyTokenBucket | None = None,
        sleep_fn: SleepFn = time.sleep,
    ) -> None:
        settings = get_settings()
        if sdk_client is None:
            if not settings.has_tavily_configured:
                raise ProviderConfigError("TAVILY_API_KEY is not configured.")
            if TavilySdkClient is None:
                raise ProviderConfigError("tavily-python is not installed.")
            sdk_client = cast(
                TavilySdkClientProtocol, TavilySdkClient(api_key=settings.tavily_api_key)
            )

        self._client = sdk_client
        self._sleep = sleep_fn
        self._rate_limiter = rate_limiter or TavilyTokenBucket(
            rpm=settings.tavily_rate_limit_rpm,
            sleep_fn=sleep_fn,
        )

    def search(self, params: dict[str, Any], *, max_attempts: int = 3) -> TavilyCallResult:
        return self._call("search", params, max_attempts=max_attempts)

    def extract(self, params: dict[str, Any], *, max_attempts: int = 3) -> TavilyCallResult:
        return self._call("extract", params, max_attempts=max_attempts)

    def research(self, params: dict[str, Any], *, max_attempts: int = 1) -> TavilyCallResult:
        return self._call("research", params, max_attempts=max_attempts)

    def get_research(self, request_id: str, *, max_attempts: int = 1) -> TavilyCallResult:
        return self._call("get_research", {"request_id": request_id}, max_attempts=max_attempts)

    def _call(
        self,
        operation: str,
        params: dict[str, Any],
        *,
        max_attempts: int,
    ) -> TavilyCallResult:
        last_error = "Tavily request failed."
        last_status: int | None = None
        started_at = datetime.now(tz=UTC)

        for attempt in range(1, max_attempts + 1):
            attempt_started = datetime.now(tz=UTC)
            try:
                self._rate_limiter.acquire()
                logger.info(
                    "tavily.request operation=%s attempt=%s max_attempts=%s fingerprint=%s",
                    operation,
                    attempt,
                    max_attempts,
                    fingerprint_params(params),
                )
                payload_obj = self._invoke_sdk(operation, params)
                payload, shape_error = self._coerce_payload(payload_obj)
                request_id = self._extract_request_id(payload)
                if shape_error is not None:
                    return TavilyCallResult(
                        ok=False,
                        status_code=None,
                        payload=payload,
                        error_message=shape_error,
                        tavily_request_id=request_id,
                        started_at=attempt_started,
                        finished_at=datetime.now(tz=UTC),
                    )

                payload_error = self._extract_payload_error(payload)
                if payload_error is not None:
                    return TavilyCallResult(
                        ok=False,
                        status_code=None,
                        payload=payload,
                        error_message=payload_error,
                        tavily_request_id=request_id,
                        started_at=attempt_started,
                        finished_at=datetime.now(tz=UTC),
                    )

                return TavilyCallResult(
                    ok=True,
                    status_code=200,
                    payload=payload,
                    error_message=None,
                    tavily_request_id=request_id,
                    started_at=attempt_started,
                    finished_at=datetime.now(tz=UTC),
                )
            except Exception as exc:
                status_code, retry_after = self._exception_status_and_retry_after(exc)
                last_status = status_code
                last_error = self._safe_exception_message(exc)
                if not self._should_retry(status_code, last_error) or attempt >= max_attempts:
                    return TavilyCallResult(
                        ok=False,
                        status_code=status_code,
                        payload=None,
                        error_message=last_error,
                        tavily_request_id=None,
                        started_at=attempt_started,
                        finished_at=datetime.now(tz=UTC),
                    )
                self._sleep_retry(attempt, retry_after=retry_after)

        return TavilyCallResult(
            ok=False,
            status_code=last_status,
            payload=None,
            error_message=last_error,
            tavily_request_id=None,
            started_at=started_at,
            finished_at=datetime.now(tz=UTC),
        )

    def _invoke_sdk(self, operation: str, params: dict[str, Any]) -> object:
        if operation == "search":
            return self._client.search(**params)
        if operation == "extract":
            return self._client.extract(**params)
        if operation == "research":
            return self._client.research(**params)
        if operation == "get_research":
            request_id = params.get("request_id")
            if not isinstance(request_id, str) or not request_id.strip():
                raise ValueError("Tavily research request_id must not be empty.")
            return self._client.get_research(request_id.strip())
        raise ValueError(f"Unsupported Tavily operation '{operation}'.")

    def _coerce_payload(self, value: object) -> tuple[dict[str, Any] | None, str | None]:
        if isinstance(value, dict):
            return cast(dict[str, Any], value), None
        model_dump = getattr(value, "model_dump", None)
        if callable(model_dump):
            payload = model_dump()
            if isinstance(payload, dict):
                return cast(dict[str, Any], payload), None
        to_dict = getattr(value, "dict", None)
        if callable(to_dict):
            payload = to_dict()
            if isinstance(payload, dict):
                return cast(dict[str, Any], payload), None
        logger.warning("tavily.response.unexpected_shape payload_type=%s", type(value).__name__)
        return None, "Tavily returned an unexpected payload shape."

    def _extract_payload_error(self, payload: dict[str, Any] | None) -> str | None:
        if not payload:
            return None
        error_value = payload.get("error") or payload.get("detail")
        if isinstance(error_value, str) and error_value.strip():
            return error_value.strip()
        return None

    def _extract_request_id(self, payload: dict[str, Any] | None) -> str | None:
        if not payload:
            return None
        request_id = payload.get("request_id")
        return str(request_id) if request_id is not None else None

    def _exception_status_and_retry_after(self, exc: Exception) -> tuple[int | None, float | None]:
        response = getattr(exc, "response", None)
        status_code = self._coerce_int(getattr(response, "status_code", None))
        if status_code is None:
            status_code = self._coerce_int(getattr(exc, "status_code", None))

        retry_after: float | None = None
        retry_attr = getattr(exc, "retry_after_seconds", None)
        if isinstance(retry_attr, int | float):
            retry_after = float(retry_attr)
        headers = getattr(response, "headers", None)
        if retry_after is None and isinstance(headers, Mapping):
            value = headers.get("retry-after") or headers.get("Retry-After")
            retry_after = self._parse_retry_after(value)
        return status_code, retry_after

    def _should_retry(self, status_code: int | None, message: str) -> bool:
        normalized = message.lower()
        if status_code in {401, 403}:
            return False
        if status_code == 429 or (status_code is not None and 500 <= status_code <= 599):
            return True
        return any(
            term in normalized
            for term in ("timeout", "timed out", "temporarily unavailable", "rate limit")
        )

    def _sleep_retry(self, attempt: int, *, retry_after: float | None) -> None:
        if retry_after is not None and retry_after >= 0:
            self._sleep(min(retry_after, 60.0))
            return
        base = 0.75 * (2 ** (attempt - 1))
        self._sleep(base + random.uniform(0, 0.25))

    def _safe_exception_message(self, exc: Exception) -> str:
        message = str(exc).strip() or exc.__class__.__name__
        key = get_settings().tavily_api_key
        return message.replace(key, "[REDACTED]") if key else message

    def _coerce_int(self, value: object) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        return None

    def _parse_retry_after(self, value: object) -> float | None:
        if isinstance(value, int | float):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value.strip())
            except ValueError:
                return None
        return None
