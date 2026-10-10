from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session
from test_workspace_e2e import _build_session_factory, _login, _override_client, _seed_workspace

from app.modules.leads.models import Lead
from app.modules.research.models import ResearchChangeEvent, ResearchRun
from app.modules.users.models import Workspace


def _add_run(db: Session, *, workspace_id: int, lead_id: int, offset: int) -> ResearchRun:
    run = ResearchRun(
        workspace_id=workspace_id,
        lead_id=lead_id,
        depth="deep" if offset else "quick",
        mode="planned",
        status="ok",
        providers_used_json=["tavily"],
        evidence_confidence=0.8,
        research_coverage=0.7,
        created_at=datetime.now(tz=UTC) + timedelta(minutes=offset),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def test_research_history_is_paginated_newest_first_and_run_scoped(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    with session_factory() as db:
        workspace = db.scalar(select(Workspace).where(Workspace.public_id == seed.workspace_public_id))
        lead = db.scalar(select(Lead).where(Lead.public_id == seed.lead_public_id))
        assert workspace is not None and lead is not None
        first = _add_run(db, workspace_id=workspace.id, lead_id=lead.id, offset=0)
        second = _add_run(db, workspace_id=workspace.id, lead_id=lead.id, offset=1)
        db.add_all(
            [
                ResearchChangeEvent(
                    workspace_id=workspace.id,
                    lead_id=lead.id,
                    current_research_run_id=first.id,
                    claim_type="rating",
                    previous_value="4.6",
                    new_value="3.9",
                    event_type="rating_changed",
                    direction="declined",
                    significance=0.56,
                    explanation="Rating declined.",
                ),
                ResearchChangeEvent(
                    workspace_id=workspace.id,
                    lead_id=lead.id,
                    current_research_run_id=second.id,
                    claim_type="online_booking",
                    previous_value="false",
                    new_value="true",
                    event_type="digital_capability_changed",
                    direction="improved",
                    significance=0.6,
                    explanation="Booking became available.",
                ),
            ]
        )
        db.commit()
        newest_public_id = second.public_id

    monkeypatch.setattr(
        "app.modules.research.orchestrator.ResearchOrchestrator.run",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("provider invoked")),
    )
    monkeypatch.setattr(
        "app.modules.research.delta.ChangeExplainer.explain",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("LLM invoked")),
    )
    with _override_client(session_factory) as client:
        token = _login(client, seed)
        response = client.get(
            f"/api/v1/leads/{seed.lead_public_id}/research-history?page=1&per_page=1",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["pagination"] == {"page": 1, "per_page": 1, "total": 2}
    assert payload["items"][0]["run_id"] == newest_public_id
    assert [change["claim_type"] for change in payload["items"][0]["changes"]] == [
        "online_booking"
    ]
    assert "providers_used_json" not in payload["items"][0]


def test_research_history_empty_and_missing_or_foreign_leads_return_safely() -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    with session_factory() as db:
        foreign_workspace = Workspace(public_id="ws_history_foreign", name="Foreign")
        db.add(foreign_workspace)
        db.commit()
        db.refresh(foreign_workspace)
        foreign_lead = Lead(
            workspace_id=foreign_workspace.id,
            company_name="Foreign Lead",
            review_count=0,
            data_completeness=0.1,
            data_confidence=0.1,
            has_website=False,
            status="new",
        )
        db.add(foreign_lead)
        db.commit()
        db.refresh(foreign_lead)
        foreign_id = foreign_lead.public_id

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        headers = {"Authorization": f"Bearer {token}"}
        empty = client.get(
            f"/api/v1/leads/{seed.lead_public_id}/research-history", headers=headers
        )
        missing = client.get("/api/v1/leads/lead_missing/research-history", headers=headers)
        foreign = client.get(f"/api/v1/leads/{foreign_id}/research-history", headers=headers)

    assert empty.status_code == 200
    assert empty.json()["items"] == []
    assert empty.json()["pagination"]["total"] == 0
    assert missing.status_code == 404
    assert foreign.status_code == 404
