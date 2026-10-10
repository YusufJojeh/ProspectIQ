from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.modules.leads.models import Lead
from app.modules.research.contradiction import ContradictionDetector
from app.modules.research.repository import ResearchRepository
from app.modules.research.schemas import ResearchDepth, ResearchRunResult
from app.modules.research.tools import TOOL_DEFINITIONS, ResearchToolExecutor
from app.shared.enums.jobs import ProviderFetchStatus

logger = logging.getLogger(__name__)

_NO_EXTERNAL_CALL_TOOLS = frozenset(
    {
        "get_existing_evidence",
        "get_previous_research",
        "get_lead_score_breakdown",
        "get_icp_profile",
        "resolve_company_domain",
        "compare_evidence",
    }
)

# Deterministic tool sequence used when research_agent_runtime == "stub" (tests
# and demo mode): looks at existing evidence, does one broad search, tries one
# crawl, then compares evidence -- enough to exercise the full loop without
# ever calling OpenAI.
_STUB_SCRIPT: tuple[str, ...] = (
    "get_existing_evidence",
    "search_web_tavily",
    "crawl_company_site",
    "compare_evidence",
)


@dataclass(frozen=True, slots=True)
class ToolCallRequest:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class AgentTurn:
    tool_call: ToolCallRequest | None
    final_content: str | None


class ToolCaller(Protocol):
    def step(
        self, messages: list[dict[str, Any]], tool_defs: list[dict[str, Any]]
    ) -> AgentTurn: ...


class _OpenAIToolCaller:
    """Non-streaming, single-tool-call-per-round OpenAI chat completions caller.

    One round trip per loop iteration keeps the bounded agent loop simple to
    reason about: the loop decides whether a tool call is affordable *before*
    it is executed, so there is never a partially-applied batch of tool calls
    to unwind.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def step(self, messages: list[dict[str, Any]], tool_defs: list[dict[str, Any]]) -> AgentTurn:
        with httpx.Client(
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={
                "Authorization": f"Bearer {self._settings.openai_api_key}",
                "Content-Type": "application/json",
            },
        ) as client:
            response = client.post(
                f"{self._settings.openai_base_url.rstrip('/')}/chat/completions",
                json={
                    "model": self._settings.openai_model,
                    "messages": messages,
                    "tools": tool_defs,
                    "tool_choice": "auto",
                },
            )
            response.raise_for_status()
            payload = response.json()

        message = payload["choices"][0]["message"]
        tool_calls = message.get("tool_calls")
        if tool_calls:
            call = tool_calls[0]
            func = call.get("function", {})
            try:
                arguments = json.loads(func.get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {}
            return AgentTurn(
                tool_call=ToolCallRequest(
                    id=call.get("id", ""), name=func.get("name", ""), arguments=arguments
                ),
                final_content=None,
            )
        return AgentTurn(tool_call=None, final_content=message.get("content") or "")


class _StubToolCaller:
    def __init__(self) -> None:
        self._index = 0

    def step(self, messages: list[dict[str, Any]], tool_defs: list[dict[str, Any]]) -> AgentTurn:
        if self._index >= len(_STUB_SCRIPT):
            return AgentTurn(
                tool_call=None,
                final_content="Stub research loop finished after its scripted tool sequence.",
            )
        name = _STUB_SCRIPT[self._index]
        self._index += 1
        return AgentTurn(
            tool_call=ToolCallRequest(id=f"stub-{self._index}", name=name, arguments={}),
            final_content=None,
        )


class ResearchAgentLoop:
    """Bounded LLM tool-calling research loop -- the mode="agentic" alternative
    to ResearchOrchestrator's fixed-step mode="planned" flow.

    The LLM only ever names one of TOOL_DEFINITIONS' fixed tools; it never
    supplies a URL or Apify Actor ID, so it cannot steer a crawl anywhere the
    security/allowlist layer in app.modules.provider_apify hasn't already
    approved. Every budget (tool calls, external searches, crawls, sources,
    wall-clock runtime) is enforced here, in the loop, before a tool call is
    ever executed -- not inside the tool executor -- so a verbose or
    misbehaving model can never run past app.core.config's research_agent_max_*
    settings.
    """

    def __init__(
        self,
        *,
        contradiction_detector: ContradictionDetector | None = None,
        research_repository: ResearchRepository | None = None,
    ) -> None:
        self.contradiction_detector = contradiction_detector or ContradictionDetector()
        self.research_repository = research_repository or ResearchRepository()

    def run(
        self, db: Session, *, workspace_id: int, lead: Lead, depth: ResearchDepth
    ) -> ResearchRunResult:
        settings = get_settings()
        runtime = settings.research_agent_runtime
        if runtime == "blocked":
            return ResearchRunResult(
                depth=depth,
                mode="agentic",
                status=ProviderFetchStatus.ERROR.value,
                message=(
                    "Agentic research is unavailable because OPENAI_API_KEY is not configured."
                ),
            )

        executor = ResearchToolExecutor(db, workspace_id=workspace_id, lead=lead)
        caller: ToolCaller = _StubToolCaller() if runtime == "stub" else _OpenAIToolCaller(settings)
        tool_defs = [spec.as_openai_tool() for spec in TOOL_DEFINITIONS]
        messages = self._build_messages(lead, depth)

        max_calls = settings.research_agent_max_tool_calls
        max_searches = settings.research_agent_max_external_searches
        max_crawls = settings.research_agent_max_crawls
        max_sources = settings.research_agent_max_sources
        max_runtime_seconds = settings.research_agent_max_runtime_seconds

        started_at = time.monotonic()
        tool_calls_made = 0
        final_summary = ""

        while tool_calls_made < max_calls and (time.monotonic() - started_at) < max_runtime_seconds:
            turn = caller.step(messages, tool_defs)
            if turn.tool_call is None:
                final_summary = turn.final_content or ""
                break

            name = turn.tool_call.name
            result = self._execute_within_budget(
                executor,
                name,
                turn.tool_call.arguments,
                max_searches=max_searches,
                max_crawls=max_crawls,
                max_sources=max_sources,
            )
            tool_calls_made += 1
            messages.append(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": turn.tool_call.id,
                            "type": "function",
                            "function": {
                                "name": name,
                                "arguments": json.dumps(turn.tool_call.arguments),
                            },
                        }
                    ],
                }
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": turn.tool_call.id,
                    "content": json.dumps(result, default=str),
                }
            )
        else:
            final_summary = "Research agent stopped after reaching its tool-call or runtime bound."

        contradictions = self.contradiction_detector.detect(
            executor.facts_created, executor.fetches_by_id
        )
        self.research_repository.save_contradictions(
            db, workspace_id=workspace_id, lead_id=lead.id, contradictions=contradictions
        )

        providers_used = sorted({fetch.provider for fetch in executor.fetches_by_id.values()})
        status = (
            ProviderFetchStatus.OK.value
            if executor.fetches_by_id
            else ProviderFetchStatus.ERROR.value
        )
        last_fetch_public_id = None
        if executor.fetches_by_id:
            last_fetch = max(executor.fetches_by_id.values(), key=lambda fetch: fetch.id)
            last_fetch_public_id = last_fetch.public_id

        message = final_summary or (
            f"Agentic research completed using {tool_calls_made} tool call(s)."
            if status == ProviderFetchStatus.OK.value
            else "Agentic research made no successful provider calls."
        )

        return ResearchRunResult(
            depth=depth,
            mode="agentic",
            providers_used=providers_used,
            steps_executed=len(executor.fetches_by_id),
            facts_created=len(executor.facts_created),
            contradictions=contradictions,
            status=status,
            message=message,
            last_provider_fetch_public_id=last_fetch_public_id,
            tool_calls_made=tool_calls_made,
        )

    def _execute_within_budget(
        self,
        executor: ResearchToolExecutor,
        name: str,
        arguments: dict[str, Any],
        *,
        max_searches: int,
        max_crawls: int,
        max_sources: int,
    ) -> dict[str, Any]:
        if name in {"search_web_tavily", "search_google_serpapi"} and (
            executor.searches_performed >= max_searches
        ):
            return {"error": "Search budget exhausted for this research run."}
        if name in {"crawl_company_site", "crawl_reviews"} and executor.crawls_performed >= max_crawls:
            return {"error": "Crawl budget exhausted for this research run."}
        if name not in _NO_EXTERNAL_CALL_TOOLS and executor.sources_gathered >= max_sources:
            return {"error": "Source budget exhausted for this research run."}
        return executor.execute(name, arguments)

    def _build_messages(self, lead: Lead, depth: ResearchDepth) -> list[dict[str, Any]]:
        system = (
            "You are a bounded research agent for LeadScope AI. Gather evidence about the "
            "given business by calling tools, then reply with a short plain-text summary of "
            "what you found and stop calling tools once you have enough evidence for this "
            f"depth ({depth}). Prefer get_existing_evidence and get_previous_research before "
            "spending external searches or crawls. You cannot supply a URL or Actor ID to any "
            "crawl tool -- they always resolve their own target from evidence already on file."
        )
        user = (
            f"Lead: {lead.company_name}\n"
            f"City: {lead.city or 'unknown'}\n"
            f"Category: {lead.category or 'unknown'}\n"
            f"Known website: {lead.website_url or 'none yet'}"
        )
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
