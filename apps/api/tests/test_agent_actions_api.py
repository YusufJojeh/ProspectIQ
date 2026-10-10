from __future__ import annotations

from test_workspace_e2e import _build_session_factory, _login, _override_client, _seed_workspace

from app.core.config import clear_settings_cache
from app.core.security import hash_password
from app.modules.users.models import User, Workspace


def _use_stub_runtime(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("TAVILY_RUNTIME_MODE", "demo")
    monkeypatch.setenv("APIFY_RUNTIME_MODE", "demo")
    clear_settings_cache()


def test_agent_run_lifecycle_via_api_pauses_approves_and_resumes(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _use_stub_runtime(monkeypatch)
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        headers = {"Authorization": f"Bearer {token}"}

        create_response = client.post(
            "/api/v1/agent/runs",
            json={"goal": "Research this lead and propose next steps.", "lead_id": seed.lead_public_id},
            headers=headers,
        )
        assert create_response.status_code == 201
        run_payload = create_response.json()
        assert run_payload["status"] == "waiting_for_approval"
        run_id = run_payload["run_id"]

        events_response = client.get(f"/api/v1/agent/runs/{run_id}/events", headers=headers)
        assert events_response.status_code == 200
        event_types = [event["event_type"] for event in events_response.json()["events"]]
        assert "agent_started" in event_types
        assert "action_proposed" in event_types
        assert "waiting_for_approval" in event_types

        actions_response = client.get(
            "/api/v1/agent/actions", params={"status": "pending"}, headers=headers
        )
        assert actions_response.status_code == 200
        pending_actions = actions_response.json()["items"]
        assert len(pending_actions) == 1
        action_id = pending_actions[0]["action_id"]
        assert pending_actions[0]["tool_name"] == "add_lead_note"
        # The action is correlated to its run by the PUBLIC run id (not an
        # internal integer), and can be listed per run.
        assert pending_actions[0]["run_id"] == run_id
        by_run = client.get("/api/v1/agent/actions", params={"run_id": run_id}, headers=headers)
        assert [a["action_id"] for a in by_run.json()["items"]] == [action_id]
        unknown = client.get("/api/v1/agent/actions", params={"run_id": "arun_nope"}, headers=headers)
        assert unknown.json()["items"] == [] and unknown.json()["total"] == 0

        approve_response = client.post(
            f"/api/v1/agent/actions/{action_id}/approve", headers=headers
        )
        assert approve_response.status_code == 200
        assert approve_response.json()["status"] == "executed"

        run_after_approve = client.get(f"/api/v1/agent/runs/{run_id}", headers=headers).json()
        assert run_after_approve["status"] == "waiting_for_approval"

        actions_response_2 = client.get(
            "/api/v1/agent/actions", params={"status": "pending"}, headers=headers
        )
        second_action_id = actions_response_2.json()["items"][0]["action_id"]

        reject_response = client.post(
            f"/api/v1/agent/actions/{second_action_id}/reject",
            json={"reason": "Not needed right now."},
            headers=headers,
        )
        assert reject_response.status_code == 200
        assert reject_response.json()["status"] == "rejected"

        run_final = client.get(f"/api/v1/agent/runs/{run_id}", headers=headers).json()
        assert run_final["status"] == "completed"
        assert run_final["final_answer"] is not None


def test_agent_action_is_workspace_scoped_and_missing_ids_404(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _use_stub_runtime(monkeypatch)
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    foreign_password = "ForeignPass123!"
    with session_factory() as db:
        foreign_workspace = Workspace(public_id="ws_agent_foreign", name="Foreign")
        db.add(foreign_workspace)
        db.commit()
        db.refresh(foreign_workspace)
        foreign_admin = User(
            workspace_id=foreign_workspace.id,
            email="foreign-admin@example.com",
            full_name="Foreign Admin",
            hashed_password=hash_password(foreign_password),
            role="admin",
        )
        db.add(foreign_admin)
        db.commit()

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        headers = {"Authorization": f"Bearer {token}"}
        create_response = client.post(
            "/api/v1/agent/runs",
            json={"goal": "Research this lead.", "lead_id": seed.lead_public_id},
            headers=headers,
        )
        actions = client.get(
            "/api/v1/agent/actions", params={"status": "pending"}, headers=headers
        ).json()["items"]
        action_id = actions[0]["action_id"]
        run_id = create_response.json()["run_id"]

        foreign_login = client.post(
            "/api/v1/auth/login",
            json={"email": "foreign-admin@example.com", "password": foreign_password},
        )
        assert foreign_login.status_code == 200
        foreign_headers = {"Authorization": f"Bearer {foreign_login.json()['access_token']}"}

        foreign_get_run = client.get(f"/api/v1/agent/runs/{run_id}", headers=foreign_headers)
        assert foreign_get_run.status_code == 404

        foreign_get_action = client.get(
            f"/api/v1/agent/actions/{action_id}", headers=foreign_headers
        )
        assert foreign_get_action.status_code == 404

        foreign_approve = client.post(
            f"/api/v1/agent/actions/{action_id}/approve", headers=foreign_headers
        )
        assert foreign_approve.status_code == 404

        cancel_missing = client.post(
            "/api/v1/agent/runs/run_does_not_exist/cancel", headers=headers
        )
        assert cancel_missing.status_code == 404

        get_missing_action = client.get(
            "/api/v1/agent/actions/aact_does_not_exist", headers=headers
        )
        assert get_missing_action.status_code == 404

        own_approve = client.post(f"/api/v1/agent/actions/{action_id}/approve", headers=headers)
        assert own_approve.status_code == 200


def test_action_decisions_follow_workspace_permissions_not_role_names(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Regression: the endpoints once checked role names that no longer exist
    (agency_manager/sales_user), so only `admin` could approve. Every role that
    holds `leads:manage` may decide; a role without it may not, and its refusal
    must leave the action pending."""
    _use_stub_runtime(monkeypatch)
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with session_factory() as db:
        workspace = db.query(Workspace).filter_by(public_id="ws_test").one()
        db.add(
            User(
                workspace_id=workspace.id,
                email="legacy@example.com",
                full_name="Legacy Role",
                hashed_password=hash_password("LegacyPass123!"),
                role="sales_user",
            )
        )
        db.commit()

    def login(client, email: str, password: str) -> dict[str, str]:  # type: ignore[no-untyped-def]
        response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert response.status_code == 200
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    with _override_client(session_factory) as client:
        admin_headers = {"Authorization": f"Bearer {_login(client, seed)}"}
        member = login(client, "sales@example.com", "SalesPass123!")
        manager = login(client, "manager@example.com", "ManagerPass123!")
        legacy = login(client, "legacy@example.com", "LegacyPass123!")

        client.post(
            "/api/v1/agent/runs",
            json={"goal": "Research this lead and propose next steps.", "lead_id": seed.lead_public_id},
            headers=admin_headers,
        )
        pending = client.get(
            "/api/v1/agent/actions", params={"status": "pending"}, headers=admin_headers
        ).json()["items"]
        action_id = pending[0]["action_id"]

        denied_approve = client.post(f"/api/v1/agent/actions/{action_id}/approve", headers=legacy)
        denied_reject = client.post(
            f"/api/v1/agent/actions/{action_id}/reject", json={}, headers=legacy
        )
        assert denied_approve.status_code == 403
        assert denied_reject.status_code == 403
        still_pending = client.get(f"/api/v1/agent/actions/{action_id}", headers=admin_headers)
        assert still_pending.json()["status"] == "pending"

        assert (
            client.post(f"/api/v1/agent/actions/{action_id}/approve", headers=member).json()["status"]
            == "executed"
        )
        second = client.get(
            "/api/v1/agent/actions", params={"status": "pending"}, headers=admin_headers
        ).json()["items"][0]["action_id"]
        rejected = client.post(
            f"/api/v1/agent/actions/{second}/reject", json={}, headers=manager
        )
        assert rejected.status_code == 200
        assert rejected.json()["status"] == "rejected"
