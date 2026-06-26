from __future__ import annotations

from test_workspace_e2e import (
    _build_session_factory,
    _E2EAnalysisAdapter,
    _login,
    _override_client,
    _seed_workspace,
)

from app.modules.ai_analysis.service import RuntimeCandidate


def test_history_endpoint_returns_empty_list_when_no_snapshots() -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        response = client.get(
            f"/api/v1/ai-analysis/leads/{seed.lead_public_id}/history",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["lead_id"] == seed.lead_public_id
    assert data["items"] == []


def test_history_endpoint_returns_snapshot_after_analysis(monkeypatch) -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    monkeypatch.setattr(
        "app.modules.ai_analysis.service.AIAnalysisService._resolve_runtime_candidates",
        lambda self: [
            RuntimeCandidate(
                adapter=_E2EAnalysisAdapter(),
                provider_name="test",
                model_name="test-analysis-model",
            )
        ],
    )

    with _override_client(session_factory) as client:
        token = _login(client, seed)

        client.post(
            f"/api/v1/ai-analysis/leads/{seed.lead_public_id}/generate",
            headers={"Authorization": f"Bearer {token}"},
        )

        history_response = client.get(
            f"/api/v1/ai-analysis/leads/{seed.lead_public_id}/history",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert history_response.status_code == 200
    items = history_response.json()["items"]
    assert len(items) == 1
    assert items[0]["lead_id"] == seed.lead_public_id
    assert items[0]["analysis"]["summary"]


def test_generate_endpoint_creates_fresh_snapshot_for_same_facts(monkeypatch) -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    monkeypatch.setattr(
        "app.modules.ai_analysis.service.AIAnalysisService._resolve_runtime_candidates",
        lambda self: [
            RuntimeCandidate(
                adapter=_E2EAnalysisAdapter(),
                provider_name="test",
                model_name="test-analysis-model",
            )
        ],
    )

    with _override_client(session_factory) as client:
        token = _login(client, seed)

        client.post(
            f"/api/v1/ai-analysis/leads/{seed.lead_public_id}/generate",
            headers={"Authorization": f"Bearer {token}"},
        )
        client.post(
            f"/api/v1/ai-analysis/leads/{seed.lead_public_id}/generate",
            headers={"Authorization": f"Bearer {token}"},
        )

        history_response = client.get(
            f"/api/v1/ai-analysis/leads/{seed.lead_public_id}/history",
            headers={"Authorization": f"Bearer {token}"},
        )

    items = history_response.json()["items"]
    assert len(items) == 2
    assert items[0]["public_id"] != items[1]["public_id"]


def test_history_endpoint_returns_404_for_unknown_lead() -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        response = client.get(
            "/api/v1/ai-analysis/leads/lead_unknown_xyz/history",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 404


def test_history_endpoint_requires_authentication() -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with _override_client(session_factory) as client:
        response = client.get(
            f"/api/v1/ai-analysis/leads/{seed.lead_public_id}/history",
        )

    assert response.status_code == 401
