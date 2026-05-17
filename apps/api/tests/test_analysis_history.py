from __future__ import annotations

from tests.test_workspace_e2e import (
    _build_session_factory,
    _login,
    _override_client,
    _seed_workspace,
)


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


def test_history_endpoint_returns_snapshot_after_analysis() -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

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


def test_history_deduplication_returns_one_snapshot_for_same_facts() -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

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
    assert len(items) == 1


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
