from fastapi.testclient import TestClient

import app.main as main_module

from app.main import app


def test_healthcheck_returns_ok() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "ProspectIQ API"


def test_database_healthcheck_returns_ok_when_probe_passes(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setattr(main_module, "check_database_connection", lambda: True)

    response = client.get("/api/v1/health/db")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}
