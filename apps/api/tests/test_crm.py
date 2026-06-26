from __future__ import annotations

from sqlalchemy import select
from test_workspace_e2e import _build_session_factory, _login, _override_client, _seed_workspace

from app.modules.campaigns.models import Campaign, CampaignLead
from app.modules.crm.models import CrmActivity, CrmDeal
from app.modules.leads.models import Lead
from app.modules.users.models import User, Workspace


def test_crm_default_pipeline_lead_deal_move_and_activity() -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        headers = {"Authorization": f"Bearer {token}"}

        pipelines_response = client.get("/api/v1/crm/pipelines", headers=headers)
        assert pipelines_response.status_code == 200
        pipeline = pipelines_response.json()["items"][0]
        assert [stage["name"] for stage in pipeline["stages"]] == [
            "New Opportunity",
            "Contacted",
            "Interested",
            "Proposal / Offer",
            "Negotiation",
            "Won",
            "Lost",
        ]

        deal_response = client.post(
            f"/api/v1/leads/{seed.lead_public_id}/create-deal",
            headers=headers,
            json={},
        )
        assert deal_response.status_code == 201
        deal_id = deal_response.json()["public_id"]

        duplicate_response = client.post(
            f"/api/v1/leads/{seed.lead_public_id}/create-deal",
            headers=headers,
            json={},
        )
        assert duplicate_response.status_code == 409

        contacted_stage_id = pipeline["stages"][1]["public_id"]
        move_response = client.post(
            f"/api/v1/crm/deals/{deal_id}/move",
            headers=headers,
            json={"stage_id": contacted_stage_id},
        )
        assert move_response.status_code == 200
        assert move_response.json()["stage_name"] == "Contacted"

        activity_response = client.post(
            f"/api/v1/crm/deals/{deal_id}/activities",
            headers=headers,
            json={
                "activity_type": "follow_up",
                "title": "Call owner",
                "note": "Offline demo follow-up only.",
            },
        )
        assert activity_response.status_code == 200
        activity_id = activity_response.json()["public_id"]

        complete_response = client.post(
            f"/api/v1/crm/deals/{deal_id}/activities/{activity_id}/complete",
            headers=headers,
        )
        detail_response = client.get(f"/api/v1/crm/deals/{deal_id}", headers=headers)

    assert complete_response.status_code == 200
    assert complete_response.json()["completed_at"] is not None
    assert detail_response.status_code == 200
    assert detail_response.json()["lead"]["public_id"] == seed.lead_public_id
    assert len(detail_response.json()["activities"]) >= 2

    with session_factory() as db:
        deal = db.scalar(select(CrmDeal).where(CrmDeal.public_id == deal_id))
        assert deal is not None
        assert deal.stage_id is not None
        assert db.scalar(select(CrmActivity).where(CrmActivity.public_id == activity_id)) is not None


def test_crm_campaign_create_deals_and_workspace_scoping() -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with session_factory() as db:
        lead = db.scalar(select(Lead).where(Lead.public_id == seed.lead_public_id))
        owner = db.scalar(select(User).where(User.email == seed.admin_email))
        assert lead is not None
        assert owner is not None
        campaign = Campaign(
            workspace_id=lead.workspace_id,
            name="CRM conversion campaign",
            created_by_user_id=owner.id,
        )
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
        db.add(CampaignLead(campaign_id=campaign.id, lead_id=lead.id, status="added"))
        db.commit()
        campaign_id = campaign.public_id

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(
            f"/api/v1/campaigns/{campaign_id}/create-deals",
            headers=headers,
            json={},
        )
        second_response = client.post(
            f"/api/v1/campaigns/{campaign_id}/create-deals",
            headers=headers,
            json={},
        )

    assert response.status_code == 200
    assert response.json()["created_count"] == 1
    assert second_response.status_code == 200
    assert second_response.json()["skipped_count"] == 1

    with session_factory() as db:
        foreign_workspace = Workspace(public_id="ws_foreign_crm", name="Foreign CRM")
        db.add(foreign_workspace)
        db.commit()
        db.refresh(foreign_workspace)
        deal = db.scalar(select(CrmDeal))
        assert deal is not None
        deal.workspace_id = foreign_workspace.id
        db.add(deal)
        db.commit()
        deal_id = deal.public_id

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        response = client.get(
            f"/api/v1/crm/deals/{deal_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 404
