from __future__ import annotations

from test_workspace_e2e import (
    _build_session_factory,
    _login,
    _override_client,
    _seed_workspace,
)


def test_service_catalog_returns_defaults_when_no_custom_items() -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        response = client.get(
            "/api/v1/admin/service-catalog",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["is_default"] is True
    assert len(data["items"]) > 0
    for item in data["items"]:
        assert item["service_name"]
        assert item["is_active"] is True


def test_create_catalog_item_returns_201() -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        response = client.post(
            "/api/v1/admin/service-catalog",
            headers={"Authorization": f"Bearer {token}"},
            json={"service_name": "Custom Local SEO", "rank_order": 1},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["service_name"] == "Custom Local SEO"
    assert data["rank_order"] == 1
    assert data["is_active"] is True
    assert data["public_id"].startswith("scat_")


def test_service_catalog_returns_custom_items_after_creation() -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        client.post(
            "/api/v1/admin/service-catalog",
            headers={"Authorization": f"Bearer {token}"},
            json={"service_name": "Custom PPC", "rank_order": 1},
        )

        list_response = client.get(
            "/api/v1/admin/service-catalog",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert list_response.status_code == 200
    data = list_response.json()
    assert data["is_default"] is False
    names = [item["service_name"] for item in data["items"]]
    assert "Custom PPC" in names


def test_update_catalog_item_changes_fields() -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        create_resp = client.post(
            "/api/v1/admin/service-catalog",
            headers={"Authorization": f"Bearer {token}"},
            json={"service_name": "Social Media", "rank_order": 2},
        )
        item_id = create_resp.json()["public_id"]

        patch_resp = client.patch(
            f"/api/v1/admin/service-catalog/{item_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"description": "Organic social growth", "rank_order": 1},
        )

    assert patch_resp.status_code == 200
    updated = patch_resp.json()
    assert updated["description"] == "Organic social growth"
    assert updated["rank_order"] == 1


def test_delete_catalog_item_returns_204() -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        create_resp = client.post(
            "/api/v1/admin/service-catalog",
            headers={"Authorization": f"Bearer {token}"},
            json={"service_name": "Delete Me", "rank_order": 5},
        )
        item_id = create_resp.json()["public_id"]

        delete_resp = client.delete(
            f"/api/v1/admin/service-catalog/{item_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert delete_resp.status_code == 204

        list_resp = client.get(
            "/api/v1/admin/service-catalog",
            headers={"Authorization": f"Bearer {token}"},
        )

    names = [item["service_name"] for item in list_resp.json()["items"]]
    assert "Delete Me" not in names


def test_delete_nonexistent_catalog_item_returns_404() -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        response = client.delete(
            "/api/v1/admin/service-catalog/scat_doesnotexist",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 404


def test_catalog_create_validates_rank_order_bounds() -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        response = client.post(
            "/api/v1/admin/service-catalog",
            headers={"Authorization": f"Bearer {token}"},
            json={"service_name": "Bad Rank", "rank_order": 0},
        )

    assert response.status_code == 422


def test_service_catalog_requires_admin_role() -> None:
    session_factory = _build_session_factory()
    _seed_workspace(session_factory)

    with _override_client(session_factory) as client:
        member_login = client.post(
            "/api/v1/auth/login",
            json={"email": "sales@example.com", "password": "SalesPass123!"},
        )
        assert member_login.status_code == 200
        member_token = member_login.json()["access_token"]

        response = client.get(
            "/api/v1/admin/service-catalog",
            headers={"Authorization": f"Bearer {member_token}"},
        )

    assert response.status_code == 403
