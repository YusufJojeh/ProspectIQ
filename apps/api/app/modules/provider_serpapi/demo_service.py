from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.modules.provider_serpapi.models import ProviderFetch, ProviderRawPayload, ProviderSettings
from app.modules.provider_serpapi.schemas import PlaceLookupKey
from app.shared.enums.jobs import ProviderFetchStatus

_CITY_COORDINATES: dict[str, tuple[float, float]] = {
    "ankara": (39.9334, 32.8597),
    "antalya": (36.8969, 30.7133),
    "bursa": (40.1950, 29.0600),
    "dubai": (25.2048, 55.2708),
    "istanbul": (41.0082, 28.9784),
    "izmir": (38.4237, 27.1428),
    "london": (51.5072, -0.1276),
    "riyadh": (24.7136, 46.6753),
}

_SERVICE_SUFFIXES = (
    "Studio",
    "Partners",
    "Growth Lab",
    "Collective",
    "Works",
)


def _payload_sha(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _slugify(value: str) -> str:
    normalized = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    collapsed = "-".join(part for part in normalized.split("-") if part)
    return collapsed or "prospect"


class DemoSerpApiService:
    def get_settings(self, db: Session, workspace_id: int) -> ProviderSettings:
        settings = (
            db.query(ProviderSettings)
            .filter(ProviderSettings.workspace_id == workspace_id)
            .one_or_none()
        )
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
        radius_km: int | None = None,
        keyword_filter: str | None = None,
        page: int = 1,
        attempt: int = 1,
    ) -> tuple[ProviderFetch, dict[str, Any]]:
        search_parameters: dict[str, Any] = {
            "business_type": business_type,
            "city": city,
            "region": region,
            "radius_km": radius_km,
            "keyword_filter": keyword_filter,
            "page": page,
        }
        payload = {
            "search_metadata": {
                "id": f"demo-search-{search_job_id}-{page}",
                "status": "Success",
            },
            "search_parameters": search_parameters,
            "local_results": self._build_local_results(
                business_type=business_type,
                city=city,
                region=region,
                keyword_filter=keyword_filter,
            ),
        }
        return self._persist_fetch(
            db,
            workspace_id=workspace_id,
            search_job_id=search_job_id,
            engine="google_maps",
            mode="maps_search",
            params=search_parameters,
            payload=payload,
        )

    def maps_place(
        self,
        db: Session,
        *,
        workspace_id: int,
        search_job_id: int | None,
        lookup: PlaceLookupKey,
        attempt: int = 1,
    ) -> tuple[ProviderFetch, dict[str, Any]]:
        lookup_value = lookup.value
        base_slug = _slugify(lookup_value.split(":")[-1])
        website = f"https://www.{base_slug}.example"
        payload = {
            "search_metadata": {
                "id": f"demo-place-{base_slug}-{attempt}",
                "status": "Success",
            },
            "place_results": {
                "title": lookup_value.replace("-", " ").title(),
                "address": "Demo address",
                "phone": "+90 212 555 0101",
                "website": website,
                "rating": 4.6,
                "reviews": 28,
                "gps_coordinates": {
                    "latitude": 41.0082,
                    "longitude": 28.9784,
                },
                "data_id": base_slug,
                "type": "Business",
            },
        }
        return self._persist_fetch(
            db,
            workspace_id=workspace_id,
            search_job_id=search_job_id,
            engine="google_maps",
            mode="maps_place",
            params={"lookup_type": lookup.key_type, "lookup": lookup.value},
            payload=payload,
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
        branded_slug = _slugify(" ".join(query.split()[:2]))
        website = f"https://www.{branded_slug}.example"
        payload = {
            "search_metadata": {
                "id": f"demo-web-{branded_slug}-{attempt}",
                "status": "Success",
            },
            "knowledge_graph": {
                "website": website,
            },
            "organic_results": [
                {"position": 1, "link": website},
                {"position": 2, "link": "https://www.facebook.com/demo-business"},
            ],
        }
        return self._persist_fetch(
            db,
            workspace_id=workspace_id,
            search_job_id=search_job_id,
            engine="google",
            mode="web_search",
            params={"query": query},
            payload=payload,
        )

    def _build_local_results(
        self,
        *,
        business_type: str,
        city: str,
        region: str | None,
        keyword_filter: str | None,
    ) -> list[dict[str, Any]]:
        city_key = city.casefold().strip()
        base_lat, base_lng = _CITY_COORDINATES.get(city_key, (41.0082, 28.9784))
        business_slug = _slugify(business_type)
        city_slug = _slugify(city)
        keyword_label = keyword_filter.strip().title() if keyword_filter else None
        base_label = keyword_label or business_type.title()
        region_label = f" {region}" if region else ""
        items: list[dict[str, Any]] = []
        for index, suffix in enumerate(_SERVICE_SUFFIXES, start=1):
            company_name = f"{base_label} {suffix}"
            slug = f"{business_slug}-{city_slug}-{index}"
            website = None if index % 2 == 0 else f"https://www.{slug}.example"
            items.append(
                {
                    "title": company_name,
                    "address": f"{city.title()}{region_label} Demo District {index}",
                    "phone": f"+90 212 555 01{index:02d}",
                    "website": website,
                    "rating": round(4.1 + (index * 0.12), 1),
                    "reviews": 8 + (index * 7),
                    "gps_coordinates": {
                        "latitude": round(base_lat + (index * 0.008), 6),
                        "longitude": round(base_lng + (index * 0.01), 6),
                    },
                    "data_id": slug,
                    "data_cid": f"demo-cid-{slug}",
                    "place_id": f"demo-place-{slug}",
                    "city": city.title(),
                    "type": business_type.title(),
                }
            )
        return items

    def _persist_fetch(
        self,
        db: Session,
        *,
        workspace_id: int,
        search_job_id: int | None,
        engine: str,
        mode: str,
        params: dict[str, Any],
        payload: dict[str, Any],
    ) -> tuple[ProviderFetch, dict[str, Any]]:
        now = datetime.now(tz=UTC)
        fetch = ProviderFetch(
            workspace_id=workspace_id,
            provider="demo",
            engine=engine,
            mode=mode,
            search_job_id=search_job_id,
            request_fingerprint=_payload_sha(params),
            request_params_json=params,
            serpapi_search_id=payload.get("search_metadata", {}).get("id"),
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
