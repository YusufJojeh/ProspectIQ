from __future__ import annotations

from app.modules.agents.profiles import SALES_COPILOT_PROFILE, tools_for
from app.modules.agents.runtime import tools_for_run
from app.modules.agents.tool_registry import RAG


def test_lead_bound_run_keeps_every_profile_tool() -> None:
    expected = {tool.name for tool in tools_for(SALES_COPILOT_PROFILE, role="admin")}
    actual = {
        tool.name for tool in tools_for_run(SALES_COPILOT_PROFILE, role="admin", has_lead=True)
    }
    assert actual == expected


def test_workspace_run_is_offered_only_lead_free_knowledge_tools() -> None:
    tools = tools_for_run(SALES_COPILOT_PROFILE, role="admin", has_lead=False)
    names = {tool.name for tool in tools}

    assert tools, "a workspace run must still be able to search sales knowledge"
    assert all(tool.tool_type == RAG for tool in tools)
    assert "search_sales_knowledge" in names
    assert "match_capabilities_to_lead" not in names
    assert "get_lead_context" not in names
