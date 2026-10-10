from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.modules.provider_apify.allowlist import resolve_actor_id
from app.modules.provider_apify.client import ApifyCallResult, ApifyClient
from app.modules.provider_apify.exceptions import UnknownActorError
from app.modules.provider_serpapi.models import ProviderFetch, ProviderRawPayload
from app.shared.enums.jobs import ProviderFetchStatus

logger = logging.getLogger(__name__)


def _payload_sha(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _fingerprint(actor_key: str, run_input: dict[str, Any]) -> str:
    canonical = json.dumps(
        {"actor_key": actor_key, "run_input": run_input},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ApifyService:
    """Runs allowlisted Apify Actors and persists results through the same
    provider-fetch/evidence tables TavilyService and SerpApiService use.

    The backend -- not the caller -- maps `actor_key` to a real Actor ID
    (see app.modules.provider_apify.allowlist), so nothing upstream,
    including an LLM tool call, can trigger an arbitrary Actor run.
    """

    def __init__(self, client: ApifyClient | None = None) -> None:
        self._client = client

    def crawl(
        self,
        db: Session,
        *,
        workspace_id: int,
        search_job_id: int | None,
        actor_key: str,
        run_input: dict[str, Any],
        attempt: int = 1,
    ) -> tuple[ProviderFetch, dict[str, Any]]:
        actor_id = resolve_actor_id(actor_key)
        if actor_id is None:
            raise UnknownActorError(
                f"Apify actor_key '{actor_key}' is not allowlisted or configured."
            )

        request_fingerprint = _fingerprint(actor_key, run_input)
        fetch = ProviderFetch(
            workspace_id=workspace_id,
            provider="apify",
            engine=actor_key,
            mode="crawl",
            search_job_id=search_job_id,
            request_fingerprint=request_fingerprint,
            request_params_json={"actor_key": actor_key, "run_input": run_input},
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
                "provider.fetch.start provider=apify actor_key=%s search_job_id=%s attempt=%s fingerprint=%s",
                actor_key,
                search_job_id,
                attempt,
                request_fingerprint,
            )
            client = self._client or ApifyClient()
            result: ApifyCallResult = client.run_actor_and_get_items(actor_id, run_input)
            payload = result.payload or {}
            fetch.http_status = result.status_code
            fetch.serpapi_search_id = result.apify_run_id
            fetch.started_at = result.started_at
            fetch.finished_at = result.finished_at
            fetch.status = self._resolve_status(result)
            fetch.error_message = result.error_message
        except Exception as exc:
            fetch.status = self._resolve_status_from_message(str(exc))
            fetch.error_message = str(exc)
        finally:
            if fetch.finished_at is None:
                fetch.finished_at = datetime.now(tz=UTC)
            logger.info(
                "provider.fetch.finish provider=apify actor_key=%s search_job_id=%s attempt=%s "
                "fingerprint=%s status=%s http_status=%s apify_run_id=%s error=%s",
                actor_key,
                search_job_id,
                attempt,
                request_fingerprint,
                fetch.status,
                fetch.http_status,
                fetch.serpapi_search_id,
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

    def _resolve_status(self, result: ApifyCallResult) -> str:
        if result.ok:
            return ProviderFetchStatus.OK.value
        return self._resolve_status_from_message(result.error_message or "")

    def _resolve_status_from_message(self, message: str) -> str:
        normalized = message.lower()
        if "429" in normalized or "rate limit" in normalized:
            return ProviderFetchStatus.RATE_LIMITED.value
        if "timeout" in normalized or "timed out" in normalized:
            return ProviderFetchStatus.TIMEOUT.value
        return ProviderFetchStatus.ERROR.value
