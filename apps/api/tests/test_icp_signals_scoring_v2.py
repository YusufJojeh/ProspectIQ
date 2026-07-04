from __future__ import annotations

from sqlalchemy import select
from test_workspace_e2e import _build_session_factory, _login, _override_client, _seed_workspace

from app.modules.icp.models import IcpProfile
from app.modules.leads.models import Lead
from app.modules.provider_serpapi.models import ProviderNormalizedFact
from app.modules.scoring.schemas import ScoringThresholds, ScoringWeights
from app.modules.scoring.service import ScoringEngine
from app.modules.signals.service import LeadSignalDetectorService
from app.modules.users.models import User, Workspace
from app.shared.dto.lead_facts import NormalizedLeadFacts
from app.shared.enums.jobs import LeadScoreBand


def test_icp_profile_crud_and_match_api_are_workspace_scoped() -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        headers = {"Authorization": f"Bearer {token}"}
        create_response = client.post(
            "/api/v1/icp-profiles",
            headers=headers,
            json={
                "name": "Dental growth ICP",
                "target_industries": ["Dentist"],
                "target_cities": ["Istanbul"],
                "min_rating": 4.0,
                "min_reviews": 10,
                "website_preference": "any",
                "required_signals": ["ready_for_outreach"],
                "excluded_keywords": ["closed"],
            },
        )
        assert create_response.status_code == 201
        profile_id = create_response.json()["public_id"]

        list_response = client.get("/api/v1/icp-profiles", headers=headers)
        assert list_response.status_code == 200
        assert [item["public_id"] for item in list_response.json()["items"]] == [profile_id]

        signals_response = client.post(
            f"/api/v1/leads/{seed.lead_public_id}/signals/recompute",
            headers=headers,
        )
        assert signals_response.status_code == 200
        assert any(
            item["signal_type"] == "ready_for_outreach"
            for item in signals_response.json()["items"]
        )

        match_response = client.post(
            f"/api/v1/icp-profiles/{profile_id}/match/{seed.lead_public_id}",
            headers=headers,
        )
        assert match_response.status_code == 200
        payload = match_response.json()
        assert payload["matched"] is True
        assert payload["fit_score"] >= 60


def test_icp_match_rejects_foreign_workspace_lead() -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with session_factory() as db:
        owner = db.scalar(select(User).where(User.email == seed.admin_email))
        assert owner is not None
        profile = IcpProfile(
            workspace_id=owner.workspace_id,
            created_by_user_id=owner.id,
            name="Scoped ICP",
            target_industries=["Clinic"],
            target_cities=["Istanbul"],
            website_preference="any",
            required_signals=[],
            excluded_keywords=[],
        )
        db.add(profile)
        foreign_workspace = Workspace(public_id="ws_foreign_icp", name="Foreign")
        db.add(foreign_workspace)
        db.commit()
        db.refresh(foreign_workspace)
        foreign_lead = Lead(
            workspace_id=foreign_workspace.id,
            company_name="Foreign Clinic",
            city="Istanbul",
            review_count=20,
            rating=4.6,
            data_completeness=0.8,
            data_confidence=0.8,
            has_website=False,
            status="new",
        )
        db.add(foreign_lead)
        db.commit()
        db.refresh(profile)
        db.refresh(foreign_lead)
        profile_id = profile.public_id
        foreign_lead_id = foreign_lead.public_id

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        response = client.post(
            f"/api/v1/icp-profiles/{profile_id}/match/{foreign_lead_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 404


def test_signal_detector_generates_expected_sales_signals() -> None:
    lead = Lead(
        workspace_id=1,
        company_name="North Clinic",
        category="Clinic",
        city="Istanbul",
        phone="+90 555 100 2000",
        review_count=80,
        rating=4.4,
        data_completeness=0.68,
        data_confidence=0.78,
        has_website=False,
        status="new",
    )
    fact = ProviderNormalizedFact(
        workspace_id=1,
        lead_id=1,
        provider_fetch_id=1,
        source_type="maps_search",
        company_name="North Clinic",
        category="Clinic",
        city="Istanbul",
        phone="+90 555 100 2000",
        review_count=80,
        rating=4.4,
        confidence=0.78,
        completeness=0.68,
        facts_json={"knowledge_graph_present": True},
    )

    detected = LeadSignalDetectorService().detect(lead, [fact])
    signal_types = {signal.signal_type for signal in detected}

    assert {"no_website", "high_reviews", "high_local_visibility", "ready_for_outreach"}.issubset(
        signal_types
    )


def test_scoring_v2_uses_icp_match_and_signals_for_priority_band() -> None:
    engine = ScoringEngine()

    class _Match:
        fit_score = 88.0

    class _Signal:
        def __init__(self, signal_type: str, signal_strength: float) -> None:
            self.signal_type = signal_type
            self.signal_strength = signal_strength

    result = engine.evaluate(
        NormalizedLeadFacts(
            company_name="North Clinic",
            city="Istanbul",
            category="Clinic",
            review_count=80,
            rating=4.4,
            data_completeness=0.78,
            data_confidence=0.82,
            has_website=False,
            phone_present=True,
            address_present=True,
            category_clarity=1.0,
            local_presence_signal=0.85,
            weak_website_signal=1.0,
            digital_footprint_gap=0.8,
            source_agreement=0.8,
            evidence_sources_count=2,
        ),
        weights=ScoringWeights(),
        thresholds=ScoringThresholds(),
        icp_match=_Match(),  # type: ignore[arg-type]
        lead_signals=[
            _Signal("no_website", 1.0),  # type: ignore[list-item]
            _Signal("high_reviews", 0.9),  # type: ignore[list-item]
            _Signal("high_local_visibility", 0.9),  # type: ignore[list-item]
            _Signal("ready_for_outreach", 0.85),  # type: ignore[list-item]
        ],
    )

    assert result.band in {LeadScoreBand.HOT_LEAD, LeadScoreBand.WARM_LEAD}
    assert result.fit_score == 88.0
    assert result.final_priority_score is not None
    assert {item.key for item in result.breakdown} >= {
        "fit_score",
        "need_score",
        "urgency_score",
        "reachability_score",
    }
