from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker
from test_lead_refresh_orchestrator import (
    _build_session_factory,
    _FakeRefreshProviderService,
    _seed_refresh_target,
)

from app.modules.audit_logs.models import AuditLog
from app.modules.leads.models import Lead
from app.workers.orchestration.lead_refresh import LeadRefreshOrchestrator


def test_run_for_lead_records_refreshed_audit() -> None:
    session_factory = _build_session_factory()
    workspace_id, user_id, lead_id = _seed_refresh_target(session_factory)
    with session_factory() as db:
        lead = db.get(Lead, lead_id)
        assert lead is not None
        lead_public_id = lead.public_id

    provider = _FakeRefreshProviderService(
        maps_place_payload={
            "place_results": {
                "title": "Acme Dental",
                "address": "Bagdat Avenue, Istanbul, Turkey",
                "phone": "+90 555 111 2233",
                "website": "https://acmedental.example",
                "rating": 4.7,
                "reviews": 18,
                "gps_coordinates": {"latitude": 41.01, "longitude": 29.05},
                "data_id": "maps-acme-1",
                "type": "Dentist",
            }
        }
    )
    orch = LeadRefreshOrchestrator(session_factory=session_factory, provider_service=provider)
    orch.run_for_lead(
        workspace_id=workspace_id,
        lead_public_id=lead_public_id,
        actor_user_id=user_id,
    )

    with session_factory() as db:
        n = db.scalar(
            select(func.count(AuditLog.id)).where(AuditLog.event_name == "lead.refreshed")
        )
        assert n == 1


def test_run_for_lead_records_failure_audit_when_refresh_raises(monkeypatch) -> None:
    session_factory = _build_session_factory()
    workspace_id, user_id, lead_id = _seed_refresh_target(session_factory)
    with session_factory() as db:
        lead = db.get(Lead, lead_id)
        assert lead is not None
        lead_public_id = lead.public_id

    def _boom(self, db, *, lead, requested_by_user_id):  # noqa: ANN001
        raise RuntimeError("simulated provider failure")

    monkeypatch.setattr(LeadRefreshOrchestrator, "refresh", _boom)

    orch = LeadRefreshOrchestrator(session_factory=session_factory, provider_service=None)
    orch.run_for_lead(
        workspace_id=workspace_id,
        lead_public_id=lead_public_id,
        actor_user_id=user_id,
    )

    with session_factory() as db:
        n = db.scalar(
            select(func.count(AuditLog.id)).where(AuditLog.event_name == "lead.refresh_failed")
        )
        assert n == 1


def test_run_for_lead_invokes_session_factory() -> None:
    """run_for_lead must obtain its own DB session from session_factory (not a request Session)."""
    session_factory = _build_session_factory()
    workspace_id, user_id, lead_id = _seed_refresh_target(session_factory)
    with session_factory() as db:
        lead = db.get(Lead, lead_id)
        assert lead is not None
        lead_public_id = lead.public_id

    provider = _FakeRefreshProviderService(
        maps_place_payload={
            "place_results": {
                "title": "Acme Dental",
                "address": "Bagdat Avenue, Istanbul, Turkey",
                "phone": "+90 555 111 2233",
                "website": "https://acmedental.example",
                "rating": 4.7,
                "reviews": 18,
                "gps_coordinates": {"latitude": 41.01, "longitude": 29.05},
                "data_id": "maps-acme-1",
                "type": "Dentist",
            }
        }
    )

    class _TrackCalls:
        def __init__(self, inner: sessionmaker[Session]) -> None:
            self._inner = inner
            self.calls = 0

        def __call__(self):
            self.calls += 1
            return self._inner()

    tracker = _TrackCalls(session_factory)
    orch = LeadRefreshOrchestrator(
        session_factory=tracker,
        provider_service=provider,
    )
    orch.run_for_lead(
        workspace_id=workspace_id,
        lead_public_id=lead_public_id,
        actor_user_id=user_id,
    )
    assert tracker.calls >= 1
