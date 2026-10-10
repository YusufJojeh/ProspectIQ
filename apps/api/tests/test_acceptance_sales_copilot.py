from __future__ import annotations

import json
from typing import Any

import pytest
from agent_api_helpers import start_agent_run
from test_agent_behavior_evals import _REAL_HTTPX_CLIENT, _env, _FakeResponse, _seed_knowledge
from test_workspace_e2e import _build_session_factory, _login, _override_client, _seed_workspace

import app.modules.agents.runtime as runtime_module
from app.modules.agents.models import AgentAction, AgentRun
from app.modules.crm.models import CrmActivity
from app.modules.leads.models import LeadNote

# --- Main acceptance scenario (mission section 48) ------------------------
#
# The model double below holds NO script. On every call it reads the
# transcript the runtime sent and decides the next step from what the tools
# actually returned -- the knowledge results decide whether it drafts
# outreach or declares no match. The runtime never learns the sequence.

_GOAL = (
    "Research this company deeply. Tell me whether it fits our ICP. Find which of our "
    "services or case studies match its problems. Prepare a personalized outreach "
    "message. Add the opportunity analysis as a note and create a follow-up for three "
    "days from now."
)


class _ReasoningProvider:
    def __init__(self) -> None:
        self.decisions: list[str] = []

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        if "Authorization" in (kwargs.get("headers") or {}):
            return self
        return _REAL_HTTPX_CLIENT(*args, **kwargs)

    def __enter__(self) -> _ReasoningProvider:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def post(self, url: str, json: dict[str, Any] | None = None, **kwargs: Any) -> _FakeResponse:
        messages = (json or {}).get("messages", [])
        called: list[str] = [
            call["function"]["name"]
            for message in messages
            if message.get("role") == "assistant"
            for call in message.get("tool_calls") or []
        ]
        results: dict[str, Any] = {}
        names_by_id = {
            call["id"]: call["function"]["name"]
            for message in messages
            if message.get("role") == "assistant"
            for call in message.get("tool_calls") or []
        }
        for message in messages:
            if message.get("role") == "tool":
                name = names_by_id.get(message.get("tool_call_id", ""), "")
                try:
                    results[name] = _loads(message.get("content") or "{}")
                except ValueError:
                    results[name] = {}
        choice = self._decide(called, results)
        self.decisions.append(choice[0])
        if choice[0] == "final":
            return _FakeResponse(
                {
                    "choices": [{"message": {"role": "assistant", "content": _dumps(choice[1])}}],
                    "usage": {"prompt_tokens": 200, "completion_tokens": 60},
                }
            )
        return _FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": f"call_{len(called) + 1}",
                                    "type": "function",
                                    "function": {"name": choice[0], "arguments": _dumps(choice[1])},
                                }
                            ],
                        }
                    }
                ],
                "usage": {"prompt_tokens": 200, "completion_tokens": 30},
            }
        )

    def _decide(self, called: list[str], results: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        for tool in ("get_lead_context", "get_icp_profile", "get_evidence_graph"):
            if tool not in called:
                return tool, {}
        if "search_web_tavily" not in called:
            return "search_web_tavily", {}
        if "get_score_breakdown" not in called:
            return "get_score_breakdown", {}
        if "search_sales_knowledge" not in called:
            return "search_sales_knowledge", {"query": "online booking appointment scheduling"}
        knowledge = results.get("search_sales_knowledge", {}).get("results") or []
        if not knowledge:
            return "final", {"answer": "No sufficiently supported internal capability.", "confidence": 0.3}
        if "draft_outreach" not in called:
            return "draft_outreach", {"tone": "consultative"}
        if "add_lead_note" not in called:
            title = knowledge[0].get("title", "")
            return "add_lead_note", {"note": f"Opportunity: online booking gap. Fit: {title}."}
        if "create_follow_up" not in called:
            return "create_follow_up", {"title": "Follow up on booking proposal", "due_in_days": 3}
        return "final", {
            "answer": "Strong fit; note and follow-up completed.",
            "confidence": 0.7,
            # One real citation and one the model made up.
            "knowledge_refs": [knowledge[0].get("document_id"), "doc_invented_by_model"],
            # The model claims an action that never ran.
            "completed_actions": ["send_email:fabricated"],
            "research_coverage": 1.0,
        }


def _dumps(value: dict[str, Any]) -> str:
    return json.dumps(value)


def _loads(value: str) -> Any:
    # Untrusted results arrive fenced (BEGIN_UNTRUSTED_..._CONTEXT); a model
    # reads the JSON inside the fence, so the double does the same.
    start, end = value.find("{"), value.rfind("}")
    return json.loads(value[start : end + 1]) if start != -1 else {}


def test_main_acceptance_scenario_pauses_executes_on_approval_and_resumes_same_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch)
    provider = _ReasoningProvider()
    monkeypatch.setattr(runtime_module.httpx, "Client", provider)
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    _seed_knowledge(session_factory, seed, with_booking=True)

    with _override_client(session_factory) as client:
        headers = {"Authorization": f"Bearer {_login(client, seed)}"}
        run = start_agent_run(client,
            "/api/v1/agent/runs",
            json={"goal": _GOAL, "lead_id": seed.lead_public_id, "profile": "sales_copilot"},
            headers=headers,
        ).json()
        run_id = run["run_id"]
        assert run["status"] == "waiting_for_approval"

        with session_factory() as db:
            assert db.query(LeadNote).count() == 0, "No note may be written before approval."
            assert db.query(CrmActivity).count() == 0

        approved: list[str] = []
        # Proposals pause one at a time; approve each until the run finishes.
        for _ in range(4):
            pending = client.get(
                "/api/v1/agent/actions", params={"status": "pending"}, headers=headers
            ).json()["items"]
            if not pending:
                break
            action = pending[0]
            approved.append(action["tool_name"])
            response = client.post(f"/api/v1/agent/actions/{action['action_id']}/approve", headers=headers)
            assert response.status_code == 200
            assert response.json()["status"] == "executed"
            # A retried approval must not execute twice.
            retry = client.post(f"/api/v1/agent/actions/{action['action_id']}/approve", headers=headers)
            assert retry.status_code in {200, 409}

        final = client.get(f"/api/v1/agent/runs/{run_id}", headers=headers).json()
        events = client.get(f"/api/v1/agent/runs/{run_id}/events", headers=headers).json()["events"]

    assert approved == ["add_lead_note", "create_follow_up"]
    assert final["status"] == "completed"
    answer = final["final_answer"]
    # Backend-owned fields: only the real citation survives, actions come
    # from AgentAction rows, and coverage is the Evidence Graph's number.
    assert len(answer["knowledge_refs"]) == 1 and "doc_invented_by_model" not in answer["knowledge_refs"]
    assert [ref.split(":")[0] for ref in answer["completed_actions"]] == [
        "add_lead_note",
        "create_follow_up",
    ]
    assert answer["pending_actions"] == []
    assert answer["research_coverage"] < 1.0

    # The runtime followed the model's choices; the RAG result drove drafting.
    assert provider.decisions.index("search_sales_knowledge") < provider.decisions.index("draft_outreach")
    event_types = [event["event_type"] for event in events]
    assert event_types.count("agent_resumed") == 2
    assert "knowledge_selected" in event_types

    with session_factory() as db:
        assert db.query(AgentRun).count() == 1, "Resume must reuse the SAME run."
        assert db.query(LeadNote).count() == 1, "Exactly one note despite the retried approval."
        assert db.query(CrmActivity).count() == 1
        actions = db.query(AgentAction).all()
        assert {action.status for action in actions} == {"executed"}
        run_row = db.query(AgentRun).one()
        assert {action.trace_id for action in actions} == {run_row.trace_id}


def test_arguments_outside_the_registered_schema_are_rejected_not_executed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An invalid enum from the model is a tool error the model can correct,
    never an unhandled exception inside a domain service."""
    from test_agent_behavior_evals import _ScriptedProvider, _start

    _env(monkeypatch)
    provider = _ScriptedProvider(
        calls=[
            ("draft_outreach", {"tone": "professional"}),
            ("create_follow_up", {"title": "x", "due_in_days": 9999}),
            ("add_lead_note", {"note": "hi", "workspace_id": 7}),
        ],
        final={"answer": "Stopped.", "confidence": 0.1},
    )
    monkeypatch.setattr(runtime_module.httpx, "Client", provider)
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    run, events = _start(session_factory, seed, goal="Draft something.", profile="sales_copilot")

    failed = [event for event in events if event["event_type"] == "tool_failed"]
    assert len(failed) == 3
    assert run["status"] in {"completed", "failed"}
    with session_factory() as db:
        assert db.query(AgentAction).count() == 0, "Nothing invalid may reach the action gate."
