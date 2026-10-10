from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.modules.provider_apify.allowlist import ALLOWED_ACTOR_KEYS
from app.modules.provider_apify.exceptions import UnknownActorError
from app.modules.provider_serpapi.models import ProviderFetch, ProviderRawPayload
from app.shared.enums.jobs import ProviderFetchStatus


def _payload_sha(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _target_url(run_input: dict[str, Any]) -> str:
    start_urls = run_input.get("startUrls")
    if isinstance(start_urls, list) and start_urls:
        first = start_urls[0]
        first_url = first.get("url") if isinstance(first, dict) else None
        if isinstance(first_url, str):
            return first_url
        if isinstance(first, str):
            return first
    url = run_input.get("url")
    return url if isinstance(url, str) and url else "https://demo-business.example"


class DemoApifyService:
    """Deterministic stand-in for ApifyService, used in demo/stub/CI runtime modes."""

    def crawl(
        self,
        db: Session,
        *,
        workspace_id: int,
        search_job_id: int | None,
        actor_key: str,
        run_input: dict[str, Any],
        attempt: int = 1,  # noqa: ARG002
    ) -> tuple[ProviderFetch, dict[str, Any]]:
        if actor_key not in ALLOWED_ACTOR_KEYS:
            raise UnknownActorError(f"Apify actor_key '{actor_key}' is not allowlisted.")

        url = _target_url(run_input)
        demo_run_id = f"demo-run-{hashlib.sha256(f'{actor_key}:{url}'.encode()).hexdigest()[:12]}"
        items = [
            {
                "url": url,
                "title": "Demo Business",
                "text": (
                    "Demo Apify crawl content used for provider evidence in demo/stub mode. "
                    "Call us at +1 555 0100 for a consultation."
                ),
                "category": "Local Business",
            }
        ]
        payload = {
            "items": items,
            "item_count": len(items),
            "run_status": "SUCCEEDED",
            "apify_run_id": demo_run_id,
        }
        return self._persist_fetch(
            db,
            workspace_id=workspace_id,
            search_job_id=search_job_id,
            actor_key=actor_key,
            run_input=run_input,
            payload=payload,
            apify_run_id=demo_run_id,
        )

    def _persist_fetch(
        self,
        db: Session,
        *,
        workspace_id: int,
        search_job_id: int | None,
        actor_key: str,
        run_input: dict[str, Any],
        payload: dict[str, Any],
        apify_run_id: str,
    ) -> tuple[ProviderFetch, dict[str, Any]]:
        now = datetime.now(tz=UTC)
        params = {"actor_key": actor_key, "run_input": run_input}
        fetch = ProviderFetch(
            workspace_id=workspace_id,
            provider="apify",
            engine=actor_key,
            mode="crawl",
            search_job_id=search_job_id,
            request_fingerprint=_payload_sha(params),
            request_params_json=params,
            serpapi_search_id=apify_run_id,
            status=ProviderFetchStatus.OK.value,
            http_status=201,
            started_at=now,
            finished_at=now,
            error_message=None,
            attempt=1,
        )
        db.add(fetch)
        db.commit()
        db.refresh(fetch)
        db.add(
            ProviderRawPayload(
                provider_fetch_id=fetch.id,
                payload_json=payload,
                payload_sha256=_payload_sha(payload),
            )
        )
        db.commit()
        return fetch, payload
