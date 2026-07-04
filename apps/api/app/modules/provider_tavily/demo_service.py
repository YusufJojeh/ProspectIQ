from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.modules.provider_serpapi.models import ProviderFetch, ProviderRawPayload
from app.shared.enums.jobs import ProviderFetchStatus


def _payload_sha(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _slugify(value: str) -> str:
    normalized = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    collapsed = "-".join(part for part in normalized.split("-") if part)
    return collapsed or "prospect"


class DemoTavilyService:
    """Deterministic stand-in for TavilyService, used in demo/stub/CI runtime modes."""

    def web_search(
        self,
        db: Session,
        *,
        workspace_id: int,
        search_job_id: int | None,
        query: str,
        attempt: int = 1,
    ) -> tuple[ProviderFetch, dict[str, Any]]:
        branded_slug = _slugify(" ".join(query.split()[:2]))
        website = f"https://www.{branded_slug}.example"
        payload = {
            "query": query,
            "answer": f"{branded_slug.replace('-', ' ').title()} is a local business found via demo Tavily search.",
            "results": [
                {
                    "title": branded_slug.replace("-", " ").title(),
                    "url": website,
                    "content": "Demo Tavily result content.",
                    "score": 0.82,
                },
                {
                    "title": "Facebook Page",
                    "url": "https://www.facebook.com/demo-business",
                    "content": "Demo directory listing.",
                    "score": 0.4,
                },
            ],
            "response_time": 0.12,
        }
        return self._persist_fetch(
            db,
            workspace_id=workspace_id,
            search_job_id=search_job_id,
            params={"query": query},
            payload=payload,
        )

    def _persist_fetch(
        self,
        db: Session,
        *,
        workspace_id: int,
        search_job_id: int | None,
        params: dict[str, Any],
        payload: dict[str, Any],
    ) -> tuple[ProviderFetch, dict[str, Any]]:
        now = datetime.now(tz=UTC)
        fetch = ProviderFetch(
            workspace_id=workspace_id,
            provider="tavily",
            engine="tavily",
            mode="web_search",
            search_job_id=search_job_id,
            request_fingerprint=_payload_sha(params),
            request_params_json=params,
            status=ProviderFetchStatus.OK.value,
            http_status=200,
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
