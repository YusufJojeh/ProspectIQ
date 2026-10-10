from __future__ import annotations

from typing import Any

import pytest
from agent_api_helpers import start_agent_run
from agent_harness import Decision, Transcript, TranscriptProvider, add_fact
from sqlalchemy import select
from test_agent_behavior_evals import _env
from test_workspace_e2e import _build_session_factory, _login, _override_client, _seed_workspace

import app.modules.agents.runtime as runtime_module
from app.modules.agents.grounding import ground_evidence_refs, observed_evidence_refs
from app.modules.agents.models import AgentEvent, AgentRun, AgentToolCall
from app.modules.leads.models import Lead, LeadNote
from app.modules.users.models import Workspace

# --- Final-answer evidence_refs are backend-grounded ----------------------
#
# The model may only cite evidence refs that (a) appeared in a successful
# tool result of THIS run and (b) resolve to a record owned by this run's
# workspace and lead. Everything else is dropped, with an audit event.


def _ids(session_factory: Any, seed: Any) -> tuple[int, int]:
    with session_factory() as db:
        workspace = db.scalar(select(Workspace).where(Workspace.public_id == seed.workspace_public_id))
        lead = db.scalar(select(Lead).where(Lead.public_id == seed.lead_public_id))
        assert workspace is not None and lead is not None
        return workspace.id, lead.id


def _setup(monkeypatch: pytest.MonkeyPatch, decide: Any) -> tuple[Any, Any, TranscriptProvider]:
    _env(monkeypatch)
    provider = TranscriptProvider(decide)
    monkeypatch.setattr(runtime_module.httpx, "Client", provider)
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    return session_factory, seed, provider


def _run(session_factory: Any, seed: Any, goal: str = "What do we know?") -> dict[str, Any]:
    with _override_client(session_factory) as client:
        headers = {"Authorization": f"Bearer {_login(client, seed)}"}
        response = start_agent_run(client,
            "/api/v1/agent/runs",
            json={"goal": goal, "lead_id": seed.lead_public_id, "profile": "research"},
            headers=headers,
        )
        assert response.status_code == 200
        payload: dict[str, Any] = response.json()
        return payload


def _read_then_cite(extra: list[str], *, cite_observed: bool = True) -> Any:
    def decide(state: Transcript) -> Decision:
        if "get_evidence_graph" not in state.called:
            return "get_evidence_graph", {}
        cited = (state.refs() if cite_observed else []) + extra
        return "final", {"answer": "Summary.", "confidence": 0.6, "evidence_refs": cited}

    return decide


def _dropped_events(session_factory: Any, run_id: str) -> list[AgentEvent]:
    with session_factory() as db:
        run = db.query(AgentRun).filter_by(public_id=run_id).one()
        return list(
            db.query(AgentEvent).filter_by(agent_run_id=run.id, event_type="final_evidence_ref_dropped")
        )


def test_evidence_observed_in_the_run_is_retained(monkeypatch: pytest.MonkeyPatch) -> None:
    session_factory, seed, _ = _setup(monkeypatch, _read_then_cite([]))
    workspace_id, lead_id = _ids(session_factory, seed)
    with session_factory() as db:
        fact = add_fact(db, workspace_id=workspace_id, lead_id=lead_id)

    run = _run(session_factory, seed)

    refs = run["final_answer"]["evidence_refs"]
    assert f"ev_{fact.id}" in refs and all(ref.startswith("ev_") for ref in refs)
    assert not _dropped_events(session_factory, run["run_id"])


def test_nonexistent_evidence_is_removed(monkeypatch: pytest.MonkeyPatch) -> None:
    session_factory, seed, _ = _setup(monkeypatch, _read_then_cite(["ev_999999"], cite_observed=False))

    run = _run(session_factory, seed)

    assert run["final_answer"]["evidence_refs"] == []
    dropped = _dropped_events(session_factory, run["run_id"])
    assert dropped and dropped[0].payload_json["dropped"] == ["ev_999999"]
    # One invented ref never fails the run.
    assert run["status"] == "completed"


def test_mixed_real_and_fake_refs_keep_only_the_real(monkeypatch: pytest.MonkeyPatch) -> None:
    session_factory, seed, _ = _setup(
        monkeypatch, _read_then_cite(["evidence_fake_999", "rce_madeup"])
    )
    workspace_id, lead_id = _ids(session_factory, seed)
    with session_factory() as db:
        real = add_fact(db, workspace_id=workspace_id, lead_id=lead_id)

    run = _run(session_factory, seed)

    refs = run["final_answer"]["evidence_refs"]
    assert f"ev_{real.id}" in refs
    assert "evidence_fake_999" not in refs and "rce_madeup" not in refs
    assert set(_dropped_events(session_factory, run["run_id"])[0].payload_json["dropped"]) == {
        "evidence_fake_999",
        "rce_madeup",
    }


def test_evidence_of_another_lead_is_removed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A real fact id that belongs to a different lead is not citable, even
    if the model guesses the id correctly."""
    session_factory, seed, _ = _setup(monkeypatch, lambda state: ("final", {}))
    workspace_id, lead_id = _ids(session_factory, seed)
    with session_factory() as db:
        other = add_fact(db, workspace_id=workspace_id, lead_id=lead_id + 1000)
    provider = TranscriptProvider(_read_then_cite([f"ev_{other.id}"], cite_observed=False))
    monkeypatch.setattr(runtime_module.httpx, "Client", provider)

    run = _run(session_factory, seed)

    assert run["final_answer"]["evidence_refs"] == []


def test_foreign_workspace_ref_is_dropped_even_if_it_reached_a_tool_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Defence in depth: tools are lead-scoped so a foreign ref cannot be
    observed. Simulate that invariant breaking -- a persisted tool result
    containing another workspace's fact -- and the ownership check still
    removes it."""
    session_factory, seed, _ = _setup(monkeypatch, _read_then_cite([]))
    workspace_id, lead_id = _ids(session_factory, seed)
    with session_factory() as db:
        own = add_fact(db, workspace_id=workspace_id, lead_id=lead_id)
        foreign = add_fact(db, workspace_id=workspace_id + 500, lead_id=lead_id)

    run = _run(session_factory, seed)
    with session_factory() as db:
        run_row = db.query(AgentRun).filter_by(public_id=run["run_id"]).one()
        call = db.query(AgentToolCall).filter_by(agent_run_id=run_row.id).first()
        assert call is not None
        call.result_json = {"sources": [{"evidence_ref": f"ev_{foreign.id}"}, {"evidence_ref": f"ev_{own.id}"}]}
        db.commit()
        assert f"ev_{foreign.id}" in observed_evidence_refs(db, run_row.id)
        kept, dropped = ground_evidence_refs(
            db,
            agent_run_id=run_row.id,
            workspace_id=run_row.workspace_id,
            lead_id=run_row.lead_id,
            requested=[f"ev_{foreign.id}", f"ev_{own.id}"],
        )
    assert kept == [f"ev_{own.id}"]
    assert dropped == [f"ev_{foreign.id}"]


def test_evidence_seen_before_a_pause_survives_same_run_resume(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def decide(state: Transcript) -> Decision:
        if "get_evidence_graph" not in state.called:
            return "get_evidence_graph", {}
        if "add_lead_note" not in state.called:
            return "add_lead_note", {"note": "Evidence reviewed."}
        return "final", {"answer": "Noted.", "confidence": 0.6, "evidence_refs": state.refs()}

    session_factory, seed, _ = _setup(monkeypatch, decide)
    workspace_id, lead_id = _ids(session_factory, seed)
    with session_factory() as db:
        fact = add_fact(db, workspace_id=workspace_id, lead_id=lead_id)

    with _override_client(session_factory) as client:
        headers = {"Authorization": f"Bearer {_login(client, seed)}"}
        run = start_agent_run(client,
            "/api/v1/agent/runs",
            json={"goal": "Review and note.", "lead_id": seed.lead_public_id, "profile": "research"},
            headers=headers,
        ).json()
        assert run["status"] == "waiting_for_approval"
        action = client.get("/api/v1/agent/actions", params={"status": "pending"}, headers=headers).json()["items"][0]
        client.post(f"/api/v1/agent/actions/{action['action_id']}/approve", headers=headers)
        final = client.get(f"/api/v1/agent/runs/{run['run_id']}", headers=headers).json()

    assert final["status"] == "completed"
    assert f"ev_{fact.id}" in final["final_answer"]["evidence_refs"]
    with session_factory() as db:
        assert db.query(AgentRun).count() == 1
        assert db.query(LeadNote).count() == 1


def test_no_observed_evidence_means_no_final_refs(monkeypatch: pytest.MonkeyPatch) -> None:
    def decide(state: Transcript) -> Decision:
        return "final", {"answer": "Guessing.", "confidence": 0.9, "evidence_refs": ["ev_1", "ev_2"]}

    session_factory, seed, _ = _setup(monkeypatch, decide)
    workspace_id, lead_id = _ids(session_factory, seed)
    with session_factory() as db:
        # Real facts of this lead exist, but the run never looked at them.
        add_fact(db, workspace_id=workspace_id, lead_id=lead_id)

    run = _run(session_factory, seed)

    assert run["final_answer"]["evidence_refs"] == []


def test_model_cannot_fabricate_evidence_for_an_unsupported_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The model asserts online booking exists and invents a citation for
    it. The claim text is the model's, but it leaves with zero evidence
    attached -- the answer is visibly unsupported rather than falsely
    grounded."""
    session_factory, seed, _ = _setup(
        monkeypatch,
        _read_then_cite(["ev_424242", "rce_booking_enabled"], cite_observed=False),
    )
    workspace_id, lead_id = _ids(session_factory, seed)
    with session_factory() as db:
        add_fact(db, workspace_id=workspace_id, lead_id=lead_id)

    run = _run(session_factory, seed, goal="Does the lead offer online booking?")

    assert run["final_answer"]["evidence_refs"] == []
    assert len(_dropped_events(session_factory, run["run_id"])[0].payload_json["dropped"]) == 2
