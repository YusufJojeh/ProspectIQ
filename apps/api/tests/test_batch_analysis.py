from __future__ import annotations

from test_workspace_e2e import (
    _build_session_factory,
    _E2EAnalysisAdapter,
    _login,
    _override_client,
    _seed_workspace,
)

from app.modules.ai_analysis.service import RuntimeCandidate


def _stub_analysis_runtime(monkeypatch) -> None:
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


def test_batch_analysis_succeeds_for_known_lead(monkeypatch) -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    _stub_analysis_runtime(monkeypatch)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        response = client.post(
            "/api/v1/ai-analysis/batch",
            headers={"Authorization": f"Bearer {token}"},
            json={"lead_ids": [seed.lead_public_id]},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["triggered_count"] == 1
    assert len(data["results"]) == 1
    assert data["results"][0]["lead_id"] == seed.lead_public_id
    assert data["results"][0]["snapshot"] is not None
    assert data["results"][0]["error"] is None


def test_batch_analysis_returns_error_entry_for_unknown_lead() -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        response = client.post(
            "/api/v1/ai-analysis/batch",
            headers={"Authorization": f"Bearer {token}"},
            json={"lead_ids": ["lead_does_not_exist"]},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["triggered_count"] == 1
    result = data["results"][0]
    assert result["lead_id"] == "lead_does_not_exist"
    assert result["snapshot"] is None
    assert result["error"] is not None


def test_batch_analysis_mixes_success_and_error(monkeypatch) -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    _stub_analysis_runtime(monkeypatch)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        response = client.post(
            "/api/v1/ai-analysis/batch",
            headers={"Authorization": f"Bearer {token}"},
            json={"lead_ids": [seed.lead_public_id, "lead_missing"]},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["triggered_count"] == 2
    by_lead = {r["lead_id"]: r for r in data["results"]}
    assert by_lead[seed.lead_public_id]["snapshot"] is not None
    assert by_lead[seed.lead_public_id]["error"] is None
    assert by_lead["lead_missing"]["snapshot"] is None
    assert by_lead["lead_missing"]["error"] is not None


def test_batch_analysis_requires_at_least_one_lead_id() -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        response = client.post(
            "/api/v1/ai-analysis/batch",
            headers={"Authorization": f"Bearer {token}"},
            json={"lead_ids": []},
        )

    assert response.status_code == 422


def test_batch_analysis_requires_authentication() -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with _override_client(session_factory) as client:
        response = client.post(
            "/api/v1/ai-analysis/batch",
            json={"lead_ids": [seed.lead_public_id]},
        )

    assert response.status_code == 401
