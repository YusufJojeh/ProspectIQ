from __future__ import annotations

from dataclasses import dataclass

from app.modules.agents.tool_registry import (
    HIGH,
    LOW,
    MEDIUM,
    PERM_CRM_WRITE,
    PERM_KNOWLEDGE_READ,
    PERM_LEAD_READ,
    PERM_LEAD_WRITE,
    PERM_OUTREACH_WRITE,
    PERM_RESEARCH_RUN,
    PROFILE_ADMIN_ASSISTANT,
    PROFILE_READ_ONLY,
    PROFILE_RESEARCH,
    PROFILE_SALES_COPILOT,
    TOOL_REGISTRY,
    ToolDefinition,
    tools_for_profile,
)
from app.modules.auth.permissions import ROLE_PERMISSIONS

# --- Agent profiles ------------------------------------------------------
#
# A profile is a POLICY, not an engine. There is exactly one AgentRuntime;
# a profile only decides which tools that runtime is allowed to describe to
# the model, what risk ceiling applies, and which system prompt it runs
# under. Nothing here contains a loop, a planner, or a workflow -- adding a
# profile must never mean adding a second agent implementation.


@dataclass(frozen=True, slots=True)
class AgentProfile:
    key: str
    label: str
    description: str
    #: The tools this profile may use. A tool must ALSO name the profile in
    #: its own allowed_profiles, so neither side can unilaterally widen
    #: access.
    tool_names: frozenset[str]
    max_risk: str
    prompt_key: str
    prompt_guidance: str


def _tools_of_type(*types: str) -> frozenset[str]:
    return frozenset(tool.name for tool in TOOL_REGISTRY.values() if tool.tool_type in types)


_READ_ONLY_NAMES = _tools_of_type("read", "rag")
_ALL_NAMES = frozenset(TOOL_REGISTRY)


RESEARCH_PROFILE = AgentProfile(
    key=PROFILE_RESEARCH,
    label="Lead Research",
    description="Investigates a lead with external research and proposes evidence-backed updates.",
    tool_names=_ALL_NAMES,
    max_risk=HIGH,
    prompt_key="agent.research",
    prompt_guidance=(
        "You investigate one lead. Ground every claim in evidence you retrieved this run, "
        "and never assert a score, coverage, confidence or freshness value yourself -- read "
        "those from the tools that compute them."
    ),
)

SALES_COPILOT_PROFILE = AgentProfile(
    key=PROFILE_SALES_COPILOT,
    label="Sales Copilot",
    description=(
        "Helps a salesperson act on a lead: matches the lead's problems to what this "
        "workspace can actually deliver, and drafts outreach grounded in approved "
        "internal knowledge."
    ),
    tool_names=_ALL_NAMES,
    max_risk=MEDIUM,
    prompt_key="agent.sales_copilot",
    prompt_guidance=(
        "You help a salesperson. Every claim about what we offer or have delivered must come "
        "from search_sales_knowledge and be cited; if the knowledge base does not support a "
        "claim, say so rather than inventing a capability, a client name or a number. "
        "Outreach you draft is a proposal for a human to review, never a sent message."
    ),
)

READ_ONLY_PROFILE = AgentProfile(
    key=PROFILE_READ_ONLY,
    label="Read Only",
    description="Answers questions from stored data and approved knowledge. Changes nothing.",
    tool_names=_READ_ONLY_NAMES,
    max_risk=LOW,
    prompt_key="agent.read_only",
    prompt_guidance=(
        "You can only read. If answering would require changing data, running external "
        "research, or spending provider budget, say what you would need instead of doing it."
    ),
)

ADMIN_ASSISTANT_PROFILE = AgentProfile(
    key=PROFILE_ADMIN_ASSISTANT,
    label="Admin Assistant",
    description="Full tool access for workspace administrators, still behind the approval gate.",
    tool_names=_ALL_NAMES,
    max_risk=HIGH,
    prompt_key="agent.admin_assistant",
    prompt_guidance=(
        "You assist a workspace administrator. Wider tool access does not mean fewer "
        "approvals: every write is still proposed for a human decision."
    ),
)

PROFILES: dict[str, AgentProfile] = {
    profile.key: profile
    for profile in (
        RESEARCH_PROFILE,
        SALES_COPILOT_PROFILE,
        READ_ONLY_PROFILE,
        ADMIN_ASSISTANT_PROFILE,
    )
}

DEFAULT_PROFILE_KEY = PROFILE_RESEARCH


def get_profile(key: str | None) -> AgentProfile:
    """Resolve a profile key, falling back to research.

    An unknown key resolves to the default rather than raising: a profile is
    a restriction, and a typo must never be able to produce a run with no
    restrictions at all.
    """
    return PROFILES.get(key or DEFAULT_PROFILE_KEY, PROFILES[DEFAULT_PROFILE_KEY])


# --- Role -> agent permission mapping ------------------------------------
#
# The agent permission vocabulary is intentionally separate from the
# workspace permission vocabulary: a tool asks "may this caller write to a
# lead?", not "is this caller a manager?". The mapping below is the single
# place the two meet, so a change to workspace roles cannot silently widen
# what an agent may do.

_PERMISSION_MAP: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("leads:view", (PERM_LEAD_READ, PERM_KNOWLEDGE_READ)),
    ("leads:manage", (PERM_LEAD_WRITE, PERM_CRM_WRITE)),
    # research:run gates EXTERNAL PROVIDER SPEND (Tavily, SerpAPI, Apify
    # crawls), so it maps only from searches:run. "ai_analysis:run" is about
    # analysing data the workspace already paid to collect and deliberately
    # does not grant it -- otherwise every member could spend the budget that
    # searches:run exists to control.
    ("searches:run", (PERM_RESEARCH_RUN,)),
    ("outreach:manage", (PERM_OUTREACH_WRITE,)),
)


def agent_permissions_for_role(role: str) -> frozenset[str]:
    workspace_permissions = set(ROLE_PERMISSIONS.get(role, ()))
    granted: set[str] = set()
    for workspace_permission, agent_permissions in _PERMISSION_MAP:
        if workspace_permission in workspace_permissions:
            granted.update(agent_permissions)
    return frozenset(granted)


def tools_for(profile: AgentProfile, *, role: str) -> list[ToolDefinition]:
    """The tools a given (profile, role) pair may actually use.

    This is the only input to the provider-facing tool list, so a tool the
    caller is not entitled to is never described to the model at all -- it is
    not merely rejected after the model asks for it.
    """
    return tools_for_profile(
        allowed_names=profile.tool_names,
        granted_permissions=agent_permissions_for_role(role),
        max_risk=profile.max_risk,
    )


__all__ = [
    "ADMIN_ASSISTANT_PROFILE",
    "DEFAULT_PROFILE_KEY",
    "PROFILES",
    "READ_ONLY_PROFILE",
    "RESEARCH_PROFILE",
    "SALES_COPILOT_PROFILE",
    "AgentProfile",
    "agent_permissions_for_role",
    "get_profile",
    "tools_for",
]
