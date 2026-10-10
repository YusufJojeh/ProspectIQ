from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.config import get_settings
from app.modules.knowledge.constants import COLLECTION_TYPES
from app.modules.proposals.brands import BRAND_KEYS

# --- The single authoritative tool registry -----------------------------
#
# One ToolDefinition per tool, and nothing about a tool is declared
# anywhere else: the provider-native function schema, the risk level, the
# permission requirement, the profile allowlist, the approval requirement,
# the execution timeout, the result bound and the cost class all come from
# here. The runtime, the executor, the action gate and the profile policy
# all read this table rather than re-deriving any of it.

# Tool types. READ/RESEARCH/RAG return information; GENERATIVE produces
# content without mutating anything; WRITE_PROPOSAL and ACTION can only
# ever reach a domain service through an approved AgentAction.
READ = "read"
RESEARCH = "research"
RAG = "rag"
GENERATIVE = "generative"
WRITE_PROPOSAL = "write_proposal"
ACTION = "action"

TOOL_TYPES: frozenset[str] = frozenset(
    {READ, RESEARCH, RAG, GENERATIVE, WRITE_PROPOSAL, ACTION}
)

LOW = "low"
MEDIUM = "medium"
HIGH = "high"
BLOCKED = "blocked"

#: Ordered, so a profile can express a ceiling ("nothing above MEDIUM")
#: rather than enumerating levels.
RISK_ORDER: tuple[str, ...] = (LOW, MEDIUM, HIGH, BLOCKED)


def risk_rank(risk_level: str) -> int:
    try:
        return RISK_ORDER.index(risk_level)
    except ValueError:
        return len(RISK_ORDER)


# Cost classes drive budget accounting and model routing, not pricing
# itself -- concrete rates live in the ProviderPricing table.
COST_NONE = "none"  # pure database read
COST_CHEAP = "cheap"  # one embedding or small model call
COST_EXTERNAL = "external"  # billable third-party API call
COST_EXPENSIVE = "expensive"  # multi-call pipeline (crawl, deep research)

# Agent profiles. A profile is a policy over this registry, never a second
# runtime -- see app.modules.agents.profiles.
PROFILE_RESEARCH = "research"
PROFILE_SALES_COPILOT = "sales_copilot"
PROFILE_READ_ONLY = "read_only"
PROFILE_ADMIN_ASSISTANT = "admin_assistant"

ALL_PROFILES: tuple[str, ...] = (
    PROFILE_RESEARCH,
    PROFILE_SALES_COPILOT,
    PROFILE_READ_ONLY,
    PROFILE_ADMIN_ASSISTANT,
)

# Permission keys, checked against the acting user's role before a tool is
# offered to the model at all.
PERM_LEAD_READ = "lead:read"
PERM_LEAD_WRITE = "lead:write"
PERM_RESEARCH_RUN = "research:run"
PERM_KNOWLEDGE_READ = "knowledge:read"
PERM_OUTREACH_WRITE = "outreach:write"
PERM_CRM_WRITE = "crm:write"

_NO_PARAMS: dict[str, Any] = {"type": "object", "properties": {}, "additionalProperties": False}

_DEFAULT_TIMEOUT_SECONDS = 30.0
_DEFAULT_MAX_RESULT_BYTES = 16384


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """One entry in the single authoritative tool registry.

    `requires_approval` is independent of `tool_type`: most WRITE_PROPOSAL
    tools require approval, but `draft_outreach` does not, because it only
    ever creates a *draft* the human hasn't acted on yet -- the mutation the
    approval gate actually protects is `save_outreach_draft`/`send`.

    No tool schema here accepts workspace_id/lead_id/user_id/actor_id/url
    -- those always come from the AgentRun's own bound context, never from
    the model. That absence is the structural reason a prompt-injected
    model cannot reach another tenant's data.
    """

    name: str
    description: str
    parameters: dict[str, Any]
    tool_type: str
    risk_level: str
    requires_approval: bool
    resource_type: str | None = None
    required_permissions: tuple[str, ...] = field(default_factory=tuple)
    allowed_profiles: tuple[str, ...] = ALL_PROFILES
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS
    max_result_bytes: int = _DEFAULT_MAX_RESULT_BYTES
    cost_class: str = COST_NONE
    external_io: bool = False
    #: A settings flag that must be true for this tool to exist at all. A
    #: flagged-off tool is never described to the model, never executable and
    #: never approvable -- three independent refusals, because one forgotten
    #: check on an irreversible send is one too many.
    feature_flag: str | None = None

    @property
    def mutating(self) -> bool:
        """True iff executing this tool can change stored business data.

        GENERATIVE tools are *not* mutating even though they call a model:
        they return content, and persisting it is a separate approved
        action.
        """
        return self.tool_type in {WRITE_PROPOSAL, ACTION} and self.requires_approval

    def as_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


READ_RESEARCH_TOOLS: tuple[ToolDefinition, ...] = (
    ToolDefinition(
        name="get_lead_context",
        description="Get the lead's core profile fields: name, city, category, website, status, data completeness.",
        parameters=_NO_PARAMS,
        tool_type=READ,
        risk_level=LOW,
        requires_approval=False,
        required_permissions=(PERM_LEAD_READ,),
    ),
    ToolDefinition(
        name="get_lead_notes",
        description="List the notes colleagues have written on this lead, newest first.",
        parameters=_NO_PARAMS,
        tool_type=READ,
        risk_level=LOW,
        requires_approval=False,
        required_permissions=(PERM_LEAD_READ,),
    ),
    ToolDefinition(
        name="get_lead_activity",
        description="List CRM activities (calls, follow-ups, meetings) logged against this lead's open deal.",
        parameters=_NO_PARAMS,
        tool_type=READ,
        risk_level=LOW,
        requires_approval=False,
        required_permissions=(PERM_LEAD_READ,),
    ),
    ToolDefinition(
        name="get_contact_channels",
        description="List the contact channels evidenced for this lead (phone, email, WhatsApp, contact form, social).",
        parameters=_NO_PARAMS,
        tool_type=READ,
        risk_level=LOW,
        requires_approval=False,
        required_permissions=(PERM_LEAD_READ,),
    ),
    ToolDefinition(
        name="get_service_catalog",
        description="List this workspace's service and capability documents, so you know what we can actually offer before proposing anything.",
        parameters=_NO_PARAMS,
        tool_type=READ,
        risk_level=LOW,
        requires_approval=False,
        required_permissions=(PERM_KNOWLEDGE_READ,),
        cost_class=COST_CHEAP,
    ),
    ToolDefinition(
        name="get_existing_evidence",
        description="List every normalized fact already stored for this lead, across all providers.",
        parameters=_NO_PARAMS,
        tool_type=READ,
        risk_level=LOW,
        requires_approval=False,
        required_permissions=(PERM_LEAD_READ,),
    ),
    ToolDefinition(
        name="get_evidence_graph",
        description="Resolve gathered facts into the canonical Evidence Graph (claims, contradictions, confidence, coverage, digital_maturity).",
        parameters=_NO_PARAMS,
        tool_type=READ,
        risk_level=LOW,
        requires_approval=False,
        required_permissions=(PERM_LEAD_READ,),
    ),
    ToolDefinition(
        name="get_research_history",
        description="List this lead's past research runs and the deltas (fact changes) each one produced.",
        parameters=_NO_PARAMS,
        tool_type=READ,
        risk_level=LOW,
        requires_approval=False,
        required_permissions=(PERM_LEAD_READ,),
    ),
    ToolDefinition(
        name="get_previous_research",
        description="List deduplicated evidence items gathered in prior research runs for this lead.",
        parameters=_NO_PARAMS,
        tool_type=READ,
        risk_level=LOW,
        requires_approval=False,
        required_permissions=(PERM_LEAD_READ,),
    ),
    ToolDefinition(
        name="get_icp_profile",
        description="Get the workspace's active Ideal Customer Profile definitions.",
        parameters=_NO_PARAMS,
        tool_type=READ,
        risk_level=LOW,
        requires_approval=False,
        required_permissions=(PERM_LEAD_READ,),
    ),
    ToolDefinition(
        name="get_score_breakdown",
        description="Get the lead's latest fit/need/urgency/reachability score breakdown, if scored.",
        parameters=_NO_PARAMS,
        tool_type=READ,
        risk_level=LOW,
        requires_approval=False,
        required_permissions=(PERM_LEAD_READ,),
    ),
    ToolDefinition(
        name="get_delta_changes",
        description="List the most recent Delta Intelligence change events detected for this lead (what changed between research runs).",
        parameters=_NO_PARAMS,
        tool_type=READ,
        risk_level=LOW,
        requires_approval=False,
        required_permissions=(PERM_LEAD_READ,),
    ),
    ToolDefinition(
        name="get_outreach_history",
        description="List outreach drafts/messages previously generated for this lead and their status.",
        parameters=_NO_PARAMS,
        tool_type=READ,
        risk_level=LOW,
        requires_approval=False,
        required_permissions=(PERM_LEAD_READ,),
    ),
    ToolDefinition(
        name="search_web_tavily",
        description="Fast, broad web search for the lead's business. Good first step to discover the official website and general presence.",
        parameters=_NO_PARAMS,
        tool_type=RESEARCH,
        risk_level=LOW,
        requires_approval=False,
        required_permissions=(PERM_RESEARCH_RUN,),
        cost_class=COST_EXTERNAL,
        external_io=True,
        timeout_seconds=30.0,
    ),
    ToolDefinition(
        name="search_google_serpapi",
        description="Google-oriented search as redundancy/cross-check against Tavily results.",
        parameters=_NO_PARAMS,
        tool_type=RESEARCH,
        risk_level=LOW,
        requires_approval=False,
        required_permissions=(PERM_RESEARCH_RUN,),
        cost_class=COST_EXTERNAL,
        external_io=True,
        timeout_seconds=30.0,
    ),
    ToolDefinition(
        name="crawl_company_site",
        description="Deep-crawl the lead's own official website for services, contact details, and online-presence facts. Takes no URL parameter -- always targets the site already found for this lead.",
        parameters=_NO_PARAMS,
        tool_type=RESEARCH,
        risk_level=LOW,
        requires_approval=False,
        required_permissions=(PERM_RESEARCH_RUN,),
        cost_class=COST_EXPENSIVE,
        external_io=True,
        timeout_seconds=90.0,
    ),
    ToolDefinition(
        name="crawl_reviews",
        description="Deep-crawl review sources for this lead. Takes no URL parameter -- resolved server-side.",
        parameters=_NO_PARAMS,
        tool_type=RESEARCH,
        risk_level=LOW,
        requires_approval=False,
        required_permissions=(PERM_RESEARCH_RUN,),
        cost_class=COST_EXPENSIVE,
        external_io=True,
        timeout_seconds=90.0,
    ),
    ToolDefinition(
        name="compare_evidence",
        description="Resolve gathered facts into the Evidence Graph, surfacing contradictions and current confidence/coverage. Call before deciding whether enough evidence exists.",
        parameters=_NO_PARAMS,
        tool_type=RESEARCH,
        risk_level=LOW,
        requires_approval=False,
        required_permissions=(PERM_LEAD_READ,),
    ),
    ToolDefinition(
        name="refresh_lead_research",
        description="Run one bounded quick-depth research pass (search + crawl + compare) for this lead using the existing research pipeline, then return the refreshed Evidence Graph.",
        parameters=_NO_PARAMS,
        tool_type=RESEARCH,
        risk_level=MEDIUM,
        requires_approval=False,
        required_permissions=(PERM_RESEARCH_RUN,),
        cost_class=COST_EXPENSIVE,
        external_io=True,
        timeout_seconds=120.0,
        allowed_profiles=(PROFILE_RESEARCH, PROFILE_SALES_COPILOT, PROFILE_ADMIN_ASSISTANT),
    ),
)


WRITE_TOOLS: tuple[ToolDefinition, ...] = (
    ToolDefinition(
        name="draft_outreach",
        description="Generate (or regenerate) an outreach message draft for this lead. Does not send anything and does not require approval -- it only produces a draft for the human to review.",
        parameters={
            "type": "object",
            "properties": {
                "tone": {
                    "type": "string",
                    "enum": ["formal", "friendly", "consultative", "short_pitch"],
                },
                "regenerate": {"type": "boolean"},
                "language": {"type": "string"},
            },
            "additionalProperties": False,
        },
        tool_type=WRITE_PROPOSAL,
        risk_level=LOW,
        requires_approval=False,
        resource_type="outreach_message",
        required_permissions=(PERM_OUTREACH_WRITE,),
        cost_class=COST_CHEAP,
        max_result_bytes=32768,
        allowed_profiles=(PROFILE_RESEARCH, PROFILE_SALES_COPILOT, PROFILE_ADMIN_ASSISTANT),
    ),
    ToolDefinition(
        name="save_outreach_draft",
        description="Overwrite the lead's latest outreach draft with edited subject/message text. Requires human approval before the draft is changed.",
        parameters={
            "type": "object",
            "properties": {
                "subject": {"type": "string", "minLength": 1, "maxLength": 200},
                "message": {"type": "string", "minLength": 1, "maxLength": 5000},
            },
            "required": ["subject", "message"],
            "additionalProperties": False,
        },
        tool_type=WRITE_PROPOSAL,
        risk_level=MEDIUM,
        requires_approval=True,
        resource_type="outreach_message",
        required_permissions=(PERM_OUTREACH_WRITE,),
        allowed_profiles=(PROFILE_RESEARCH, PROFILE_SALES_COPILOT, PROFILE_ADMIN_ASSISTANT),
    ),
    ToolDefinition(
        name="draft_proposal",
        description=(
            "Draft a priced proposal / quotation for this lead in one of the workspace's "
            "branded layouts. Call search_sales_knowledge for pricing_guidance, "
            "past_proposals and proposal_templates FIRST: an amount is kept only when it "
            "appears in pricing you retrieved this run (a package total split across "
            "milestones counts), otherwise the line is left unpriced for the salesperson. "
            "Amounts are in major units (1500 = 1,500.00). Requires human approval; it "
            "creates a draft the salesperson reviews, prices and exports -- nothing is sent."
        ),
        parameters={
            "type": "object",
            "properties": {
                "brand": {"type": "string", "enum": list(BRAND_KEYS)},
                "title": {"type": "string", "minLength": 1, "maxLength": 200},
                "outcome": {"type": "string", "maxLength": 2000},
                "currency": {"type": "string", "minLength": 3, "maxLength": 3},
                "language": {"type": "string", "enum": ["en", "ar"]},
                "validity_days": {"type": "integer", "minimum": 7, "maximum": 90},
                "milestones": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 8,
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "minLength": 1, "maxLength": 200},
                            "description": {"type": "string", "maxLength": 600},
                            "amount": {"type": "number", "minimum": 0, "maximum": 10000000000},
                        },
                        "required": ["title"],
                        "additionalProperties": False,
                    },
                },
                "commercial_notes": {"type": "string", "maxLength": 2000},
                "pricing_basis": {
                    "type": "string",
                    "description": "Quote the retrieved pricing guidance the amounts come from.",
                    "maxLength": 1000,
                },
            },
            "required": ["brand", "title", "milestones"],
            "additionalProperties": False,
        },
        tool_type=WRITE_PROPOSAL,
        risk_level=MEDIUM,
        requires_approval=True,
        resource_type="proposal",
        required_permissions=(PERM_OUTREACH_WRITE,),
        allowed_profiles=(PROFILE_RESEARCH, PROFILE_SALES_COPILOT, PROFILE_ADMIN_ASSISTANT),
    ),
    ToolDefinition(
        name="add_lead_note",
        description="Add a note to the lead's record explaining an opportunity, risk, or observation. Requires human approval.",
        parameters={
            "type": "object",
            "properties": {"note": {"type": "string", "minLength": 1, "maxLength": 1000}},
            "required": ["note"],
            "additionalProperties": False,
        },
        tool_type=WRITE_PROPOSAL,
        risk_level=LOW,
        requires_approval=True,
        resource_type="lead_note",
        required_permissions=(PERM_LEAD_WRITE,),
        allowed_profiles=(PROFILE_RESEARCH, PROFILE_SALES_COPILOT, PROFILE_ADMIN_ASSISTANT),
    ),
    ToolDefinition(
        name="create_follow_up",
        description="Create a follow-up CRM activity for this lead, due a number of days from now. Requires human approval.",
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string", "minLength": 1, "maxLength": 200},
                "note": {"type": "string", "maxLength": 1000},
                "due_in_days": {"type": "integer", "minimum": 0, "maximum": 365},
            },
            "required": ["title", "due_in_days"],
            "additionalProperties": False,
        },
        tool_type=WRITE_PROPOSAL,
        risk_level=MEDIUM,
        requires_approval=True,
        resource_type="crm_activity",
        required_permissions=(PERM_CRM_WRITE,),
        allowed_profiles=(PROFILE_RESEARCH, PROFILE_SALES_COPILOT, PROFILE_ADMIN_ASSISTANT),
    ),
    ToolDefinition(
        name="create_lead_task",
        description=(
            "Create a task for this lead (implemented as a CRM follow-up activity -- the "
            "domain model has no separate 'task' concept, so this is the closest safe "
            "existing mutation). Requires human approval."
        ),
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string", "minLength": 1, "maxLength": 200},
                "note": {"type": "string", "maxLength": 1000},
                "due_in_days": {"type": "integer", "minimum": 0, "maximum": 365},
            },
            "required": ["title"],
            "additionalProperties": False,
        },
        tool_type=WRITE_PROPOSAL,
        risk_level=MEDIUM,
        requires_approval=True,
        resource_type="crm_activity",
        required_permissions=(PERM_CRM_WRITE,),
        allowed_profiles=(PROFILE_RESEARCH, PROFILE_SALES_COPILOT, PROFILE_ADMIN_ASSISTANT),
    ),
    ToolDefinition(
        name="update_lead_stage",
        description="Change the lead's pipeline status (e.g. reviewed, qualified, contacted). Requires human approval.",
        parameters={
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": [
                        "new",
                        "reviewed",
                        "qualified",
                        "contacted",
                        "interested",
                        "won",
                        "lost",
                        "archived",
                    ],
                },
                "note": {"type": "string", "maxLength": 1000},
            },
            "required": ["status"],
            "additionalProperties": False,
        },
        tool_type=WRITE_PROPOSAL,
        risk_level=MEDIUM,
        requires_approval=True,
        resource_type="lead",
        required_permissions=(PERM_LEAD_WRITE,),
        allowed_profiles=(PROFILE_RESEARCH, PROFILE_SALES_COPILOT, PROFILE_ADMIN_ASSISTANT),
    ),
    ToolDefinition(
        name="update_lead_tags",
        description=(
            "Add tags to the lead (stored in its enrichments.tags field -- the Lead model "
            "has no dedicated tags column, so this is the closest safe existing mutation). "
            "Requires human approval."
        ),
        parameters={
            "type": "object",
            "properties": {
                "tags": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1, "maxLength": 40},
                    "minItems": 1,
                    "maxItems": 20,
                }
            },
            "required": ["tags"],
            "additionalProperties": False,
        },
        tool_type=WRITE_PROPOSAL,
        risk_level=LOW,
        requires_approval=True,
        resource_type="lead",
        required_permissions=(PERM_LEAD_WRITE,),
        allowed_profiles=(PROFILE_RESEARCH, PROFILE_SALES_COPILOT, PROFILE_ADMIN_ASSISTANT),
    ),
    ToolDefinition(
        name="request_deep_research",
        description="Request a deep-depth research pass for this lead (more external searches/crawls than the default). Requires human approval because it consumes provider budget.",
        parameters={
            "type": "object",
            "properties": {
                "depth": {"type": "string", "enum": ["quick", "standard", "deep"]},
            },
            "additionalProperties": False,
        },
        tool_type=ACTION,
        risk_level=HIGH,
        requires_approval=True,
        resource_type="research_run",
        required_permissions=(PERM_RESEARCH_RUN,),
        cost_class=COST_EXPENSIVE,
        external_io=True,
        timeout_seconds=180.0,
        allowed_profiles=(PROFILE_RESEARCH, PROFILE_SALES_COPILOT, PROFILE_ADMIN_ASSISTANT),
    ),
)


RAG_TOOLS: tuple[ToolDefinition, ...] = (
    ToolDefinition(
        name="search_sales_knowledge",
        description=(
            "Search the workspace's own approved sales knowledge (service catalogue, "
            "capabilities, case studies, playbooks, objection handling, pricing guidance, "
            "proposal templates) and return cited passages. Use this to ground any claim "
            "about what we offer or have delivered; never assert such a claim from memory."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to look for, in natural language.",
                    "maxLength": 1000,
                },
                "collection_types": {
                    "type": "array",
                    "description": "Optional filter restricting the search to these kinds of documents.",
                    "items": {"type": "string", "enum": list(COLLECTION_TYPES)},
                    "maxItems": 6,
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": 20},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        tool_type=RAG,
        risk_level=LOW,
        requires_approval=False,
        required_permissions=(PERM_KNOWLEDGE_READ,),
        cost_class=COST_CHEAP,
        timeout_seconds=20.0,
    ),
    ToolDefinition(
        name="get_relevant_case_studies",
        description=(
            "Find case studies and portfolio work relevant to a described situation, with "
            "citations. Only cite a client, outcome or number that appears in a returned "
            "passage."
        ),
        parameters={
            "type": "object",
            "properties": {
                "situation": {
                    "type": "string",
                    "description": "The prospect's problem or industry, in natural language.",
                    "maxLength": 1000,
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": 10},
            },
            "required": ["situation"],
            "additionalProperties": False,
        },
        tool_type=RAG,
        risk_level=LOW,
        requires_approval=False,
        required_permissions=(PERM_KNOWLEDGE_READ,),
        cost_class=COST_CHEAP,
        timeout_seconds=20.0,
    ),
    ToolDefinition(
        name="get_sales_playbook",
        description=(
            "Retrieve the workspace's sales playbook, industry playbook or objection-handling "
            "guidance for a described situation, with citations."
        ),
        parameters={
            "type": "object",
            "properties": {
                "topic": {"type": "string", "maxLength": 1000},
                "limit": {"type": "integer", "minimum": 1, "maximum": 10},
            },
            "required": ["topic"],
            "additionalProperties": False,
        },
        tool_type=RAG,
        risk_level=LOW,
        requires_approval=False,
        required_permissions=(PERM_KNOWLEDGE_READ,),
        cost_class=COST_CHEAP,
        timeout_seconds=20.0,
    ),
    ToolDefinition(
        name="match_capabilities_to_lead",
        description=(
            "Match this lead's evidenced problems to services this workspace can actually "
            "deliver, with case-study proof. The opportunities and their confidence are "
            "computed by the backend from the Evidence Graph -- treat them as given, do not "
            "recompute or restate them as your own judgement."
        ),
        parameters=_NO_PARAMS,
        tool_type=RAG,
        risk_level=LOW,
        requires_approval=False,
        required_permissions=(PERM_LEAD_READ, PERM_KNOWLEDGE_READ),
        cost_class=COST_CHEAP,
        timeout_seconds=30.0,
    ),
)


#: --- External send tools -------------------------------------------------
#:
#: These are the only tools in the system whose effect leaves the building and
#: cannot be undone. They are DISABLED by default (external_send_enabled), and
#: they are HIGH risk and approval-required even when enabled. The approved
#: payload is hash-verified immediately before execution, so what a human read
#: is byte-for-byte what would be sent.
EXTERNAL_SEND_TOOLS: tuple[ToolDefinition, ...] = (
    ToolDefinition(
        name="send_email",
        description="Send an approved outreach email to this lead. Irreversible. Disabled unless the workspace has enabled external sending.",
        parameters={
            "type": "object",
            "properties": {
                "outreach_message_id": {"type": "string"},
                "to_email": {"type": "string"},
            },
            "required": ["outreach_message_id", "to_email"],
            "additionalProperties": False,
        },
        tool_type=ACTION,
        risk_level=HIGH,
        requires_approval=True,
        resource_type="outreach_message",
        required_permissions=(PERM_OUTREACH_WRITE,),
        cost_class=COST_EXTERNAL,
        external_io=True,
        feature_flag="external_send_enabled",
        allowed_profiles=(PROFILE_SALES_COPILOT, PROFILE_ADMIN_ASSISTANT),
    ),
    ToolDefinition(
        name="send_whatsapp",
        description="Send an approved WhatsApp message to this lead. Irreversible. Disabled unless the workspace has enabled external sending.",
        parameters={
            "type": "object",
            "properties": {
                "outreach_message_id": {"type": "string"},
                "to_number": {"type": "string"},
            },
            "required": ["outreach_message_id", "to_number"],
            "additionalProperties": False,
        },
        tool_type=ACTION,
        risk_level=HIGH,
        requires_approval=True,
        resource_type="outreach_message",
        required_permissions=(PERM_OUTREACH_WRITE,),
        cost_class=COST_EXTERNAL,
        external_io=True,
        feature_flag="external_send_enabled",
        allowed_profiles=(PROFILE_SALES_COPILOT, PROFILE_ADMIN_ASSISTANT),
    ),
    ToolDefinition(
        name="send_linkedin_message",
        description="Send an approved LinkedIn message to this lead. Irreversible. Disabled unless the workspace has enabled external sending.",
        parameters={
            "type": "object",
            "properties": {
                "outreach_message_id": {"type": "string"},
                "profile_url": {"type": "string"},
            },
            "required": ["outreach_message_id", "profile_url"],
            "additionalProperties": False,
        },
        tool_type=ACTION,
        risk_level=HIGH,
        requires_approval=True,
        resource_type="outreach_message",
        required_permissions=(PERM_OUTREACH_WRITE,),
        cost_class=COST_EXTERNAL,
        external_io=True,
        feature_flag="external_send_enabled",
        allowed_profiles=(PROFILE_SALES_COPILOT, PROFILE_ADMIN_ASSISTANT),
    ),
)

EXTERNAL_SEND_TOOL_NAMES: frozenset[str] = frozenset(
    tool.name for tool in EXTERNAL_SEND_TOOLS
)


TOOL_REGISTRY: dict[str, ToolDefinition] = {
    tool.name: tool
    for tool in (*READ_RESEARCH_TOOLS, *RAG_TOOLS, *WRITE_TOOLS, *EXTERNAL_SEND_TOOLS)
}


def get_tool(name: str) -> ToolDefinition | None:
    return TOOL_REGISTRY.get(name)


def tools_for_profile(
    *,
    allowed_names: frozenset[str],
    granted_permissions: frozenset[str],
    max_risk: str,
) -> list[ToolDefinition]:
    """The tools a given profile/permission set may actually use.

    This is the *only* place the provider-facing tool list is derived, so a
    tool the caller is not entitled to is never described to the model --
    it is not merely rejected after the model asks for it. Three
    independent conditions must all hold: the profile names the tool, the
    tool names the profile, and the acting user holds every permission the
    tool requires.
    """
    ceiling = risk_rank(max_risk)
    settings = get_settings()
    selected: list[ToolDefinition] = []
    for tool in TOOL_REGISTRY.values():
        if tool.name not in allowed_names:
            continue
        if tool.feature_flag is not None and not getattr(settings, tool.feature_flag, False):
            continue
        if risk_rank(tool.risk_level) > ceiling or tool.risk_level == BLOCKED:
            continue
        if not set(tool.required_permissions).issubset(granted_permissions):
            continue
        selected.append(tool)
    return selected


def _schema_error(schema: dict[str, Any], value: Any, path: str) -> str | None:
    """Checks `value` against the JSON-Schema subset the registry uses.

    Deliberately small: object/string/integer/number/boolean/array, enum,
    required, additionalProperties=false and min/max bounds. A keyword the
    registry never uses is simply not checked.
    """
    expected = schema.get("type")
    if expected == "object":
        if not isinstance(value, dict):
            return f"{path} must be an object."
        properties: dict[str, Any] = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                return f"{path}.{key} is required."
        for key, item in value.items():
            if key not in properties:
                if schema.get("additionalProperties") is False:
                    return f"{path}.{key} is not an accepted argument."
                continue
            error = _schema_error(properties[key], item, f"{path}.{key}")
            if error:
                return error
        return None
    if expected == "string" and not isinstance(value, str):
        return f"{path} must be a string."
    if expected == "boolean" and not isinstance(value, bool):
        return f"{path} must be a boolean."
    if expected == "integer" and (isinstance(value, bool) or not isinstance(value, int)):
        return f"{path} must be an integer."
    if expected == "number" and (isinstance(value, bool) or not isinstance(value, int | float)):
        return f"{path} must be a number."
    if expected == "array":
        if not isinstance(value, list):
            return f"{path} must be an array."
        if len(value) < schema.get("minItems", 0):
            return f"{path} needs at least {schema['minItems']} items."
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            return f"{path} has more than {schema['maxItems']} items."
        for index, item in enumerate(value):
            error = _schema_error(schema.get("items", {}), item, f"{path}[{index}]")
            if error:
                return error
        return None
    if "enum" in schema and value not in schema["enum"]:
        return f"{path} must be one of {schema['enum']}."
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            return f"{path} is too short."
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            return f"{path} exceeds {schema['maxLength']} characters."
    if isinstance(value, int | float) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            return f"{path} must be >= {schema['minimum']}."
        if "maximum" in schema and value > schema["maximum"]:
            return f"{path} must be <= {schema['maximum']}."
    return None


def validate_arguments(tool: ToolDefinition, arguments: dict[str, Any]) -> str | None:
    """Returns a model-readable error, or None when the arguments conform to
    the tool's registered input schema. Enforced once, at dispatch."""
    return _schema_error(tool.parameters, arguments, "arguments")


def openai_tools_for(tools: list[ToolDefinition]) -> list[dict[str, Any]]:
    return [tool.as_openai_tool() for tool in tools]


def all_openai_tools() -> list[dict[str, Any]]:
    return [tool.as_openai_tool() for tool in TOOL_REGISTRY.values()]


__all__ = [
    "ACTION",
    "EXTERNAL_SEND_TOOLS",
    "EXTERNAL_SEND_TOOL_NAMES",
    "RAG_TOOLS",
    "ALL_PROFILES",
    "BLOCKED",
    "COST_CHEAP",
    "COST_EXPENSIVE",
    "COST_EXTERNAL",
    "COST_NONE",
    "GENERATIVE",
    "HIGH",
    "LOW",
    "MEDIUM",
    "PERM_CRM_WRITE",
    "PERM_KNOWLEDGE_READ",
    "PERM_LEAD_READ",
    "PERM_LEAD_WRITE",
    "PERM_OUTREACH_WRITE",
    "PERM_RESEARCH_RUN",
    "PROFILE_ADMIN_ASSISTANT",
    "PROFILE_READ_ONLY",
    "PROFILE_RESEARCH",
    "PROFILE_SALES_COPILOT",
    "RAG",
    "READ",
    "READ_RESEARCH_TOOLS",
    "RESEARCH",
    "RISK_ORDER",
    "TOOL_REGISTRY",
    "TOOL_TYPES",
    "WRITE_PROPOSAL",
    "WRITE_TOOLS",
    "ToolDefinition",
    "all_openai_tools",
    "get_tool",
    "openai_tools_for",
    "risk_rank",
    "tools_for_profile",
    "validate_arguments",
]
