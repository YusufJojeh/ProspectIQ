from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from test_knowledge_rag import _collection, _document
from test_workspace_e2e import _build_session_factory, _login, _override_client, _seed_workspace

import app.modules.agents.runtime as runtime_module
from app.core.config import clear_settings_cache
from app.modules.knowledge.constants import CASE_STUDIES, SERVICES
from app.modules.knowledge.service import KnowledgeService
from app.modules.users.models import User, Workspace

# --- Agent behaviour evals -----------------------------------------------
#
# These are behavioural assertions about the RUNTIME, driven by a provider
# double that decides one call at a time. The double plays the part of a
# reasonable model; what is under test is what the runtime does with those
# choices -- which tools it offers, what it refuses, what it writes, and
# what it hands back.

_REAL_HTTPX_CLIENT = httpx.Client


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class _ScriptedProvider:
    """Plays a sequence of tool choices, then a final answer.

    The runtime is never told the sequence; it only ever sees one decision
    at a time, exactly as with a live model.
    """

    def __init__(self, calls: list[tuple[str, dict[str, Any]]], final: dict[str, Any]) -> None:
        self._calls = list(calls)
        self._final = final
        self.index = 0
        self.offered_tool_names: list[list[str]] = []
        self.requests: list[dict[str, Any]] = []

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        headers = kwargs.get("headers") or {}
        if "Authorization" in headers:
            return self
        return _REAL_HTTPX_CLIENT(*args, **kwargs)

    def __enter__(self) -> _ScriptedProvider:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def post(self, url: str, json: dict[str, Any] | None = None, **kwargs: Any) -> _FakeResponse:
        body = json or {}
        self.requests.append(body)
        self.offered_tool_names.append(
            [tool["function"]["name"] for tool in body.get("tools", [])]
        )
        if self.index >= len(self._calls):
            return _FakeResponse(
                {
                    "choices": [
                        {"message": {"role": "assistant", "content": _dumps(self._final)}}
                    ],
                    "usage": {"prompt_tokens": 100, "completion_tokens": 30},
                }
            )
        name, arguments = self._calls[self.index]
        self.index += 1
        return _FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": f"call_{self.index}",
                                    "type": "function",
                                    "function": {
                                        "name": name,
                                        "arguments": _dumps(arguments),
                                    },
                                }
                            ],
                        }
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 30},
            }
        )


def _dumps(value: dict[str, Any]) -> str:
    return json.dumps(value)


def _env(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-a-real-key")
    monkeypatch.setenv("AGENT_RUNTIME_MODE", "openai")
    monkeypatch.setenv("TAVILY_RUNTIME_MODE", "demo")
    monkeypatch.setenv("APIFY_RUNTIME_MODE", "demo")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)
    clear_settings_cache()


def _seed_knowledge(session_factory: Any, seed: Any, *, with_booking: bool) -> None:
    """Seed the workspace's own sales knowledge.

    `with_booking=False` seeds a knowledge base that is real but
    IRRELEVANT to a clinic with no online booking -- the setup for the
    'no sufficient internal match' scenario.
    """
    service = KnowledgeService()
    with session_factory() as db:
        workspace = db.query(Workspace).filter_by(public_id=seed.workspace_public_id).one()
        admin = db.query(User).filter_by(email=seed.admin_email).one()
        services_id = _collection(
            service, db, workspace_id=workspace.id, slug="services", kind=SERVICES
        )
        cases_id = _collection(
            service, db, workspace_id=workspace.id, slug="case-studies", kind=CASE_STUDIES
        )
        if with_booking:
            _document(
                service,
                db,
                workspace_id=workspace.id,
                user_id=admin.id,
                collection_id=services_id,
                title="Online Booking and Appointment Scheduling",
                content=(
                    "## Online booking\n\n"
                    "We install an online booking appointment scheduling system with "
                    "automated reminders for clinics."
                ),
            )
            _document(
                service,
                db,
                workspace_id=workspace.id,
                user_id=admin.id,
                collection_id=cases_id,
                title="Clinic Appointment Automation",
                content=(
                    "## Outcome\n\n"
                    "A clinic replaced phone-only booking with online appointment "
                    "scheduling and recovered out-of-hours demand."
                ),
            )
        else:
            _document(
                service,
                db,
                workspace_id=workspace.id,
                user_id=admin.id,
                collection_id=services_id,
                title="Warehouse Logistics Telemetry",
                content=(
                    "## Logistics telemetry\n\n"
                    "We instrument warehouse conveyor hardware and forklift fleets "
                    "with telemetry dashboards for industrial operators."
                ),
            )
        db.commit()


def _start(session_factory: Any, seed: Any, *, goal: str, profile: str = "research") -> Any:
    with _override_client(session_factory) as client:
        token = _login(client, seed)
        headers = {"Authorization": f"Bearer {token}"}
        run = client.post(
            "/api/v1/agent/runs",
            json={"goal": goal, "lead_id": seed.lead_public_id, "profile": profile},
            headers=headers,
        ).json()
        events = client.get(
            f"/api/v1/agent/runs/{run['run_id']}/events", headers=headers
        ).json()["events"]
        return run, events


# --- Evidence sufficiency ------------------------------------------------


def test_reading_existing_evidence_spends_no_external_provider_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch)
    provider = _ScriptedProvider(
        calls=[("get_lead_context", {}), ("get_evidence_graph", {})],
        final={"answer": "Evidence already sufficient.", "confidence": 0.7},
    )
    monkeypatch.setattr(runtime_module.httpx, "Client", provider)
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    run, events = _start(session_factory, seed, goal="Summarise what we already know.")

    from app.modules.agents.models import AgentRun

    with session_factory() as db:
        row = db.query(AgentRun).filter_by(public_id=run["run_id"]).one()
    assert run["status"] == "completed"
    # No search, no crawl: reading stored evidence must not cost provider
    # budget, or "check before you research" is advice the system ignores.
    assert row.external_search_count == 0
    assert row.crawl_count == 0


def test_research_tools_are_used_when_the_model_asks_for_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch)
    provider = _ScriptedProvider(
        calls=[
            ("get_evidence_graph", {}),
            ("search_web_tavily", {}),
        ],
        final={"answer": "Researched.", "confidence": 0.6},
    )
    monkeypatch.setattr(runtime_module.httpx, "Client", provider)
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    run, _events = _start(session_factory, seed, goal="Find out more.")

    from app.modules.agents.models import AgentRun
    from app.modules.ai_runtime.models import ProviderUsage

    with session_factory() as db:
        row = db.query(AgentRun).filter_by(public_id=run["run_id"]).one()
        usage = db.query(ProviderUsage).filter_by(subject_id=row.public_id).all()
    assert row.external_search_count == 1
    # And the external call is in the ledger under the run's trace.
    searches = [entry for entry in usage if entry.operation == "external_search"]
    assert len(searches) == 1
    assert searches[0].trace_id == row.trace_id


# --- Mutation always goes through the approval gate ----------------------


def test_a_mutation_request_produces_a_pending_action_and_writes_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch)
    provider = _ScriptedProvider(
        calls=[("add_lead_note", {"note": "Worth a call this week."})],
        final={"answer": "Proposed.", "confidence": 0.5},
    )
    monkeypatch.setattr(runtime_module.httpx, "Client", provider)
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    run, events = _start(session_factory, seed, goal="Add a note.")

    from app.modules.leads.models import LeadNote

    with session_factory() as db:
        notes = db.query(LeadNote).count()

    assert run["status"] == "waiting_for_approval"
    assert any(event["event_type"] == "action_proposed" for event in events)
    # Nothing was written while the action is pending. This is the whole
    # point of the gate.
    assert notes == 0


def test_read_only_profile_is_never_offered_a_mutating_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch)
    provider = _ScriptedProvider(
        calls=[("get_lead_context", {})],
        final={"answer": "Read only.", "confidence": 0.5},
    )
    monkeypatch.setattr(runtime_module.httpx, "Client", provider)
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    _run, _events = _start(
        session_factory, seed, goal="Just tell me about this lead.", profile="read_only"
    )

    offered = set(provider.offered_tool_names[0])
    assert "get_lead_context" in offered
    # The mutating tools are not merely rejected after the model asks --
    # they are never described to it.
    assert not offered & {
        "add_lead_note",
        "update_lead_stage",
        "create_follow_up",
        "save_outreach_draft",
        "send_email",
    }


# --- Sales knowledge grounding -------------------------------------------


def test_rag_search_is_recorded_with_the_documents_that_grounded_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch)
    provider = _ScriptedProvider(
        calls=[
            (
                "search_sales_knowledge",
                {"query": "online booking appointment scheduling"},
            )
        ],
        final={"answer": "Found a capability.", "confidence": 0.6},
    )
    monkeypatch.setattr(runtime_module.httpx, "Client", provider)
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    _seed_knowledge(session_factory, seed, with_booking=True)

    run, events = _start(session_factory, seed, goal="What can we offer them?")

    types = [event["event_type"] for event in events]
    assert "rag_search_started" in types
    assert "rag_search_completed" in types
    selected = [event for event in events if event["event_type"] == "knowledge_selected"]
    assert selected, "A successful RAG search must record which documents grounded it."
    titles = {
        citation.get("document_title")
        for event in selected
        for citation in event["payload"].get("citations", [])
    }
    assert any(title and "Booking" in title for title in titles)

    from app.modules.agents.models import AgentRun

    with session_factory() as db:
        row = db.query(AgentRun).filter_by(public_id=run["run_id"]).one()
    assert row.rag_query_count == 1


def test_no_relevant_internal_capability_returns_no_results_rather_than_a_stretch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Third acceptance scenario: good lead evidence, no internal match.

    The knowledge base here is real but about warehouse logistics. A
    clinic's booking problem must retrieve nothing, so the agent has
    nothing to cite -- rather than being handed a loosely-similar document
    it could dress up as a fit.
    """
    _env(monkeypatch)
    provider = _ScriptedProvider(
        calls=[
            (
                "search_sales_knowledge",
                {"query": "online booking appointment scheduling for a clinic"},
            )
        ],
        final={
            "answer": (
                "This lead has an evidenced problem, but I could not find a sufficiently "
                "supported internal capability or case study to recommend."
            ),
            "confidence": 0.4,
        },
    )
    monkeypatch.setattr(runtime_module.httpx, "Client", provider)
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    _seed_knowledge(session_factory, seed, with_booking=False)

    run, events = _start(session_factory, seed, goal="What can we offer them?")

    completed = [
        event for event in events if event["event_type"] == "rag_search_completed"
    ]
    assert completed
    assert completed[0]["payload"].get("result_count") == 0
    # Nothing was selected, so there is nothing to cite.
    selected = [
        event
        for event in events
        if event["event_type"] == "knowledge_selected"
        and event["payload"].get("citations")
    ]
    assert not selected
    assert run["status"] == "completed"


# --- Untrusted content ---------------------------------------------------


def test_the_model_is_told_research_results_are_untrusted_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch)
    provider = _ScriptedProvider(
        calls=[("search_web_tavily", {})],
        final={"answer": "Done.", "confidence": 0.5},
    )
    monkeypatch.setattr(runtime_module.httpx, "Client", provider)
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    _start(session_factory, seed, goal="Search the web.")

    # The follow-up request carries the search result. It must arrive inside
    # the untrusted envelope, not as bare text the model could read as
    # instruction -- prompting is not the security boundary, but the model
    # still has to be told which bytes came from the open web.
    assert len(provider.requests) >= 2
    tool_messages = [
        message
        for body in provider.requests
        for message in body.get("messages", [])
        if message.get("role") == "tool"
    ]
    assert tool_messages, "The search result was never returned to the model."
    assert any(
        "BEGIN_UNTRUSTED" in str(message.get("content", "")) for message in tool_messages
    )

    # And the standing instruction about untrusted data is in the system
    # prompt of every request, not only the first.
    systems = [
        message["content"]
        for body in provider.requests
        for message in body.get("messages", [])
        if message.get("role") == "system"
    ]
    assert systems and all("untrusted" in str(content).lower() for content in systems)
