from __future__ import annotations

from test_workspace_e2e import (
    _build_session_factory,
    _E2EAnalysisAdapter,
    _login,
    _override_client,
    _seed_workspace,
)

from app.modules.ai_analysis.service import RuntimeCandidate
from app.modules.signals.models import LeadSignal
from app.modules.signals.repository import LeadSignalRepository


def _patch_analysis(monkeypatch) -> None:
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


def test_lead_list_exposes_top_signal_summary_after_recompute() -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        headers = {"Authorization": f"Bearer {token}"}

        recompute = client.post(
            f"/api/v1/leads/{seed.lead_public_id}/signals/recompute",
            headers=headers,
        )
        assert recompute.status_code == 200

        list_response = client.get("/api/v1/leads", headers=headers)
        assert list_response.status_code == 200
        rows = list_response.json()["items"]
        row = next(item for item in rows if item["public_id"] == seed.lead_public_id)

        assert row["signals_count"] >= 1
        assert row["top_signal_type"] is not None
        assert row["top_signal_evidence"]
        assert row["top_signal_strength"] is not None


def test_signal_summary_is_strictly_workspace_scoped() -> None:
    session_factory = _build_session_factory()
    repository = LeadSignalRepository()

    with session_factory() as db:
        # Same lead_id value under two different workspaces; only workspace 1's
        # signals must surface for a workspace-1 query.
        db.add_all(
            [
                LeadSignal(
                    workspace_id=1,
                    lead_id=99,
                    signal_type="ready_for_outreach",
                    signal_strength=0.9,
                    evidence_text="Workspace 1 signal.",
                ),
                LeadSignal(
                    workspace_id=2,
                    lead_id=99,
                    signal_type="no_website",
                    signal_strength=1.0,
                    evidence_text="Workspace 2 signal must not leak.",
                ),
            ]
        )
        db.commit()

        summaries = repository.summaries_for_leads(db, workspace_id=1, lead_ids=[99])
        assert set(summaries) == {99}
        assert summaries[99].top_signal_type == "ready_for_outreach"
        assert summaries[99].signals_count == 1
        assert "leak" not in summaries[99].top_signal_evidence


def test_ai_evidence_is_persisted_and_feedback_is_recorded(monkeypatch) -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    _patch_analysis(monkeypatch)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        headers = {"Authorization": f"Bearer {token}"}

        # Recompute signals first so the evidence builder has grounded signals.
        client.post(
            f"/api/v1/leads/{seed.lead_public_id}/signals/recompute",
            headers=headers,
        )

        generate = client.post(
            f"/api/v1/ai-analysis/leads/{seed.lead_public_id}/generate",
            headers=headers,
        )
        assert generate.status_code == 200
        snapshot_id = generate.json()["public_id"]

        evidence = client.get(
            f"/api/v1/leads/{seed.lead_public_id}/ai-evidence",
            headers=headers,
        )
        assert evidence.status_code == 200
        evidence_body = evidence.json()
        assert evidence_body["snapshot_public_id"] == snapshot_id
        assert len(evidence_body["items"]) >= 1
        first = evidence_body["items"][0]
        assert first["evidence_text"]
        assert 0.0 <= first["confidence"] <= 1.0

        feedback = client.post(
            f"/api/v1/ai-analysis/{snapshot_id}/feedback",
            headers=headers,
            json={"rating": "useful", "correction_text": "Looks accurate."},
        )
        assert feedback.status_code == 200
        assert feedback.json()["rating"] == "useful"
        assert feedback.json()["snapshot_public_id"] == snapshot_id


def test_ai_feedback_rejects_unknown_snapshot(monkeypatch) -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    _patch_analysis(monkeypatch)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        response = client.post(
            "/api/v1/ai-analysis/ais_does_not_exist/feedback",
            headers={"Authorization": f"Bearer {token}"},
            json={"rating": "not_useful"},
        )
        assert response.status_code == 404
