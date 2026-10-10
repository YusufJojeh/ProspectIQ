from __future__ import annotations

from typing import Any

import httpx
from fastapi.testclient import TestClient


def start_agent_run(
    client: TestClient, path: str, *, json: dict[str, Any], headers: dict[str, str]
) -> httpx.Response:
    """POST a run and return the run as it stands once the agent loop settles.

    The endpoint answers as soon as the run is committed and drives the loop
    as a background task; TestClient finishes background tasks before it
    returns, so a GET right after the POST sees the paused or finished run.
    """
    created = client.post(path, json=json, headers=headers)
    assert created.status_code == 201, created.text
    return client.get(f"{path}/{created.json()['run_id']}", headers=headers)
