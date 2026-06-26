from __future__ import annotations

from sqlalchemy import func, select
from test_workspace_e2e import _build_session_factory, _login, _override_client, _seed_workspace

from app.core.config import clear_settings_cache
from app.modules.ai_analysis.service import RuntimeCandidate
from app.modules.campaigns.models import Campaign, CampaignLead, OutreachEvent, SequenceStep
from app.modules.leads.models import Lead
from app.modules.outreach.models import OutreachMessage
from app.modules.users.models import Workspace


class _CampaignAnalysisAdapter:
    def analyze(self, payload: object) -> dict[str, object]:
        company_name = getattr(getattr(payload, "local_business", None), "company_name", "Lead")
        return {
            "summary": f"{company_name} has enough evidence for conservative outreach.",
            "weaknesses": ["Website conversion evidence is limited."],
            "opportunities": ["Improve local visibility using the strongest stored proof points."],
            "recommended_services": ["Local SEO Sprint"],
            "outreach_subject": f"Evidence-backed ideas for {company_name}",
            "outreach_message": (
                f"Hi {company_name}, we found a stored signal that may support a concise growth audit."
            ),
            "confidence": 0.82,
            "outreach_angle": "Lead with the strongest stored evidence and avoid unsupported claims.",
            "evidence_used": ["Stored score breakdown", "Provider facts"],
        }


def _patch_analysis(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.modules.ai_analysis.service.AIAnalysisService._resolve_runtime_candidates",
        lambda self: [
            RuntimeCandidate(
                adapter=_CampaignAnalysisAdapter(),
                provider_name="test",
                model_name="campaign-test-model",
            )
        ],
    )


def test_campaign_crud_and_workspace_scoping(monkeypatch) -> None:
    _patch_analysis(monkeypatch)
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        headers = {"Authorization": f"Bearer {token}"}

        create_response = client.post(
            "/api/v1/campaigns",
            headers=headers,
            json={"name": "June qualified leads", "description": "Graduation demo sequence"},
        )
        assert create_response.status_code == 201
        campaign_id = create_response.json()["public_id"]

        list_response = client.get("/api/v1/campaigns", headers=headers)
        get_response = client.get(f"/api/v1/campaigns/{campaign_id}", headers=headers)
        patch_response = client.patch(
            f"/api/v1/campaigns/{campaign_id}",
            headers=headers,
            json={"status": "active", "name": "June outreach"},
        )

    assert list_response.status_code == 200
    assert list_response.json()["items"][0]["name"] == "June qualified leads"
    assert get_response.status_code == 200
    assert get_response.json()["events"][0]["event_type"] == "campaign.created"
    assert patch_response.status_code == 200
    assert patch_response.json()["status"] == "active"

    with session_factory() as db:
        foreign_workspace = Workspace(public_id="ws_foreign_campaign", name="Foreign Workspace")
        db.add(foreign_workspace)
        db.commit()
        db.refresh(foreign_workspace)
        campaign = db.scalar(select(Campaign).where(Campaign.public_id == campaign_id))
        assert campaign is not None
        campaign.workspace_id = foreign_workspace.id
        db.add(campaign)
        db.commit()

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        response = client.get(
            f"/api/v1/campaigns/{campaign_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 404


def test_campaign_leads_sequence_drafts_and_events(monkeypatch) -> None:
    _patch_analysis(monkeypatch)
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        headers = {"Authorization": f"Bearer {token}"}

        create_response = client.post(
            "/api/v1/campaigns",
            headers=headers,
            json={"name": "Priority dental sequence"},
        )
        assert create_response.status_code == 201
        campaign_id = create_response.json()["public_id"]

        add_response = client.post(
            f"/api/v1/campaigns/{campaign_id}/leads",
            headers=headers,
            json={"lead_ids": [seed.lead_public_id]},
        )
        sequence_response = client.post(
            f"/api/v1/campaigns/{campaign_id}/generate-sequence",
            headers=headers,
        )
        drafts_response = client.post(
            f"/api/v1/campaigns/{campaign_id}/generate-drafts",
            headers=headers,
            json={},
        )
        events_response = client.get(f"/api/v1/campaigns/{campaign_id}/events", headers=headers)

    assert add_response.status_code == 200
    assert add_response.json()["lead_count"] == 1
    assert sequence_response.status_code == 200
    assert [item["delay_days"] for item in sequence_response.json()] == [0, 3, 7]
    assert drafts_response.status_code == 200
    assert drafts_response.json()["created_count"] == 3
    assert events_response.status_code == 200
    event_types = {item["event_type"] for item in events_response.json()}
    assert {
        "campaign.created",
        "campaign.lead_added",
        "campaign.sequence_generated",
        "campaign.draft_generated",
    }.issubset(event_types)

    with session_factory() as db:
        campaign = db.scalar(select(Campaign).where(Campaign.public_id == campaign_id))
        lead = db.scalar(select(Lead).where(Lead.public_id == seed.lead_public_id))
        assert campaign is not None
        assert lead is not None
        assert (
            db.scalar(select(func.count(SequenceStep.id)).where(SequenceStep.campaign_id == campaign.id))
            == 3
        )
        assert (
            db.scalar(select(func.count(CampaignLead.id)).where(CampaignLead.campaign_id == campaign.id))
            == 1
        )
        assert (
            db.scalar(select(func.count(OutreachMessage.id)).where(OutreachMessage.lead_id == lead.id))
            == 3
        )
        assert (
            db.scalar(
                select(func.count(OutreachEvent.id)).where(
                    OutreachEvent.campaign_id == campaign.id,
                    OutreachEvent.event_type == "campaign.draft_generated",
                )
            )
            == 3
        )

    clear_settings_cache()


def test_campaign_rejects_foreign_workspace_lead(monkeypatch) -> None:
    _patch_analysis(monkeypatch)
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with session_factory() as db:
        foreign_workspace = Workspace(public_id="ws_foreign_lead", name="Foreign Workspace")
        db.add(foreign_workspace)
        db.commit()
        db.refresh(foreign_workspace)
        foreign_lead = Lead(
            workspace_id=foreign_workspace.id,
            company_name="Foreign Lead",
            city="Ankara",
            review_count=1,
            data_completeness=0.4,
            data_confidence=0.5,
            has_website=False,
        )
        db.add(foreign_lead)
        db.commit()
        db.refresh(foreign_lead)
        foreign_lead_id = foreign_lead.public_id

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        headers = {"Authorization": f"Bearer {token}"}
        campaign_response = client.post(
            "/api/v1/campaigns",
            headers=headers,
            json={"name": "Scoped campaign"},
        )
        assert campaign_response.status_code == 201
        response = client.post(
            f"/api/v1/campaigns/{campaign_response.json()['public_id']}/leads",
            headers=headers,
            json={"lead_ids": [foreign_lead_id]},
        )

    assert response.status_code == 404
