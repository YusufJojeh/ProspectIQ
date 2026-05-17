from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.core.config import Settings


@dataclass(frozen=True)
class ConnectivityProbe:
    configured: bool
    reachable: bool
    detail: str | None = None


def probe_serpapi(settings: Settings) -> ConnectivityProbe:
    if not settings.has_serpapi_configured:
        return ConnectivityProbe(
            configured=False,
            reachable=False,
            detail="SERPAPI_API_KEY is not configured.",
        )

    try:
        with httpx.Client(timeout=httpx.Timeout(5.0, connect=3.0)) as client:
            response = client.get(
                settings.serpapi_base_url,
                params={
                    "api_key": settings.serpapi_api_key,
                    "engine": "google",
                    "q": "healthcheck",
                },
                headers={"Accept": "application/json"},
            )
        return ConnectivityProbe(
            configured=True,
            reachable=response.status_code < 400,
            detail=f"HTTP {response.status_code}",
        )
    except httpx.HTTPError as exc:
        return ConnectivityProbe(
            configured=True,
            reachable=False,
            detail=str(exc),
        )


def probe_ollama(settings: Settings) -> ConnectivityProbe:
    if not settings.has_ollama_configured:
        return ConnectivityProbe(
            configured=False,
            reachable=False,
            detail="OLLAMA_BASE_URL or OLLAMA_MODEL is not configured.",
        )

    try:
        with httpx.Client(timeout=httpx.Timeout(5.0, connect=3.0)) as client:
            response = client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
        return ConnectivityProbe(
            configured=True,
            reachable=response.status_code < 500,
            detail=f"HTTP {response.status_code}",
        )
    except httpx.HTTPError as exc:
        return ConnectivityProbe(
            configured=True,
            reachable=False,
            detail=str(exc),
        )
