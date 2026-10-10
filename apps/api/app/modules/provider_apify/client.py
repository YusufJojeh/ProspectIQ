from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.config import get_settings
from app.modules.provider_apify.exceptions import ProviderConfigError, RetryableProviderError

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.apify.com/v2"
_TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}
_WAIT_FOR_FINISH_SECONDS = 60


@dataclass(frozen=True)
class ApifyCallResult:
    ok: bool
    status_code: int | None
    payload: dict[str, Any] | None
    error_message: str | None
    apify_run_id: str | None
    started_at: datetime
    finished_at: datetime


def _actor_path(actor_id: str) -> str:
    """Apify's REST API addresses an Actor as `owner~name` in the URL path."""
    return actor_id.strip().replace("/", "~")


class ApifyClient:
    """Thin REST client for the Apify platform.

    Runs an Actor (`POST /acts/{actorId}/runs`), waits for it to reach a
    terminal status by polling `GET /actor-runs/{runId}` with
    `waitForFinish`, then reads its default dataset
    (`GET /datasets/{datasetId}/items`). This client never chooses the Actor
    ID itself -- ApifyService passes in whatever app.core.config resolved
    from an allowlisted key.
    """

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.has_apify_configured:
            raise ProviderConfigError("APIFY_API_TOKEN is not configured.")
        self._token = settings.apify_api_token
        self._max_dataset_items = settings.apify_max_dataset_items
        self._timeout_seconds = settings.apify_timeout_seconds
        self._client = httpx.Client(
            base_url=_BASE_URL,
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )

    def run_actor_and_get_items(
        self, actor_id: str, run_input: dict[str, Any], *, max_attempts: int = 2
    ) -> ApifyCallResult:
        last_error = "Apify request failed."
        started_at = datetime.now(tz=UTC)

        for attempt in range(1, max_attempts + 1):
            try:
                return self._run_once(actor_id, run_input, started_at=started_at)
            except RetryableProviderError as exc:
                last_error = str(exc)
                if attempt >= max_attempts:
                    break
                self._sleep_backoff(attempt)
            except Exception as exc:
                last_error = self._safe_message(exc)
                break

        return ApifyCallResult(
            ok=False,
            status_code=None,
            payload=None,
            error_message=last_error,
            apify_run_id=None,
            started_at=started_at,
            finished_at=datetime.now(tz=UTC),
        )

    def _run_once(
        self, actor_id: str, run_input: dict[str, Any], *, started_at: datetime
    ) -> ApifyCallResult:
        actor_path = _actor_path(actor_id)
        run_object = self._start_run(actor_path, run_input)
        run_id = str(run_object.get("id") or "")
        status = str(run_object.get("status") or "")
        deadline = time.monotonic() + self._timeout_seconds

        while status not in _TERMINAL_STATUSES and time.monotonic() < deadline and run_id:
            remaining = max(1, min(_WAIT_FOR_FINISH_SECONDS, int(deadline - time.monotonic())))
            run_object = self._get_run(run_id, wait_for_finish=remaining)
            status = str(run_object.get("status") or "")

        finished_at = datetime.now(tz=UTC)
        if status != "SUCCEEDED":
            return ApifyCallResult(
                ok=False,
                status_code=None,
                payload={"run_status": status or "UNKNOWN", "apify_run_id": run_id or None},
                error_message=f"Apify run ended with status '{status or 'UNKNOWN'}'.",
                apify_run_id=run_id or None,
                started_at=started_at,
                finished_at=finished_at,
            )

        dataset_id = run_object.get("defaultDatasetId")
        items: list[Any] = []
        if isinstance(dataset_id, str) and dataset_id:
            items = self._get_dataset_items(dataset_id)

        return ApifyCallResult(
            ok=True,
            status_code=201,
            payload={
                "items": items,
                "item_count": len(items),
                "run_status": status,
                "apify_run_id": run_id or None,
            },
            error_message=None,
            apify_run_id=run_id or None,
            started_at=started_at,
            finished_at=finished_at,
        )

    def _start_run(self, actor_path: str, run_input: dict[str, Any]) -> dict[str, Any]:
        response = self._request(
            "POST",
            f"/actors/{actor_path}/runs",
            params={"token": self._token, "waitForFinish": _WAIT_FOR_FINISH_SECONDS},
            json=run_input,
        )
        return self._parse_run_response(response)

    def _get_run(self, run_id: str, *, wait_for_finish: int) -> dict[str, Any]:
        response = self._request(
            "GET",
            f"/actor-runs/{run_id}",
            params={"token": self._token, "waitForFinish": wait_for_finish},
        )
        return self._parse_run_response(response)

    def _get_dataset_items(self, dataset_id: str) -> list[Any]:
        response = self._request(
            "GET",
            f"/datasets/{dataset_id}/items",
            params={"token": self._token, "clean": "true", "limit": self._max_dataset_items},
        )
        self._raise_for_status(response, context="dataset fetch")
        try:
            payload = response.json()
        except Exception as exc:
            raise RuntimeError("Apify dataset response was not valid JSON.") from exc
        return payload if isinstance(payload, list) else []

    def _parse_run_response(self, response: httpx.Response) -> dict[str, Any]:
        self._raise_for_status(response, context="run request")
        try:
            payload = response.json()
        except Exception as exc:
            raise RuntimeError("Apify run response was not valid JSON.") from exc
        if isinstance(payload, dict):
            data = payload.get("data")
            if isinstance(data, dict):
                return data
            return payload
        return {}

    def _raise_for_status(self, response: httpx.Response, *, context: str) -> None:
        if response.status_code == 429 or 500 <= response.status_code <= 599:
            raise RetryableProviderError(f"Apify {context} returned HTTP {response.status_code}.")
        if response.status_code >= 400:
            raise RuntimeError(f"Apify {context} failed with HTTP {response.status_code}.")

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            return self._client.request(method, path, **kwargs)
        except httpx.TimeoutException as exc:
            raise RetryableProviderError("Apify request timed out.") from exc
        except httpx.HTTPError as exc:
            raise RetryableProviderError(f"Apify request failed: {exc}") from exc

    def _sleep_backoff(self, attempt: int) -> None:
        base = 1.0 * (2 ** (attempt - 1))
        time.sleep(base + random.uniform(0, 0.25))

    def _safe_message(self, exc: Exception) -> str:
        message = str(exc).strip() or exc.__class__.__name__
        return message.replace(self._token, "[REDACTED]") if self._token else message
