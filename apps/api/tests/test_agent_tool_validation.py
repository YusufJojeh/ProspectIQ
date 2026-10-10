from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from test_agent_behavior_evals import _env, _ScriptedProvider, _start
from test_workspace_e2e import _build_session_factory, _seed_workspace

import app.modules.agents.runtime as runtime_module
from app.modules.agents.models import AgentAction, AgentToolCall
from app.modules.agents.tool_registry import TOOL_REGISTRY, validate_arguments
from app.modules.crm.models import CrmActivity
from app.modules.leads.models import LeadNote

# --- Tool-argument schema validation ------------------------------------------
#
# The model chooses arguments; the registry schema is the contract. Every
# violation below must become a normalized, model-readable tool failure --
# never a crash inside a domain service and never a partial execution.


def _tool(name: str) -> Any:
    return TOOL_REGISTRY[name]


@pytest.mark.parametrize(
    ("tool", "arguments", "fragment"),
    [
        ("draft_outreach", {"tone": "professional"}, "tone"),  # invalid enum
        ("add_lead_note", {"note": "hi", "workspace_id": 7}, "workspace_id"),  # extra property
        ("create_follow_up", {"title": "x"}, "due_in_days"),  # missing required
        ("create_follow_up", {"title": "x", "due_in_days": "soon"}, "due_in_days"),  # wrong type
        ("create_follow_up", {"title": "x", "due_in_days": True}, "due_in_days"),  # bool is not int
        ("create_follow_up", {"title": "x", "due_in_days": 9999}, "due_in_days"),  # out of range
        ("add_lead_note", {"note": "x" * 1001}, "note"),  # overlong
        ("update_lead_tags", {"tags": [{"a": 1}]}, "tags"),  # nested: wrong item type
        ("update_lead_tags", {"tags": ["ok", ""]}, "tags"),  # nested: item too short
        ("update_lead_tags", {"tags": ["x" * 41]}, "tags"),  # nested: item too long
        ("update_lead_tags", {"tags": []}, "tags"),  # minItems
        ("update_lead_tags", {"tags": "a,b"}, "tags"),  # array expected
        ("search_sales_knowledge", {"query": "q", "collection_types": ["nope"]}, "collection_types"),
        ("search_sales_knowledge", {"query": "q", "limit": 0}, "limit"),
    ],
)
def test_invalid_arguments_yield_a_readable_error(
    tool: str, arguments: dict[str, Any], fragment: str
) -> None:
    error = validate_arguments(_tool(tool), arguments)
    assert error is not None, (tool, arguments)
    assert fragment in error


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("draft_outreach", {}),
        ("draft_outreach", {"tone": "consultative"}),
        ("add_lead_note", {"note": "fine"}),
        ("create_follow_up", {"title": "Call", "due_in_days": 3}),
        ("update_lead_tags", {"tags": ["a", "b"]}),
        ("search_sales_knowledge", {"query": "booking", "collection_types": ["services"], "limit": 3}),
    ],
)
def test_conforming_arguments_pass(tool: str, arguments: dict[str, Any]) -> None:
    assert validate_arguments(_tool(tool), arguments) is None


def test_every_registered_tool_accepts_empty_or_reports_its_required_fields() -> None:
    """No tool schema may crash the validator, whatever its shape."""
    for name, tool in TOOL_REGISTRY.items():
        error = validate_arguments(tool, {})
        required = tool.parameters.get("required") or []
        assert (error is None) == (not required), (name, error)


def test_every_violation_is_a_tool_failure_and_nothing_executes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End to end through the runtime with a model that keeps sending bad
    arguments (plus a tool that does not exist)."""
    _env(
        monkeypatch,
        AGENT_MAX_STEPS="20",
        AGENT_MAX_MODEL_CALLS="20",
        AGENT_MAX_CONSECUTIVE_TOOL_FAILURES="10",
    )
    provider = _ScriptedProvider(
        calls=[
            ("draft_outreach", {"tone": "professional"}),  # invalid enum
            ("add_lead_note", {"note": "hi", "workspace_id": 7}),  # extra property
            ("create_follow_up", {"title": "x"}),  # missing property
            ("create_follow_up", {"title": "x", "due_in_days": "soon"}),  # wrong type
            ("update_lead_tags", {"tags": [{"a": 1}]}),  # nested malformed
            ("add_lead_note", {"note": "x" * 5000}),  # overlong
            ("delete_everything", {"confirm": True}),  # unknown tool
        ],
        final={"answer": "Nothing valid was possible.", "confidence": 0.1},
    )
    monkeypatch.setattr(runtime_module.httpx, "Client", provider)
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    run, events = _start(session_factory, seed, goal="Do things.", profile="sales_copilot")

    failed = [event for event in events if event["event_type"] == "tool_failed"]
    assert len(failed) == 7, [e["event_type"] for e in events]
    assert run["status"] == "completed", run["status"]
    assert run["final_answer"]["answer"]
    with session_factory() as db:
        assert db.query(AgentAction).count() == 0, "Nothing invalid may reach the action gate."
        assert db.query(LeadNote).count() == 0
        assert db.query(CrmActivity).count() == 0
        assert not db.query(AgentToolCall).filter(AgentToolCall.status == "ok").all()


# --- One runtime, four profiles -------------------------------------------------


def test_there_is_one_agent_runtime_and_exactly_four_profiles() -> None:
    from app.modules.agents.tool_registry import (
        PROFILE_ADMIN_ASSISTANT,
        PROFILE_READ_ONLY,
        PROFILE_RESEARCH,
        PROFILE_SALES_COPILOT,
    )

    agents_dir = Path(runtime_module.__file__).parent
    runtime_classes = [
        f"{path.name}:{match}"
        for path in agents_dir.glob("*.py")
        for match in re.findall(r"^class (\w*Runtime)\b", path.read_text(encoding="utf-8"), re.M)
    ]
    assert runtime_classes == ["runtime.py:AgentRuntime"]
    assert {
        PROFILE_RESEARCH, PROFILE_SALES_COPILOT, PROFILE_READ_ONLY, PROFILE_ADMIN_ASSISTANT
    } == {"research", "sales_copilot", "read_only", "admin_assistant"}


# --- External send has exactly one door -----------------------------------------


def test_external_send_is_reachable_only_through_the_gateway_inside_the_tool_executor() -> None:
    app_dir = Path(runtime_module.__file__).parents[2]
    importers = sorted(
        str(path.relative_to(app_dir)).replace("\\", "/")
        for path in app_dir.rglob("*.py")
        if "send_gateway" in path.read_text(encoding="utf-8")
        and path.name != "send_gateway.py"
    )
    assert importers == ["modules/agents/tool_executor.py"], importers
    for forbidden in ("smtplib", "sendgrid", "twilio"):
        assert not [
            p for p in app_dir.rglob("*.py") if f"import {forbidden}" in p.read_text(encoding="utf-8")
        ], forbidden
