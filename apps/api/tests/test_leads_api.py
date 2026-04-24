from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from test_workspace_e2e import _build_session_factory, _login, _override_client, _seed_workspace

from app.modules.leads.models import Lead
from app.modules.users.models import Workspace


def test_list_leads_endpoint_filters_by_status_and_sorts_newest() -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with session_factory() as db:
        workspace = db.scalar(
            select(Workspace).where(Workspace.public_id == seed.workspace_public_id)
        )
        assert workspace is not None
        db.add_all(
            [
                Lead(
                    workspace_id=workspace.id,
                    company_name="Later Reviewed Lead",
                    city="Istanbul",
                    review_count=8,
                    data_completeness=0.52,
                    data_confidence=0.61,
                    has_website=False,
                    status="reviewed",
                    created_at=datetime.now(tz=UTC) + timedelta(seconds=10),
                    updated_at=datetime.now(tz=UTC) + timedelta(seconds=10),
                ),
                Lead(
                    workspace_id=workspace.id,
                    company_name="Qualified Lead",
                    city="Istanbul",
                    review_count=12,
                    data_completeness=0.68,
                    data_confidence=0.71,
                    has_website=True,
                    status="qualified",
                ),
            ]
        )
        db.commit()

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        response = client.get(
            "/api/v1/leads?page_size=50&status=reviewed&sort=newest",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert [item["company_name"] for item in payload["items"]] == [
        "Later Reviewed Lead",
        "Acme Dental",
    ]
    assert all(item["status"] == "reviewed" for item in payload["items"])


def test_update_status_endpoint_creates_status_and_note_activity_entries() -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        headers = {"Authorization": f"Bearer {token}"}
        update_response = client.patch(
            f"/api/v1/leads/{seed.lead_public_id}/status",
            headers=headers,
            json={"status": "contacted", "note": "Reached out after qualification review."},
        )
        activity_response = client.get(
            f"/api/v1/leads/{seed.lead_public_id}/activity",
            headers=headers,
        )

    assert update_response.status_code == 200
    assert update_response.json()["status"] == "contacted"
    assert activity_response.status_code == 200
    activity_items = activity_response.json()["items"]
    assert any(
        item["entry_type"] == "status_change" and item["to_status"] == "contacted"
        for item in activity_items
    )
    assert any(
        item["entry_type"] == "note"
        and item["note"] == "Reached out after qualification review."
        for item in activity_items
    )


def test_lead_endpoints_reject_foreign_workspace_leads() -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with session_factory() as db:
        foreign_workspace = Workspace(public_id="ws_foreign", name="Foreign Workspace")
        db.add(foreign_workspace)
        db.commit()
        db.refresh(foreign_workspace)

        foreign_lead = Lead(
            workspace_id=foreign_workspace.id,
            company_name="Foreign Lead",
            city="Ankara",
            review_count=3,
            data_completeness=0.34,
            data_confidence=0.4,
            has_website=False,
            status="new",
        )
        db.add(foreign_lead)
        db.commit()
        db.refresh(foreign_lead)
        foreign_public_id = foreign_lead.public_id

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        headers = {"Authorization": f"Bearer {token}"}
        get_response = client.get(
            f"/api/v1/leads/{foreign_public_id}",
            headers=headers,
        )
        update_response = client.patch(
            f"/api/v1/leads/{foreign_public_id}/status",
            headers=headers,
            json={"status": "qualified"},
        )

    assert get_response.status_code == 404
    assert update_response.status_code == 404
