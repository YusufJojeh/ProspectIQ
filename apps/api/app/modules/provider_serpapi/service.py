from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.provider_serpapi.client import ProviderCallResult
from app.modules.provider_serpapi.client import SerpApiClient, fingerprint_params
from app.modules.provider_serpapi.engines.maps_place import build_maps_place_params, run_maps_place
from app.modules.provider_serpapi.engines.maps_search import build_maps_search_params, run_maps_search
from app.modules.provider_serpapi.engines.web_search import build_web_search_params, run_web_search
from app.modules.provider_serpapi.exceptions import RetryableProviderError
from app.modules.provider_serpapi.models import ProviderFetch, ProviderRawPayload, ProviderSettings
from app.shared.enums.jobs import ProviderFetchStatus


def _payload_sha(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class SerpApiService:
    def __init__(self) -> None:
        self.client = SerpApiClient()

    def get_settings(self, db: Session, workspace_id: int) -> ProviderSettings:
        statement = select(ProviderSettings).where(ProviderSettings.workspace_id == workspace_id)
        settings = db.scalar(statement)
        if settings is None:
            settings = ProviderSettings(workspace_id=workspace_id)
            db.add(settings)
            db.commit()
            db.refresh(settings)
        return settings

    def maps_search(
        self,
        db: Session,
        *,
        workspace_id: int,
        search_job_id: int,
        business_type: str,
        city: str,
        region: str | None,
        attempt: int = 1,
    ) -> tuple[ProviderFetch, dict[str, Any]]:
        settings = self.get_settings(db, workspace_id)
        params = build_maps_search_params(
            business_type=business_type,
            city=city,
            region=region,
            hl=settings.hl,
            gl=settings.gl,
            google_domain=settings.google_domain,
        )
        return self._run_and_persist(
            db,
            workspace_id=workspace_id,
            search_job_id=search_job_id,
            engine="google_maps",
            mode="maps_search",
            params=params,
            attempt=attempt,
        )

    def maps_place(
        self,
        db: Session,
        *,
        workspace_id: int,
        search_job_id: int | None,
        place_key: str,
        attempt: int = 1,
    ) -> tuple[ProviderFetch, dict[str, Any]]:
        settings = self.get_settings(db, workspace_id)
        params = build_maps_place_params(
            place_key=place_key, hl=settings.hl, gl=settings.gl, google_domain=settings.google_domain
        )
        return self._run_and_persist(
            db,
            workspace_id=workspace_id,
            search_job_id=search_job_id,
            engine="google_maps",
            mode="maps_place",
            params=params,
            attempt=attempt,
        )

    def web_search(
        self,
        db: Session,
        *,
        workspace_id: int,
        search_job_id: int | None,
        query: str,
        attempt: int = 1,
    ) -> tuple[ProviderFetch, dict[str, Any]]:
        settings = self.get_settings(db, workspace_id)
        params = build_web_search_params(
            query=query, hl=settings.hl, gl=settings.gl, google_domain=settings.google_domain
        )
        return self._run_and_persist(
            db,
            workspace_id=workspace_id,
            search_job_id=search_job_id,
            engine="google",
            mode="web_search",
            params=params,
            attempt=attempt,
        )

    def _run_and_persist(
        self,
        db: Session,
        *,
        workspace_id: int,
        search_job_id: int | None,
        engine: str,
        mode: str,
        params: dict[str, Any],
        attempt: int,
    ) -> tuple[ProviderFetch, dict[str, Any]]:
        fetch = ProviderFetch(
            workspace_id=workspace_id,
            provider="serpapi",
            engine=engine,
            mode=mode,
            search_job_id=search_job_id,
            request_fingerprint=fingerprint_params(params),
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
            result: ProviderCallResult
            if mode == "maps_search":
                result = run_maps_search(self.client, params=params)
            elif mode == "maps_place":
                result = run_maps_place(self.client, params=params)
            elif mode == "web_search":
                result = run_web_search(self.client, params=params)
            else:
                raise ValueError(f"Unsupported provider mode '{mode}'.")

            payload = result.payload or {}
            fetch.http_status = result.status_code
            fetch.serpapi_search_id = result.serpapi_search_id
            fetch.started_at = result.started_at
            fetch.finished_at = result.finished_at
            fetch.status = self._resolve_fetch_status(result)
            fetch.error_message = result.error_message
        except RetryableProviderError as exc:
            fetch.status = ProviderFetchStatus.TIMEOUT.value
            fetch.error_message = str(exc)
        except Exception as exc:
            fetch.status = ProviderFetchStatus.ERROR.value
            fetch.error_message = str(exc)
        finally:
            if fetch.finished_at is None:
                fetch.finished_at = datetime.now(tz=UTC)
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

    def _resolve_fetch_status(self, result: ProviderCallResult) -> str:
        if result.ok:
            return ProviderFetchStatus.OK.value
        if result.status_code == 429:
            return ProviderFetchStatus.RATE_LIMITED.value
        if result.error_message and "timeout" in result.error_message.lower():
            return ProviderFetchStatus.TIMEOUT.value
        return ProviderFetchStatus.ERROR.value
