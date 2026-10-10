from __future__ import annotations

from typing import Any

import pytest
from agent_api_helpers import start_agent_run
from agent_harness import (
    Decision,
    Transcript,
    TranscriptProvider,
    add_research_run_with_change,
)
from sqlalchemy import select
from test_agent_behavior_evals import _env, _seed_knowledge
from test_workspace_e2e import _build_session_factory, _login, _override_client, _seed_workspace

import app.modules.agents.runtime as runtime_module
import app.modules.agents.tool_executor as executor_module
from app.modules.agents.models import AgentAction, AgentEvent, AgentRun
from app.modules.leads.models import Lead, LeadNote
from app.modules.provider_serpapi.models import ProviderNormalizedFact
from app.modules.users.models import Workspace

# --- Second acceptance scenario (mission section 49) ----------------------
#
# "What changed with this lead since our last research, and does it create a
# new sales opportunity for us?"
#
# The model double is a small decision policy over the TRANSCRIPT: it reads
# what the tools returned and picks the next tool. Nothing in the runtime or
# the double replays a fixed sequence -- the same policy takes different
# paths in the four tests below because the data differs:
#
#   evidence fresh + change already recorded  -> no refresh
#   evidence stale + no change recorded       -> refresh, then re-read deltas
#   meaningful change  -> search_sales_knowledge (else it never asks RAG)
#   RAG returns nothing -> "no supported internal match"
#
# Deltas are rows written by the backend (ResearchChangeEvent); the model
# cannot create one, and a ref it invents is dropped from the answer.

_GOAL = (
    "What changed with this lead since our last research, and does it create a "
    "new sales opportunity for us?"
)
_MEANINGFUL = 0.5
_STALE_BELOW = 0.5

_CLAIM_QUERIES = {
    "online_booking": "online booking appointment scheduling",
    "has_whatsapp": "whatsapp lead qualification",
    "branch_count": "multi branch expansion",
}


def _min_freshness(graph: Any) -> float:
    values = [
        float(fact["freshness_score"])
        for group in (graph or {}).get("groups", [])
        for fact in group.get("facts", [])
        if "freshness_score" in fact
    ]
    return min(values) if values else 0.0


def _meaningful_changes(delta: Any) -> list[dict[str, Any]]:
    return [
        change
        for change in (delta or {}).get("changes", [])
        if float(change.get("significance", 0)) >= _MEANINGFUL
    ]


def change_monitoring_policy(invented_refs: list[str] | None = None) -> Any:
    def decide(state: Transcript) -> Decision:
        if "get_delta_changes" not in state.called:
            return "get_delta_changes", {}
        if "get_research_history" not in state.called:
            return "get_research_history", {}
        if "get_evidence_graph" not in state.called:
            return "get_evidence_graph", {}

        stale = _min_freshness(state.results.get("get_evidence_graph")) < _STALE_BELOW
        no_known_change = not _meaningful_changes(state.results.get("get_delta_changes"))
        if stale and no_known_change and "refresh_lead_research" not in state.called:
            return "refresh_lead_research", {}
        if state.count("refresh_lead_research") and state.count("get_delta_changes") < 2:
            return "get_delta_changes", {}

        changes = _meaningful_changes(state.results.get("get_delta_changes"))
        if not changes:
            return "final", {
                "answer": "Nothing meaningful has changed since the last research.",
                "confidence": 0.7,
                "opportunities": [],
                "evidence_refs": [*state.refs("change_id"), *(invented_refs or [])],
            }

        top = max(changes, key=lambda change: float(change["significance"]))
        if "search_sales_knowledge" not in state.called:
            query = _CLAIM_QUERIES.get(str(top["claim_type"]), str(top["claim_type"]))
            return "search_sales_knowledge", {"query": query}

        matches = state.results.get("search_sales_knowledge", {}).get("results") or []
        refs = [*state.refs("change_id"), *state.refs("evidence_ref"), *(invented_refs or [])]
        summary = f"{top['claim_type']} changed from {top['before']} to {top['after']}."
        if not matches:
            return "final", {
                "answer": (
                    f"{summary} We have evidence of this change, but I could not find a "
                    "sufficiently supported internal capability or case study to recommend."
                ),
                "confidence": 0.5,
                "opportunities": [],
                "evidence_refs": refs,
            }
        return "final", {
            "answer": f"{summary} This strengthens the opportunity: {matches[0]['document_title']}.",
            "confidence": 0.75,
            "opportunities": [str(matches[0]["document_title"])],
            "evidence_refs": refs,
            "knowledge_refs": [match["document_id"] for match in matches] + ["doc_invented"],
        }

    return decide


# --- fixtures -------------------------------------------------------------


class _Scenario:
    def __init__(self, session_factory: Any, seed: Any, provider: TranscriptProvider) -> None:
        self.session_factory = session_factory
        self.seed = seed
        self.provider = provider
        with session_factory() as db:
            workspace = db.scalar(select(Workspace).where(Workspace.public_id == seed.workspace_public_id))
            lead = db.scalar(select(Lead).where(Lead.public_id == seed.lead_public_id))
            assert workspace is not None and lead is not None
            self.workspace_id, self.lead_id = workspace.id, lead.id

    def make_evidence_stale(self) -> None:
        with self.session_factory() as db:
            for fact in db.scalars(
                select(ProviderNormalizedFact).where(ProviderNormalizedFact.lead_id == self.lead_id)
            ):
                fact.freshness_score = 0.1
            db.commit()

    def record_change(self, claim: str = "online_booking", before: str = "false", after: str = "true") -> str:
        with self.session_factory() as db:
            _, change = add_research_run_with_change(
                db,
                workspace_id=self.workspace_id,
                lead_id=self.lead_id,
                claim_type=claim,
                before=before,
                after=after,
                minutes_ago=60,
            )
            return change.public_id

    def run(self) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        with _override_client(self.session_factory) as client:
            headers = {"Authorization": f"Bearer {_login(client, self.seed)}"}
            run = start_agent_run(client,
                "/api/v1/agent/runs",
                json={"goal": _GOAL, "lead_id": self.seed.lead_public_id, "profile": "sales_copilot"},
                headers=headers,
            ).json()
            events = client.get(f"/api/v1/agent/runs/{run['run_id']}/events", headers=headers).json()["events"]
        return run, events


def _scenario(
    monkeypatch: pytest.MonkeyPatch,
    *,
    with_capability: bool,
    invented: list[str] | None = None,
    refresh_records_change: bool = True,
) -> tuple[_Scenario, list[int]]:
    _env(monkeypatch)
    provider = TranscriptProvider(change_monitoring_policy(invented))
    monkeypatch.setattr(runtime_module.httpx, "Client", provider)
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    _seed_knowledge(session_factory, seed, with_booking=with_capability)
    scenario = _Scenario(session_factory, seed, provider)
    refresh_calls: list[int] = []

    class _Result:
        def model_dump(self, mode: str = "python") -> dict[str, Any]:
            return {"ok": True, "refreshed": True}

    def fake_refresh(self: Any, db: Any, *, workspace_id: int, lead: Any, depth: str) -> _Result:
        # Stand-in for the research pipeline: it re-observes the lead (fresh
        # facts) and the DELTA ENGINE records the change as a database row.
        refresh_calls.append(1)
        for fact in db.scalars(
            select(ProviderNormalizedFact).where(ProviderNormalizedFact.lead_id == lead.id)
        ):
            fact.freshness_score = 1.0
        db.commit()
        if refresh_records_change:
            add_research_run_with_change(
                db,
                workspace_id=workspace_id,
                lead_id=lead.id,
                claim_type="online_booking",
                before="false",
                after="true",
            )
        return _Result()

    monkeypatch.setattr(executor_module.ResearchAgentLoop, "run", fake_refresh)
    return scenario, refresh_calls


def _assert_read_only(scenario: _Scenario) -> None:
    with scenario.session_factory() as db:
        assert db.query(AgentAction).count() == 0, "No mutation unless explicitly requested."
        assert db.query(LeadNote).count() == 0
        assert db.query(AgentRun).count() == 1, "One AgentRun throughout."


# --- branches -------------------------------------------------------------


def test_fresh_evidence_with_a_known_change_skips_refresh_and_finds_a_matching_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenario, refresh_calls = _scenario(monkeypatch, with_capability=True)
    change_ref = scenario.record_change()

    run, events = scenario.run()

    assert run["status"] == "completed"
    assert refresh_calls == [], "Fresh, sufficient evidence must not be re-researched."
    assert "refresh_lead_research" not in scenario.provider.decisions
    decisions = scenario.provider.decisions
    assert decisions.index("get_evidence_graph") < decisions.index("search_sales_knowledge")

    answer = run["final_answer"]
    assert "online_booking changed from false to true" in answer["answer"]
    assert change_ref in answer["evidence_refs"]
    # knowledge_refs: the real retrieved document survives, the invented one does not.
    assert answer["knowledge_refs"] and "doc_invented" not in answer["knowledge_refs"]
    assert answer["opportunities"]
    assert [event["event_type"] for event in events].count("rag_search_completed") == 1
    _assert_read_only(scenario)


def test_stale_evidence_triggers_refresh_then_rereads_the_delta_before_asking_rag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenario, refresh_calls = _scenario(monkeypatch, with_capability=True)
    scenario.make_evidence_stale()

    run, _events = scenario.run()

    decisions = scenario.provider.decisions
    assert run["status"] == "completed", decisions
    assert refresh_calls == [1], decisions
    # Tool choice changed BECAUSE of the results: stale graph -> refresh ->
    # second delta read -> only then knowledge.
    assert decisions.index("refresh_lead_research") > decisions.index("get_evidence_graph")
    assert decisions.count("get_delta_changes") == 2
    assert decisions.index("get_delta_changes", decisions.index("refresh_lead_research")) < decisions.index(
        "search_sales_knowledge"
    )
    answer = run["final_answer"]
    assert answer["knowledge_refs"] and answer["opportunities"]
    assert any(ref.startswith("rce_") for ref in answer["evidence_refs"])
    _assert_read_only(scenario)


def test_meaningful_change_but_no_internal_capability_says_so_and_cites_no_knowledge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenario, _ = _scenario(monkeypatch, with_capability=False)
    change_ref = scenario.record_change()

    run, events = scenario.run()

    answer = run["final_answer"]
    assert "could not find a sufficiently supported internal capability" in answer["answer"]
    assert answer["knowledge_refs"] == []
    assert answer["opportunities"] == []
    assert change_ref in answer["evidence_refs"], "The change itself is still evidenced."
    completed = [e for e in events if e["event_type"] == "rag_search_completed"]
    assert completed and completed[0]["payload"]["result_count"] == 0
    _assert_read_only(scenario)


def test_no_meaningful_change_after_refresh_never_reaches_rag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenario, refresh_calls = _scenario(monkeypatch, with_capability=True, refresh_records_change=False)
    scenario.make_evidence_stale()

    run, events = scenario.run()

    assert refresh_calls == [1]
    assert "search_sales_knowledge" not in scenario.provider.decisions, (
        "RAG is only consulted once a meaningful opportunity exists."
    )
    assert "Nothing meaningful has changed" in run["final_answer"]["answer"]
    assert run["final_answer"]["knowledge_refs"] == []
    assert "rag_search_started" not in [event["event_type"] for event in events]
    _assert_read_only(scenario)


def test_a_delta_the_model_invents_is_not_backend_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    """The model cites a change that no research run ever recorded. The
    deterministic delta record is the only source of truth, so the ref is
    dropped, audited, and never reaches the final answer."""
    scenario, _ = _scenario(monkeypatch, with_capability=True, invented=["rce_score_jumped_40"])
    real_ref = scenario.record_change()

    run, _events = scenario.run()

    refs = run["final_answer"]["evidence_refs"]
    assert real_ref in refs and "rce_score_jumped_40" not in refs
    with scenario.session_factory() as db:
        dropped = db.query(AgentEvent).filter_by(event_type="final_evidence_ref_dropped").all()
    assert dropped and "rce_score_jumped_40" in dropped[0].payload_json["dropped"]
