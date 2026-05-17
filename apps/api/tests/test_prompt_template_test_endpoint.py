from __future__ import annotations

from sqlalchemy import func, select
from test_workspace_e2e import (
    _build_session_factory,
    _E2EAnalysisAdapter,
    _login,
    _override_client,
    _seed_workspace,
)

from app.modules.ai_analysis.models import AIAnalysisSnapshot
from app.modules.ai_analysis.service import RuntimeCandidate


def _get_template_id(client, token) -> str:
    resp = client.get(
        "/api/v1/admin/prompt-templates",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert items, "No prompt templates found — _seed_workspace must create one"
    return items[0]["public_id"]


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


def test_template_test_endpoint_returns_preview_snapshot(monkeypatch) -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    _stub_analysis_runtime(monkeypatch)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        template_id = _get_template_id(client, token)

        response = client.post(
            f"/api/v1/admin/prompt-templates/{template_id}/test",
            headers={"Authorization": f"Bearer {token}"},
            json={"lead_id": seed.lead_public_id},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["public_id"].startswith("preview_")
    assert data["analysis"]["summary"]


def test_template_test_endpoint_does_not_persist_snapshot() -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        template_id = _get_template_id(client, token)

        client.post(
            f"/api/v1/admin/prompt-templates/{template_id}/test",
            headers={"Authorization": f"Bearer {token}"},
            json={"lead_id": seed.lead_public_id},
        )

    with session_factory() as db:
        count = db.scalar(select(func.count(AIAnalysisSnapshot.id)))

    assert count == 0


def test_template_test_endpoint_returns_404_for_unknown_lead() -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        template_id = _get_template_id(client, token)

        response = client.post(
            f"/api/v1/admin/prompt-templates/{template_id}/test",
            headers={"Authorization": f"Bearer {token}"},
            json={"lead_id": "lead_does_not_exist"},
        )

    assert response.status_code == 404


def test_template_test_endpoint_returns_403_for_non_admin() -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        template_id = _get_template_id(client, token)

        member_login = client.post(
            "/api/v1/auth/login",
            json={"email": "sales@example.com", "password": "SalesPass123!"},
        )
        member_token = member_login.json()["access_token"]

        response = client.post(
            f"/api/v1/admin/prompt-templates/{template_id}/test",
            headers={"Authorization": f"Bearer {member_token}"},
            json={"lead_id": seed.lead_public_id},
        )

    assert response.status_code == 403
