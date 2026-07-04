from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.modules.provider_serpapi.models import ProviderFetch, ProviderRawPayload
from app.modules.provider_tavily.client import TavilyCallResult, TavilyClient, fingerprint_params
from app.modules.provider_tavily.engines.tavily_web import build_tavily_web_params, run_tavily_web
from app.modules.provider_tavily.exceptions import RetryableProviderError
from app.shared.enums.jobs import ProviderFetchStatus

logger = logging.getLogger(__name__)


def _payload_sha(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class TavilyService:
    def __init__(self) -> None:
        self.client = TavilyClient()

    def web_search(
        self,
        db: Session,
        *,
        workspace_id: int,
        search_job_id: int | None,
        query: str,
        attempt: int = 1,
    ) -> tuple[ProviderFetch, dict[str, Any]]:
        params = build_tavily_web_params(query=query)
        return self._run_and_persist(
            db,
            workspace_id=workspace_id,
            search_job_id=search_job_id,
            params=params,
            attempt=attempt,
        )

    def _run_and_persist(
        self,
        db: Session,
        *,
        workspace_id: int,
        search_job_id: int | None,
        params: dict[str, Any],
        attempt: int,
    ) -> tuple[ProviderFetch, dict[str, Any]]:
        request_fingerprint = fingerprint_params(params)
        fetch = ProviderFetch(
            workspace_id=workspace_id,
            provider="tavily",
            engine="tavily",
            mode="web_search",
            search_job_id=search_job_id,
            request_fingerprint=request_fingerprint,
            request_params_json=params,
            status=ProviderFetchStatus.ERROR.value,
            started_at=datetime.now(tz=UTC),
            attempt=attempt,
        )
        db.add(fetch)
        db.commit()
        db.refresh(fetch)

        payload: dict[str, Any] = {}
        try:
            logger.info(
                "provider.fetch.start provider=tavily mode=web_search search_job_id=%s attempt=%s fingerprint=%s",
                search_job_id,
                attempt,
                request_fingerprint,
            )
            result: TavilyCallResult = run_tavily_web(self.client, params=params)
            payload = result.payload or {}
            fetch.http_status = result.status_code
            fetch.serpapi_search_id = result.tavily_request_id
            fetch.started_at = result.started_at
            fetch.finished_at = result.finished_at
            fetch.status = self._resolve_fetch_status(result)
            fetch.error_message = result.error_message
        except RetryableProviderError as exc:
            fetch.status = self._resolve_retryable_error_status(str(exc))
            fetch.error_message = str(exc)
        except Exception as exc:
            fetch.status = ProviderFetchStatus.ERROR.value
            fetch.error_message = str(exc)
        finally:
            if fetch.finished_at is None:
                fetch.finished_at = datetime.now(tz=UTC)
            logger.info(
                "provider.fetch.finish provider=tavily mode=web_search search_job_id=%s attempt=%s "
                "fingerprint=%s status=%s http_status=%s error=%s",
                search_job_id,
                attempt,
                request_fingerprint,
                fetch.status,
                fetch.http_status,
                fetch.error_message,
            )
            db.add(fetch)
            db.commit()

        raw = ProviderRawPayload(
            provider_fetch_id=fetch.id,
            payload_json=payload,
            payload_sha256=_payload_sha(payload),
        )
        db.add(raw)
        db.commit()
        return fetch, payload

    def _resolve_fetch_status(self, result: TavilyCallResult) -> str:
        if result.ok:
            return ProviderFetchStatus.OK.value
        if result.status_code == 429 or (
            result.error_message and "rate limit" in result.error_message.lower()
        ):
            return ProviderFetchStatus.RATE_LIMITED.value
        if result.error_message and "timeout" in result.error_message.lower():
            return ProviderFetchStatus.TIMEOUT.value
        return ProviderFetchStatus.ERROR.value

    def _resolve_retryable_error_status(self, error_message: str) -> str:
        normalized = error_message.lower()
        if "429" in normalized or "rate limit" in normalized or "too many requests" in normalized:
            return ProviderFetchStatus.RATE_LIMITED.value
        if "timeout" in normalized:
            return ProviderFetchStatus.TIMEOUT.value
        return ProviderFetchStatus.ERROR.value
