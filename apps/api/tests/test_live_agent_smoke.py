from __future__ import annotations

import os
from typing import Any

import pytest
from test_knowledge_rag import _collection, _document
from test_workspace_e2e import _build_session_factory as _build_e2e_session_factory
from test_workspace_e2e import _login, _override_client
from test_workspace_e2e import _seed_workspace as _seed_e2e_workspace

from app.core.config import clear_settings_cache
from app.modules.agents.models import AgentAction, AgentRun, AgentToolCall
from app.modules.ai_runtime.models import ProviderUsage
from app.modules.crm.models import CrmActivity
from app.modules.knowledge.constants import CASE_STUDIES, SERVICES
from app.modules.knowledge.service import KnowledgeService
from app.modules.leads.models import LeadNote
from app.modules.users.models import User, Workspace

# --- Live provider smoke --------------------------------------------------
#
# Opt-in only. It spends real provider budget, so it must never run as part
# of the ordinary suite: an accidentally-green CI that quietly bills an
# account is worse than no smoke test.
#
#   RUN_LIVE_AGENT_SMOKE=1 OPENAI_API_KEY=... pytest tests/test_live_agent_smoke.py
#
# What it proves that the mocked provider-contract tests cannot: that a REAL
# model, given the real registry schemas, natively calls tools, receives the
# backend's real results, and produces an answer the runtime accepts.
#
# Safety: an in-memory database seeded per test, a dedicated throwaway
# workspace and lead, a strict model-call/step budget, demo research
# providers (no Tavily/SerpAPI/Apify spend), and a read-only profile for
# smokes 1-2. Smoke 3 uses the sales_copilot profile but NEVER approves the
# action it may propose; the assertion is that nothing executed.
#
# The model comes from the existing AgentModelRouter/OPENAI_MODEL settings;
# nothing here hardcodes a model, key, or workspace id.

_ENABLED = os.getenv("RUN_LIVE_AGENT_SMOKE") == "1"

pytestmark = pytest.mark.skipif(
    not _ENABLED,
    reason=(
        "Set RUN_LIVE_AGENT_SMOKE=1 and OPENAI_API_KEY to run the live agent smoke test. "
        "It calls a real provider and spends real budget."
    ),
)


def _require_key() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY is required for the live agent smoke test.")


def _live_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _require_key()
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("AGENT_RUNTIME_MODE", "openai")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
    monkeypatch.setenv("TAVILY_RUNTIME_MODE", "demo")
    monkeypatch.setenv("APIFY_RUNTIME_MODE", "demo")
    monkeypatch.setenv("AGENT_MAX_MODEL_CALLS", "8")
    monkeypatch.setenv("AGENT_MAX_STEPS", "8")
    clear_settings_cache()


def _seed_knowledge(session_factory: Any, seed: Any) -> dict[str, str]:
    """Two known documents; returns {title: document public id}."""
    service = KnowledgeService()
    with session_factory() as db:
        workspace = db.query(Workspace).filter_by(public_id=seed.workspace_public_id).one()
        admin = db.query(User).filter_by(email=seed.admin_email).one()
        services_id = _collection(service, db, workspace_id=workspace.id, slug="services", kind=SERVICES)
        cases_id = _collection(service, db, workspace_id=workspace.id, slug="case-studies", kind=CASE_STUDIES)
        _document(
            service,
            db,
            workspace_id=workspace.id,
            user_id=admin.id,
            collection_id=services_id,
            title="Online Booking and Appointment Automation",
            content=(
                "## Online booking\n\n"
                "We install an online booking and appointment scheduling system for "
                "clinics and salons, including automated reminders that reduce no-shows."
            ),
        )
        _document(
            service,
            db,
            workspace_id=workspace.id,
            user_id=admin.id,
            collection_id=cases_id,
            title="Dental Clinic Appointment Automation",
            content=(
                "## Outcome\n\n"
                "A dental clinic moved from phone-only bookings to online scheduling "
                "with automated reminders, and recovered out-of-hours demand."
            ),
        )
        db.commit()
    return {}


def _run_agent(
    session_factory: Any, seed: Any, *, goal: str, profile: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    with _override_client(session_factory) as client:
        headers = {"Authorization": f"Bearer {_login(client, seed)}"}
        response = client.post(
            "/api/v1/agent/runs",
            json={"goal": goal, "lead_id": seed.lead_public_id, "profile": profile},
            headers=headers,
        )
        assert response.status_code == 201, response.text
        run: dict[str, Any] = response.json()
        events = client.get(f"/api/v1/agent/runs/{run['run_id']}/events", headers=headers).json()["events"]
    failed = [e for e in events if e["event_type"] == "agent_failed"]
    if failed and failed[0]["payload"].get("error_code") == "model_provider_unavailable":
        # Not a runtime defect: the provider refused or could not be reached.
        pytest.fail(
            "Live provider call failed (model_provider_unavailable). Check that OPENAI_API_KEY "
            "is valid, has quota, and can use the configured model; this run proves nothing "
            "about tool calling."
        )
    return run, events


def _types(events: list[dict[str, Any]]) -> list[str]:
    return [event["event_type"] for event in events]


def _requested_tools(events: list[dict[str, Any]]) -> list[str]:
    return [e["payload"]["tool_name"] for e in events if e["event_type"] == "tool_requested"]


def _assert_no_mutation(session_factory: Any) -> None:
    with session_factory() as db:
        assert db.query(LeadNote).count() == 0
        assert db.query(CrmActivity).count() == 0
        assert db.query(AgentAction).filter(AgentAction.status == "executed").count() == 0


def _assert_traced_and_metered(session_factory: Any, run: dict[str, Any]) -> AgentRun:
    with session_factory() as db:
        row = db.query(AgentRun).filter_by(public_id=run["run_id"]).one()
        assert row.trace_id, "trace_id must be populated"
        usage = db.query(ProviderUsage).filter_by(subject_id=row.public_id).all()
        assert usage, "usage must be recorded for the run"
        assert {entry.trace_id for entry in usage} == {row.trace_id}
        assert row.model_call_count >= 2, "a tool round-trip needs at least two model calls"
        db.expunge(row)
        return row


# --- Smoke 1: native tool call, real result back to the real model ---------


def test_live_smoke_1_native_read_tool_call_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    _live_env(monkeypatch)
    session_factory = _build_e2e_session_factory()
    seed = _seed_e2e_workspace(session_factory)

    run, events = _run_agent(
        session_factory,
        seed,
        goal="Inspect this lead's current evidence and summarize what we know.",
        profile="read_only",
    )

    requested = _requested_tools(events)
    assert requested, "The live model made no native tool call."
    assert run["status"] == "completed", (run["status"], _types(events))

    with session_factory() as db:
        row = db.query(AgentRun).filter_by(public_id=run["run_id"]).one()
        calls = db.query(AgentToolCall).filter_by(agent_run_id=row.id).all()
    ok_calls = [call for call in calls if call.status == "ok" and call.result_json]
    assert ok_calls, "A backend tool must have executed and returned a result."
    # The real tool result reached the model: a model call ran AFTER the
    # first tool completed, and it produced the final answer.
    types = _types(events)
    first_done = types.index("tool_completed")
    assert "model_completed" in types[first_done:], "No model call followed the tool result."
    assert run["final_answer"] and run["final_answer"]["answer"].strip()
    _assert_traced_and_metered(session_factory, run)
    _assert_no_mutation(session_factory)


# --- Smoke 2: lead tool -> search_sales_knowledge -> cited answer ----------


def test_live_smoke_2_rag_answer_is_grounded_in_retrieved_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _live_env(monkeypatch)
    session_factory = _build_e2e_session_factory()
    seed = _seed_e2e_workspace(session_factory)
    _seed_knowledge(session_factory, seed)

    run, events = _run_agent(
        session_factory,
        seed,
        goal=(
            "Based on this lead, find one internal service or case study that may be "
            "relevant, and cite the document(s) you used."
        ),
        profile="read_only",
    )

    requested = _requested_tools(events)
    assert "search_sales_knowledge" in requested, requested
    assert run["status"] == "completed", (run["status"], _types(events))
    assert "rag_search_completed" in _types(events)

    # knowledge_refs are backend-grounded: every ref is a document that a
    # knowledge_selected event recorded as actually retrieved in this run.
    retrieved = {
        str(citation["document_id"])
        for event in events
        if event["event_type"] == "knowledge_selected"
        for citation in event["payload"]["citations"]
    }
    assert retrieved, "The seeded booking documents should have been retrieved."
    refs = set(run["final_answer"]["knowledge_refs"])
    assert refs <= retrieved, f"ungrounded knowledge refs: {refs - retrieved}"
    _assert_traced_and_metered(session_factory, run)
    _assert_no_mutation(session_factory)


# --- Smoke 3: write proposal stays pending; nothing executes ---------------


def test_live_smoke_3_write_proposal_is_pending_and_never_executed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _live_env(monkeypatch)
    session_factory = _build_e2e_session_factory()
    seed = _seed_e2e_workspace(session_factory)

    run, events = _run_agent(
        session_factory,
        seed,
        goal=(
            "Prepare a follow-up action for this lead for three days from now, but do not "
            "execute it."
        ),
        profile="sales_copilot",
    )

    with session_factory() as db:
        actions = db.query(AgentAction).all()
    assert actions, f"The live model proposed no action; tools: {_requested_tools(events)}"
    assert {action.status for action in actions} == {"pending"}, "Nothing may run without approval."
    assert run["status"] == "waiting_for_approval"
    assert "waiting_for_approval" in _types(events)
    # The smoke deliberately never approves.
    _assert_no_mutation(session_factory)
