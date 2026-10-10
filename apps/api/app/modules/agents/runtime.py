from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

import httpx
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.core.errors import ConflictError, NotFoundError
from app.modules.agents import events
from app.modules.agents.action_gate import hash_payload
from app.modules.agents.models import AgentRun
from app.modules.agents.profiles import AgentProfile, get_profile, tools_for
from app.modules.agents.repository import AgentRepository
from app.modules.agents.schemas import AgentFinalAnswer
from app.modules.agents.tool_executor import AgentToolExecutor
from app.modules.agents.tool_registry import (
    RAG,
    READ,
    RESEARCH,
    TOOL_REGISTRY,
    WRITE_PROPOSAL,
    ToolDefinition,
    openai_tools_for,
    validate_arguments,
)
from app.modules.agents.untrusted import (
    SECURITY_PREAMBLE,
    detect_injection_markers,
    wrap_untrusted,
)
from app.modules.ai_runtime.prompts import PROMPT_AGENT_SYSTEM, PromptRegistry
from app.modules.ai_runtime.router import AgentModelRouter
from app.modules.ai_runtime.usage import (
    OPERATION_AGENT_RUN,
    OPERATION_CRAWL,
    OPERATION_EXTERNAL_SEARCH,
    UsageLedger,
)
from app.modules.leads.models import Lead
from app.modules.leads.repository import LeadsRepository
from app.modules.users.models import User

logger = logging.getLogger(__name__)

_SEARCH_TOOLS = frozenset({"search_web_tavily", "search_google_serpapi"})
_CRAWL_TOOLS = frozenset({"crawl_company_site", "crawl_reviews"})

#: Tool -> (provider, ledger operation) for the per-call-billed providers.
_EXTERNAL_PROVIDERS: dict[str, tuple[str, str]] = {
    "search_web_tavily": ("tavily", OPERATION_EXTERNAL_SEARCH),
    "search_google_serpapi": ("serpapi", OPERATION_EXTERNAL_SEARCH),
    "crawl_company_site": ("apify", OPERATION_CRAWL),
    "crawl_reviews": ("apify", OPERATION_CRAWL),
}

_STUB_SCRIPT: tuple[str, ...] = (
    "get_lead_context",
    "get_evidence_graph",
    "search_web_tavily",
    "crawl_company_site",
    "compare_evidence",
    "get_score_breakdown",
    "draft_outreach",
    "add_lead_note",
    "create_follow_up",
)


@dataclass(frozen=True, slots=True)
class ToolCallRequest:
    id: str
    name: str
    arguments: dict[str, Any]
    # True when the provider sent arguments that are not valid JSON. Such a
    # call must be refused rather than run: substituting {} would turn a
    # garbled request into a well-formed one executed on default arguments,
    # which is how "summarise lead X" quietly becomes "summarise the bound
    # lead" and nobody finds out.
    malformed: bool = False


@dataclass(frozen=True, slots=True)
class AgentTurn:
    tool_call: ToolCallRequest | None
    final_content: str | None
    input_tokens: int = 0
    output_tokens: int = 0


class AgentToolCaller(Protocol):
    def step(
        self, messages: list[dict[str, Any]], tool_defs: list[dict[str, Any]]
    ) -> AgentTurn: ...


class _OpenAIAgentCaller:
    """Single-tool-call-per-round OpenAI caller, generalized from
    app.modules.research.agent_loop._OpenAIToolCaller to the full agent tool
    registry. Parallel tool execution is deliberately kept disabled (per the
    runtime bounds this module enforces) by only ever acting on the first
    tool call a response contains, so the model-directed loop stays strictly
    sequential and every tool-call budget check happens before, not after,
    a call is executed.
    """

    def __init__(self, settings: Settings, model: str | None = None) -> None:
        self._settings = settings
        # The model is chosen by AgentModelRouter and passed in. This class
        # never reads a model from settings at call time, so a run cannot
        # silently change model between steps.
        self._model = model or settings.openai_model

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
                    "model": self._model,
                    "messages": messages,
                    "tools": tool_defs,
                    "tool_choice": "auto",
                },
            )
            response.raise_for_status()
            payload = response.json()

        message = payload["choices"][0]["message"]
        usage = payload.get("usage") or {}
        input_tokens = int(usage.get("prompt_tokens") or 0)
        output_tokens = int(usage.get("completion_tokens") or 0)

        tool_calls = message.get("tool_calls")
        if tool_calls:
            call = tool_calls[0]
            func = call.get("function", {})
            malformed = False
            try:
                parsed = json.loads(func.get("arguments") or "{}")
            except json.JSONDecodeError:
                parsed, malformed = {}, True
            if not isinstance(parsed, dict):
                parsed, malformed = {}, True
            return AgentTurn(
                tool_call=ToolCallRequest(
                    id=call.get("id", ""),
                    name=func.get("name", ""),
                    arguments=parsed,
                    malformed=malformed,
                ),
                final_content=None,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        return AgentTurn(
            tool_call=None,
            final_content=message.get("content") or "",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )


_LEAD_BOUND_RAG_TOOLS = frozenset({"match_capabilities_to_lead"})


def tools_for_run(profile: AgentProfile, *, role: str, has_lead: bool) -> list[ToolDefinition]:
    """Tools described to the model for one run.

    A workspace-level run (no lead bound) can only consult the sales knowledge
    base: every lead tool would fail, so it is never offered.
    """
    tools = tools_for(profile, role=role)
    if has_lead:
        return tools
    return [
        tool for tool in tools if tool.tool_type == RAG and tool.name not in _LEAD_BOUND_RAG_TOOLS
    ]


class _StubAgentCaller:
    """Deterministic scripted caller for agent_runtime == 'stub' (tests/demo
    mode). Mirrors research.agent_loop._StubToolCaller: exercises the full
    read -> research -> write-proposal shape of the end-to-end acceptance
    scenario without ever calling OpenAI. It stops scripting once a write
    proposal has been requested and its result comes back pending_approval
    (the runtime then pauses the run for real, exactly as it would for a
    live model).
    """

    def __init__(self, initial_index: int = 0) -> None:
        self._index = initial_index

    def step(self, messages: list[dict[str, Any]], tool_defs: list[dict[str, Any]]) -> AgentTurn:
        if self._index >= len(_STUB_SCRIPT):
            return AgentTurn(
                tool_call=None,
                final_content=json.dumps(
                    {
                        "answer": "Stub agent run finished after its scripted tool sequence.",
                        "confidence": 0.5,
                        "research_coverage": 0.5,
                    }
                ),
            )
        name = _STUB_SCRIPT[self._index]
        self._index += 1
        arguments: dict[str, Any] = {}
        if name == "create_follow_up":
            arguments = {"title": "Follow up with lead", "due_in_days": 3}
        elif name == "add_lead_note":
            arguments = {"note": "Agent identified this as a strong-fit opportunity."}
        return AgentTurn(
            tool_call=ToolCallRequest(id=f"stub-{self._index}", name=name, arguments=arguments),
            final_content=None,
        )


class _ModelUnavailableError(Exception):
    """Every routed model candidate failed for this step."""


def _args_hash(arguments: dict[str, Any]) -> str:
    canonical = json.dumps(arguments, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _persists_new_evidence(spec: Any) -> bool:
    """A successful external research call (search, crawl, refresh) writes new
    facts, so an identical read issued afterwards is NOT a duplicate: it is
    the model observing the changed state."""
    return bool(spec.tool_type == RESEARCH and spec.external_io)


def _forget_read_signatures(seen: set[tuple[str, str]]) -> None:
    for signature in [item for item in seen if (get := TOOL_REGISTRY.get(item[0])) and get.tool_type == READ]:
        seen.discard(signature)


def _bound_result(result: dict[str, Any], max_bytes: int) -> dict[str, Any]:
    serialized = json.dumps(result, default=str)
    if len(serialized.encode("utf-8")) <= max_bytes:
        return result
    return {
        "truncated": True,
        "original_size_bytes": len(serialized.encode("utf-8")),
        "preview": serialized[: max(0, max_bytes - 64)],
    }


class AgentRuntime:
    """The model-directed operational agent loop.

    Each iteration: build the provider message list from persisted
    AgentMessage rows, ask the caller for the next step, and either (a)
    execute a READ/RESEARCH/auto-write tool immediately and append its
    result, (b) create a pending AgentAction for an approval-gated write
    tool and pause the run, or (c) accept a final answer, validate it
    server-side, and complete the run. Every budget in Settings.agent_max_*
    is checked *before* the corresponding tool call executes.
    """

    def __init__(
        self,
        repository: AgentRepository | None = None,
        leads_repository: LeadsRepository | None = None,
    ) -> None:
        self.repository = repository or AgentRepository()
        self.leads_repository = leads_repository or LeadsRepository()
        self.prompts = PromptRegistry()

    # Routing and pricing are read from configuration at the moment they are
    # used, not cached on the instance: an AgentRuntime can outlive a
    # settings change, and a run costed against last hour's pricing table
    # would silently disagree with the ledger it writes into.
    @property
    def router(self) -> AgentModelRouter:
        return AgentModelRouter()

    @property
    def usage(self) -> UsageLedger:
        return UsageLedger()

    def start(
        self,
        db: Session,
        *,
        workspace_id: int,
        lead: Lead | None,
        current_user: User,
        goal: str,
        profile_key: str | None = None,
    ) -> AgentRun:
        """Create the run and drive it inline until it pauses or ends."""
        run = self.prepare_start(
            db,
            workspace_id=workspace_id,
            lead=lead,
            current_user=current_user,
            goal=goal,
            profile_key=profile_key,
        )
        if run.status != "running":
            return run
        return self._loop(db, run=run, lead=lead, current_user=current_user, settings=get_settings())

    def prepare_start(
        self,
        db: Session,
        *,
        workspace_id: int,
        lead: Lead | None,
        current_user: User,
        goal: str,
        profile_key: str | None = None,
    ) -> AgentRun:
        """Create and commit a run ready for `_loop` (status `running`), or a
        failed one when the runtime is blocked. Does not call the model."""
        settings = get_settings()
        profile = get_profile(profile_key)
        # The model is chosen here, before the run exists, by a pure
        # function of the task and the configuration. The model itself never
        # participates in this decision.
        choice = self.router.choose("tool_selection")
        run = self.repository.create_run(
            db,
            workspace_id=workspace_id,
            lead_id=lead.id if lead is not None else None,
            created_by_user_id=current_user.id,
            goal=goal,
            provider=choice.provider,
            model=choice.model,
        )
        run.profile = profile.key
        prompt = self.prompts.resolve(db, PROMPT_AGENT_SYSTEM)
        run.prompt_key = prompt.prompt_key
        run.prompt_version = prompt.version
        self.repository.save_run(db, run)
        self.repository.add_event(
            db,
            agent_run_id=run.id,
            workspace_id=workspace_id,
            run_public_id=run.public_id,
            event_type=events.AGENT_STARTED,
            payload={"goal": goal, "profile": profile.key},
        )

        if settings.agent_runtime == "blocked":
            run.status = "failed"
            run.error_code = "agent_runtime_blocked"
            run.error_message = "Agent runtime is unavailable because OPENAI_API_KEY is not configured."
            run.completed_at = datetime.now(tz=UTC)
            self.repository.save_run(db, run)
            self.repository.add_event(
                db,
                agent_run_id=run.id,
                workspace_id=workspace_id,
                run_public_id=run.public_id,
                event_type=events.AGENT_FAILED,
                payload={"error_code": run.error_code},
            )
            return run

        run.status = "running"
        self.repository.save_run(db, run)
        self.repository.add_message(
            db,
            agent_run_id=run.id,
            workspace_id=workspace_id,
            role="system",
            content=self._build_system_prompt(lead, profile, prompt.content),
        )
        self.repository.add_message(
            db, agent_run_id=run.id, workspace_id=workspace_id, role="user", content=goal
        )
        return run

    def continue_in_background(
        self,
        session_factory: sessionmaker[Session],
        *,
        workspace_id: int,
        run_id: int,
        user_id: int,
    ) -> None:
        """Drive a prepared run to its next pause or end on a fresh session.

        Scheduled as a background task after the request that prepared the
        run has returned, so the SSE stream carries each event as it is
        committed instead of replaying a run that already finished.
        """
        with session_factory() as db:
            run = self.repository.get_run_by_id(db, workspace_id=workspace_id, run_id=run_id)
            if run is None or run.status != "running":
                return
            user = db.get(User, user_id)
            if user is None or user.workspace_id != workspace_id:
                self._fail_run(
                    db, run, code="agent_user_unavailable", message="The run's user no longer exists."
                )
                return
            try:
                self._loop(
                    db,
                    run=run,
                    lead=self._run_lead(db, run),
                    current_user=user,
                    settings=get_settings(),
                )
            except Exception:
                logger.exception("agent_run.background_failed run=%s", run.public_id)
                db.rollback()
                current = self.repository.get_run_by_id(
                    db, workspace_id=workspace_id, run_id=run_id
                )
                if current is not None and current.status == "running":
                    self._fail_run(
                        db,
                        current,
                        code="agent_runtime_error",
                        message="The agent stopped unexpectedly.",
                    )

    def resume(self, db: Session, *, workspace_id: int, run_id: str, current_user: User) -> AgentRun:
        run = self.repository.get_run_by_public_id(db, workspace_id=workspace_id, run_id=run_id)
        if run is None:
            raise NotFoundError("Agent run was not found.")
        if run.status != "waiting_for_approval":
            raise ConflictError(f"Run is '{run.status}' and cannot be resumed.")
        pending = self.repository.list_pending_actions_for_run(db, run.id)
        if pending:
            raise ConflictError("Run still has pending actions awaiting approval.")
        return self._resume_from_actions(db, run=run, current_user=current_user)

    def resume_after_action(
        self, db: Session, *, workspace_id: int, run_id: int, current_user: User
    ) -> AgentRun | None:
        """Called by the action-approval API right after AgentActionGate
        finalizes a decision. If the run is waiting_for_approval and no
        other actions for it are still pending, the SAME run resumes here.
        """
        run = self.prepare_resume_after_action(db, workspace_id=workspace_id, run_id=run_id)
        if run is None:
            return None
        return self._loop(
            db,
            run=run,
            lead=self._run_lead(db, run),
            current_user=current_user,
            settings=get_settings(),
        )

    def prepare_resume_after_action(
        self, db: Session, *, workspace_id: int, run_id: int
    ) -> AgentRun | None:
        """Move a parked run back to `running` once its last pending action is
        decided, without calling the model. None when it should not resume."""
        run = self.repository.get_run_by_id(db, workspace_id=workspace_id, run_id=run_id)
        if run is None or run.status != "waiting_for_approval":
            return None
        if self.repository.list_pending_actions_for_run(db, run.id):
            return None
        return self._prepare_resume(db, run=run)

    def _run_lead(self, db: Session, run: AgentRun) -> Lead | None:
        if run.lead_id is None:
            return None
        return self.leads_repository.get_by_id_for_workspace(
            db, workspace_id=run.workspace_id, lead_id=run.lead_id
        )

    def _resume_from_actions(self, db: Session, *, run: AgentRun, current_user: User) -> AgentRun:
        run = self._prepare_resume(db, run=run)
        return self._loop(
            db,
            run=run,
            lead=self._run_lead(db, run),
            current_user=current_user,
            settings=get_settings(),
        )

    def _prepare_resume(self, db: Session, *, run: AgentRun) -> AgentRun:
        from app.modules.agents.models import AgentAction

        last_action = db.scalar(
            select(AgentAction)
            .where(AgentAction.agent_run_id == run.id)
            .order_by(AgentAction.id.desc())
            .limit(1)
        )
        if last_action is not None and last_action.tool_call_id is not None:
            tool_call = self.repository.list_tool_calls(db, run.id)
            matching = next((tc for tc in tool_call if tc.id == last_action.tool_call_id), None)
            if matching is not None:
                if last_action.status == "executed":
                    result: dict[str, Any] = last_action.result_json or {"status": "executed"}
                else:
                    result = {
                        "status": last_action.status,
                        "failure_code": last_action.failure_code,
                        "failure_message": last_action.failure_message,
                    }
                self.repository.add_message(
                    db,
                    agent_run_id=run.id,
                    workspace_id=run.workspace_id,
                    role="tool",
                    content=json.dumps(result, default=str),
                    tool_name=matching.tool_name,
                    tool_call_public_id=matching.public_id,
                )

        run.status = "running"
        self.repository.save_run(db, run)
        self.repository.add_event(
            db, agent_run_id=run.id, workspace_id=run.workspace_id, run_public_id=run.public_id, event_type=events.AGENT_RESUMED
        )
        return run

    def cancel(self, db: Session, *, workspace_id: int, run_id: str) -> AgentRun:
        run = self.repository.get_run_by_public_id(db, workspace_id=workspace_id, run_id=run_id)
        if run is None:
            raise NotFoundError("Agent run was not found.")
        if run.status not in {"queued", "running", "waiting_for_approval"}:
            raise ConflictError(f"Run is '{run.status}' and cannot be cancelled.")
        run.status = "cancelled"
        run.completed_at = datetime.now(tz=UTC)
        self.repository.save_run(db, run)
        self.repository.add_event(
            db, agent_run_id=run.id, workspace_id=workspace_id, run_public_id=run.public_id, event_type=events.AGENT_CANCELLED
        )
        return run

    def _loop(
        self,
        db: Session,
        *,
        run: AgentRun,
        lead: Lead | None,
        current_user: User,
        settings: Settings,
    ) -> AgentRun:
        prior_tool_calls = self.repository.list_tool_calls(db, run.id)
        caller: AgentToolCaller = (
            _StubAgentCaller(
                initial_index=sum(1 for tc in prior_tool_calls if tc.tool_name in _STUB_SCRIPT)
            )
            if settings.agent_runtime == "stub"
            # The run's model comes from AgentModelRouter, recorded on
            # the run at start. Reading it back here keeps a resumed run
            # on the model it began on, including after a fallback.
            else _OpenAIAgentCaller(settings, model=run.model)
        )
        executor = AgentToolExecutor(
            db, workspace_id=run.workspace_id, lead=lead, current_user=current_user
        )
        executor.run_public_id = run.public_id
        profile = get_profile(run.profile)
        # The provider only ever sees tools this profile AND this user's role
        # both allow, so an unavailable tool is never described to the model.
        tool_defs = openai_tools_for(
            tools_for_run(profile, role=current_user.role, has_lead=lead is not None)
        )
        started_at = time.monotonic()
        consecutive_failures = 0
        # Rebuilt in order so the same invalidation rule holds after a resume.
        seen_signatures: set[tuple[str, str]] = set()
        for prior in prior_tool_calls:
            if prior.status != "ok":
                continue
            seen_signatures.add((prior.tool_name, prior.arguments_hash))
            prior_spec = TOOL_REGISTRY.get(prior.tool_name)
            if prior_spec is not None and _persists_new_evidence(prior_spec):
                _forget_read_signatures(seen_signatures)

        while True:
            if self._was_stopped(db, run):
                return run
            if run.step_count >= settings.agent_max_steps:
                return self._finish_with_note(
                    db, run, "Run stopped: step budget exhausted.", budget="max_steps"
                )
            if (time.monotonic() - started_at) > settings.agent_max_runtime_seconds:
                return self._finish_with_note(
                    db, run, "Run stopped: runtime budget exhausted.", budget="max_runtime_seconds"
                )
            exhausted = self._exhausted_budget(db, run, settings)
            if exhausted is not None:
                return self._finish_with_note(
                    db,
                    run,
                    f"Run stopped: {exhausted} budget exhausted. The answer below is based "
                    "only on what had already been gathered.",
                    budget=exhausted,
                )

            messages = self._to_provider_messages(self.repository.list_messages(db, run.id))
            self.repository.add_event(
                db,
                agent_run_id=run.id,
                workspace_id=run.workspace_id,
                run_public_id=run.public_id,
                event_type=events.MODEL_STARTED,
                payload={"provider": run.provider, "model": run.model, "step": run.step_count + 1},
            )
            try:
                turn, caller = self._model_step(
                    db,
                    run=run,
                    caller=caller,
                    settings=settings,
                    messages=messages,
                    tool_defs=tool_defs,
                )
            except _ModelUnavailableError as exc:
                return self._fail_run(
                    db,
                    run,
                    code="model_provider_unavailable",
                    message=(
                        "Every routed model candidate failed for this step. "
                        f"Last provider error: {exc}"
                    ),
                )
            if self._was_stopped(db, run):
                # Cancelled or swept while the model was working: act on nothing it returned.
                return run
            run.step_count += 1
            run.model_call_count += 1
            run.input_tokens += turn.input_tokens
            run.output_tokens += turn.output_tokens
            self.repository.add_event(
                db,
                agent_run_id=run.id,
                workspace_id=run.workspace_id,
                run_public_id=run.public_id,
                event_type=events.MODEL_COMPLETED,
                payload={
                    "step": run.step_count,
                    "input_tokens": turn.input_tokens,
                    "output_tokens": turn.output_tokens,
                    # Only the *name* of the tool the model chose is exposed --
                    # never the reasoning that led it there.
                    "requested_tool": turn.tool_call.name if turn.tool_call else None,
                },
            )

            if turn.tool_call is None:
                return self._complete(db, run, lead, turn.final_content or "")

            outcome = self._handle_tool_call(
                db,
                run=run,
                executor=executor,
                settings=settings,
                call=turn.tool_call,
                seen_signatures=seen_signatures,
            )
            self.repository.save_run(db, run)

            if outcome == "paused":
                return run
            if outcome == "failure":
                consecutive_failures += 1
                if consecutive_failures >= settings.agent_max_consecutive_tool_failures:
                    return self._finish_with_note(
                        db,
                        run,
                        "Run stopped: too many consecutive tool failures.",
                        budget="max_consecutive_tool_failures",
                    )
            else:
                consecutive_failures = 0

    def _was_stopped(self, db: Session, run: AgentRun) -> bool:
        """Read the committed status, so a cancel from another request, or the
        abandoned-run sweeper, stops a run executing in the background between
        steps instead of being overwritten by it."""
        status = db.scalar(select(AgentRun.status).where(AgentRun.id == run.id))
        if status is None or status == "running":
            return False
        run.status = status
        return True

    def sweep_abandoned_runs(self, db: Session, *, workspace_id: int | None = None) -> int:
        """Fail `running` runs whose background loop is gone.

        The loop saves the run after every step, so a live run's `updated_at`
        stays fresh; one untouched for longer than the stale window lost its
        loop to a restart or crash. Each run is failed by a conditional
        UPDATE, so a run that progressed in the meantime is never clobbered,
        and an `agent_failed` event closes any stream still following it.
        The run is not retried: replaying a half-finished agent could repeat
        paid provider calls, and the user can simply ask again.
        """
        settings = get_settings()
        stale_after = max(
            settings.agent_stale_run_seconds, settings.agent_max_runtime_seconds + 300
        )
        now = datetime.now(tz=UTC)
        cutoff = now - timedelta(seconds=stale_after)
        query = select(AgentRun.id, AgentRun.workspace_id, AgentRun.public_id).where(
            AgentRun.status == "running", AgentRun.updated_at < cutoff
        )
        if workspace_id is not None:
            query = query.where(AgentRun.workspace_id == workspace_id)
        candidates = db.execute(query).all()

        swept = 0
        for run_id, run_workspace_id, run_public_id in candidates:
            result = db.execute(
                update(AgentRun)
                .where(
                    AgentRun.id == run_id,
                    AgentRun.status == "running",
                    AgentRun.updated_at < cutoff,
                )
                .values(
                    status="failed",
                    error_code="agent_run_abandoned",
                    error_message=(
                        "The run stopped before it finished, most likely because the "
                        "server restarted. Ask the question again to start a new run."
                    ),
                    completed_at=now,
                    updated_at=now,
                )
            )
            db.commit()
            if getattr(result, "rowcount", 0) != 1:
                continue
            swept += 1
            logger.warning("agent_run.abandoned_swept run=%s", run_public_id)
            self.repository.add_event(
                db,
                agent_run_id=run_id,
                workspace_id=run_workspace_id,
                run_public_id=run_public_id,
                event_type=events.AGENT_FAILED,
                payload={"error_code": "agent_run_abandoned"},
            )
        return swept

    # -- Cost, budgets and fallback ---------------------------------------

    def _exhausted_budget(
        self, db: Session, run: AgentRun, settings: Settings
    ) -> str | None:
        """The name of the first exhausted budget, or None.

        Checked before each model call rather than after, so the budget
        bounds what we spend rather than merely reporting it afterwards.
        """
        if run.model_call_count >= settings.agent_max_model_calls:
            return "max_model_calls"
        if run.input_tokens >= settings.agent_max_input_tokens:
            return "max_input_tokens"
        if run.output_tokens >= settings.agent_max_output_tokens:
            return "max_output_tokens"
        if settings.agent_max_cost_micro_usd > 0:
            totals = self.usage.totals_for_subject(db, subject_id=run.public_id)
            # An incomplete total is a lower bound: if even the priced
            # portion has passed the ceiling, we are certainly over it.
            spent = totals.cost_micro_usd or 0
            if spent >= settings.agent_max_cost_micro_usd:
                return "max_cost"
        return None

    def _model_step(
        self,
        db: Session,
        *,
        run: AgentRun,
        caller: AgentToolCaller,
        settings: Settings,
        messages: list[dict[str, Any]],
        tool_defs: list[dict[str, Any]],
    ) -> tuple[AgentTurn, AgentToolCaller]:
        """One model call, with usage recorded and bounded fallback.

        Returns the turn and the caller to use next -- after a fallback the
        run continues on the new model rather than retrying the failed one
        on every subsequent step.

        Fallback only ever moves to another candidate the router considers
        eligible for this task, which for tool selection means another
        tool-calling model. Degrading to a model that cannot call tools
        would leave the loop running and silently stop it proposing
        anything.
        """
        attempt = 0
        primary_model = run.model
        while True:
            t0 = time.monotonic()
            try:
                turn = caller.step(messages, tool_defs)
            except Exception as exc:  # noqa: BLE001 - provider errors are opaque
                latency_ms = int((time.monotonic() - t0) * 1000)
                self.usage.record(
                    db,
                    workspace_id=run.workspace_id,
                    trace_id=run.trace_id,
                    operation=OPERATION_AGENT_RUN,
                    subject_id=run.public_id,
                    provider=run.provider,
                    model=run.model,
                    latency_ms=latency_ms,
                    status="error",
                    error_message=str(exc)[:500],
                )
                if attempt >= settings.agent_max_model_fallbacks or not self.router.has_fallback(
                    "tool_selection", attempt=attempt
                ):
                    # Out of routed candidates. The run fails, visibly and
                    # with its audit trail intact, rather than the provider
                    # error escaping as an unhandled server fault.
                    raise _ModelUnavailableError(str(exc)) from exc
                attempt += 1
                choice = self.router.choose("tool_selection", attempt=attempt)
                previous_model = run.model
                run.provider = choice.provider
                run.model = choice.model
                run.fallback_used = True
                self.repository.save_run(db, run)
                self.repository.add_event(
                    db,
                    agent_run_id=run.id,
                    workspace_id=run.workspace_id,
                    run_public_id=run.public_id,
                    event_type=events.MODEL_STARTED,
                    payload={
                        "provider": choice.provider,
                        "model": choice.model,
                        "fallback_from": previous_model,
                        "reason": choice.reason,
                    },
                )
                caller = _OpenAIAgentCaller(settings, model=choice.model)
                continue

            latency_ms = int((time.monotonic() - t0) * 1000)
            self.usage.record(
                db,
                workspace_id=run.workspace_id,
                trace_id=run.trace_id,
                operation=OPERATION_AGENT_RUN,
                subject_id=run.public_id,
                provider=run.provider,
                model=run.model,
                input_tokens=turn.input_tokens,
                output_tokens=turn.output_tokens,
                latency_ms=latency_ms,
                status="ok",
                fallback_from=None if attempt == 0 else primary_model,
                metadata={"step": run.step_count + 1},
            )
            totals = self.usage.totals_for_subject(db, subject_id=run.public_id)
            run.cost_micro_usd = totals.cost_micro_usd or 0
            return turn, caller

    def _handle_tool_call(
        self,
        db: Session,
        *,
        run: AgentRun,
        executor: AgentToolExecutor,
        settings: Settings,
        call: ToolCallRequest,
        seen_signatures: set[tuple[str, str]],
    ) -> str:
        """Returns 'ok', 'failure', or 'paused'."""
        spec = TOOL_REGISTRY.get(call.name)
        args_hash = _args_hash(call.arguments)
        # Emitted before any budget check or execution, so a live client sees
        # the model's choice even when the call is then blocked or rejected.
        self.repository.add_event(
            db,
            agent_run_id=run.id,
            workspace_id=run.workspace_id,
            run_public_id=run.public_id,
            event_type=events.TOOL_REQUESTED,
            payload={
                "tool_name": call.name,
                "tool_type": spec.tool_type if spec else None,
                "risk_level": spec.risk_level if spec else None,
            },
        )

        if call.malformed:
            self._record_immediate(
                db, run=run, name=call.name, tool_type=spec.tool_type if spec else "read",
                args=call.arguments, args_hash=args_hash,
                result={
                    "error": (
                        "Tool arguments were not valid JSON. The call was not executed. "
                        "Re-send it with a well-formed JSON object."
                    )
                },
                status="error",
            )
            return "failure"

        if spec is None:
            self._record_immediate(
                db, run=run, name=call.name, tool_type="read", args=call.arguments,
                args_hash=args_hash, result={"error": f"Unknown tool '{call.name}'."}, status="error",
            )
            return "failure"

        argument_error = validate_arguments(spec, call.arguments)
        if argument_error is not None:
            self._record_immediate(
                db, run=run, name=call.name, tool_type=spec.tool_type, args=call.arguments,
                args_hash=args_hash,
                result={"error": f"Invalid arguments; the call was not executed. {argument_error}"},
                status="error",
            )
            return "failure"

        if (call.name, args_hash) in seen_signatures:
            self._record_immediate(
                db, run=run, name=call.name, tool_type=spec.tool_type, args=call.arguments,
                args_hash=args_hash,
                result={"error": "Duplicate tool call blocked: identical arguments already executed this run."},
                status="duplicate",
            )
            return "failure"

        if spec.tool_type == RAG:
            if run.rag_query_count >= settings.agent_max_rag_queries:
                result = {"error": "Knowledge-search budget exhausted for this run."}
                self._record_immediate(
                    db, run=run, name=call.name, tool_type=spec.tool_type, args=call.arguments,
                    args_hash=args_hash, result=result, status="blocked",
                )
                return "failure"

            self.repository.add_event(
                db,
                agent_run_id=run.id,
                workspace_id=run.workspace_id,
                run_public_id=run.public_id,
                event_type=events.RAG_SEARCH_STARTED,
                payload={
                    "tool_name": call.name,
                    "query": str(call.arguments.get("query") or "")[:400],
                    "collection_types": call.arguments.get("collection_types"),
                },
            )
            self._emit_tool_started(db, run, call.name, spec.tool_type)
            t0 = time.monotonic()
            result = executor.execute_rag(call.name, call.arguments)
            status = "error" if "error" in result else "ok"
            duration_ms = int((time.monotonic() - t0) * 1000)

            raw_results = result.get("results") if status == "ok" else None
            citations: list[dict[str, Any]] = (
                [item for item in raw_results if isinstance(item, dict)]
                if isinstance(raw_results, list)
                else []
            )
            self.repository.add_event(
                db,
                agent_run_id=run.id,
                workspace_id=run.workspace_id,
                run_public_id=run.public_id,
                event_type=events.RAG_SEARCH_COMPLETED,
                payload={
                    "tool_name": call.name,
                    "status": status,
                    "result_count": len(citations),
                    "candidate_count": result.get("candidate_count"),
                    "embedding_model": result.get("embedding_model"),
                    "degraded": result.get("degraded"),
                    "duration_ms": duration_ms,
                },
            )
            if citations:
                # Which documents grounded the answer, not what they said:
                # the passages themselves are untrusted content and belong in
                # the tool result, not in the event stream.
                self.repository.add_event(
                    db,
                    agent_run_id=run.id,
                    workspace_id=run.workspace_id,
                    run_public_id=run.public_id,
                    event_type=events.KNOWLEDGE_SELECTED,
                    payload={
                        "citations": [
                            {
                                "document_id": item.get("document_id"),
                                "document_title": item.get("document_title"),
                                "document_type": item.get("document_type"),
                                "section": item.get("section"),
                                "version": item.get("version"),
                                "score": item.get("score"),
                            }
                            for item in citations
                        ]
                    },
                )

            self._record_immediate(
                db, run=run, name=call.name, tool_type=spec.tool_type, args=call.arguments,
                args_hash=args_hash, result=result, status=status, duration_ms=duration_ms,
            )
            run.tool_call_count += 1
            run.rag_query_count += 1
            if status == "ok":
                seen_signatures.add((call.name, args_hash))
            return "ok" if status == "ok" else "failure"

        if spec.tool_type in (READ, RESEARCH):
            if call.name in _SEARCH_TOOLS and executor.searches_performed >= settings.agent_max_external_searches:
                result = {"error": "External-search budget exhausted for this run."}
                self._record_immediate(db, run=run, name=call.name, tool_type=spec.tool_type, args=call.arguments, args_hash=args_hash, result=result, status="blocked")
                return "failure"
            if call.name in _CRAWL_TOOLS and executor.crawls_performed >= settings.agent_max_crawls:
                result = {"error": "Crawl budget exhausted for this run."}
                self._record_immediate(db, run=run, name=call.name, tool_type=spec.tool_type, args=call.arguments, args_hash=args_hash, result=result, status="blocked")
                return "failure"
            if run.tool_call_count >= settings.agent_max_tool_calls:
                result = {"error": "Tool-call budget exhausted for this run."}
                self._record_immediate(db, run=run, name=call.name, tool_type=spec.tool_type, args=call.arguments, args_hash=args_hash, result=result, status="blocked")
                return "failure"

            self._emit_tool_started(db, run, call.name, spec.tool_type)
            t0 = time.monotonic()
            result = executor.execute_read_or_research(call.name, call.arguments)
            status = "error" if "error" in result else "ok"
            self._record_immediate(
                db, run=run, name=call.name, tool_type=spec.tool_type, args=call.arguments,
                args_hash=args_hash, result=result, status=status, duration_ms=int((time.monotonic() - t0) * 1000),
            )
            run.tool_call_count += 1
            if call.name in _SEARCH_TOOLS:
                run.external_search_count += 1
            if call.name in _CRAWL_TOOLS:
                run.crawl_count += 1
            if call.name in _EXTERNAL_PROVIDERS:
                # External providers bill per call, not per token. They go in
                # the same ledger so one query answers "what did this run
                # cost", rather than model spend and provider spend living in
                # separate places that have to be added up by hand.
                provider_name, operation = _EXTERNAL_PROVIDERS[call.name]
                self.usage.record(
                    db,
                    workspace_id=run.workspace_id,
                    trace_id=run.trace_id,
                    operation=operation,
                    subject_id=run.public_id,
                    provider=provider_name,
                    model=call.name,
                    units=1,
                    status=status,
                    metadata={"tool": call.name},
                )
            if status == "ok":
                seen_signatures.add((call.name, args_hash))
                if _persists_new_evidence(spec):
                    _forget_read_signatures(seen_signatures)
            return "ok" if status == "ok" else "failure"

        if spec.tool_type == WRITE_PROPOSAL and not spec.requires_approval:
            if run.tool_call_count >= settings.agent_max_tool_calls:
                result = {"error": "Tool-call budget exhausted for this run."}
                self._record_immediate(db, run=run, name=call.name, tool_type=spec.tool_type, args=call.arguments, args_hash=args_hash, result=result, status="blocked")
                return "failure"
            self._emit_tool_started(db, run, call.name, spec.tool_type)
            t0 = time.monotonic()
            result = executor.execute_auto_write(call.name, call.arguments)
            status = "error" if "error" in result else "ok"
            self._record_immediate(
                db, run=run, name=call.name, tool_type=spec.tool_type, args=call.arguments,
                args_hash=args_hash, result=result, status=status, duration_ms=int((time.monotonic() - t0) * 1000),
            )
            run.tool_call_count += 1
            run.write_proposal_count += 1
            if status == "ok":
                seen_signatures.add((call.name, args_hash))
            return "ok" if status == "ok" else "failure"

        # WRITE_PROPOSAL requiring approval, or ACTION: propose, never mutate.
        if run.write_proposal_count >= settings.agent_max_write_proposals:
            result = {"error": "Write-proposal budget exhausted for this run."}
            self._record_immediate(db, run=run, name=call.name, tool_type=spec.tool_type, args=call.arguments, args_hash=args_hash, result=result, status="blocked")
            return "failure"
        if run.lead_id is None:
            result = {"error": "This run has no lead bound to it; cannot propose a mutation."}
            self._record_immediate(db, run=run, name=call.name, tool_type=spec.tool_type, args=call.arguments, args_hash=args_hash, result=result, status="error")
            return "failure"

        try:
            preview, payload, resource_type, resource_id = executor.build_preview(
                call.name, call.arguments
            )
        except Exception as exc:  # noqa: BLE001
            result = {"error": str(exc)}
            self._record_immediate(db, run=run, name=call.name, tool_type=spec.tool_type, args=call.arguments, args_hash=args_hash, result=result, status="error")
            return "failure"

        tool_call_row = self.repository.add_tool_call(
            db, agent_run_id=run.id, workspace_id=run.workspace_id, tool_name=call.name,
            tool_type=spec.tool_type, arguments=call.arguments, arguments_hash=args_hash,
            status="pending_approval",
        )
        payload_hash = hash_payload(payload)
        action = self.repository.create_action(
            db,
            workspace_id=run.workspace_id,
            agent_run_id=run.id,
            tool_call_id=tool_call_row.id,
            tool_name=call.name,
            resource_type=resource_type,
            resource_id=resource_id,
            payload=payload,
            payload_hash=payload_hash,
            preview=preview,
            risk_level=spec.risk_level,
            expires_at=datetime.now(tz=UTC) + timedelta(seconds=settings.agent_action_expiry_seconds),
            idempotency_key=f"{run.public_id}:{tool_call_row.public_id}",
            trace_id=run.trace_id,
        )
        self.repository.complete_tool_call(
            db, tool_call_row, status="pending_approval",
            result={"status": "pending_approval", "action_id": action.public_id}, duration_ms=0,
        )
        # Record the assistant's tool-call request (arguments JSON as content)
        # so the conversation can be reconstructed once resumed -- the
        # matching 'tool' response is deferred until the action is decided.
        self.repository.add_message(
            db, agent_run_id=run.id, workspace_id=run.workspace_id, role="assistant",
            content=json.dumps(call.arguments), tool_name=call.name,
            tool_call_public_id=tool_call_row.public_id,
        )
        run.write_proposal_count += 1
        run.tool_call_count += 1
        run.status = "waiting_for_approval"
        self.repository.save_run(db, run)
        self.repository.add_event(
            db, agent_run_id=run.id, workspace_id=run.workspace_id, run_public_id=run.public_id, event_type=events.ACTION_PROPOSED,
            payload={"action_id": action.public_id, "tool_name": call.name},
        )
        self.repository.add_event(
            db, agent_run_id=run.id, workspace_id=run.workspace_id, run_public_id=run.public_id, event_type=events.WAITING_FOR_APPROVAL,
            payload={"action_id": action.public_id},
        )
        return "paused"

    def _emit_tool_started(
        self, db: Session, run: AgentRun, tool_name: str, tool_type: str
    ) -> None:
        self.repository.add_event(
            db,
            agent_run_id=run.id,
            workspace_id=run.workspace_id,
            run_public_id=run.public_id,
            event_type=events.TOOL_STARTED,
            payload={"tool_name": tool_name, "tool_type": tool_type},
        )

    def _record_immediate(
        self,
        db: Session,
        *,
        run: AgentRun,
        name: str,
        tool_type: str,
        args: dict[str, Any],
        args_hash: str,
        result: dict[str, Any],
        status: str,
        duration_ms: int = 0,
    ) -> None:
        settings = get_settings()
        bounded = _bound_result(result, settings.agent_max_tool_result_bytes)
        tool_call_row = self.repository.add_tool_call(
            db, agent_run_id=run.id, workspace_id=run.workspace_id, tool_name=name,
            tool_type=tool_type, arguments=args, arguments_hash=args_hash, status=status,
        )
        self.repository.complete_tool_call(
            db, tool_call_row, status=status, result=bounded, duration_ms=duration_ms
        )
        self.repository.add_event(
            db, agent_run_id=run.id, workspace_id=run.workspace_id,
            run_public_id=run.public_id,
            event_type=events.TOOL_COMPLETED if status == "ok" else events.TOOL_FAILED,
            payload={"tool_name": name, "status": status, "duration_ms": duration_ms},
        )
        self.repository.add_message(
            db, agent_run_id=run.id, workspace_id=run.workspace_id, role="assistant",
            content=json.dumps(args), tool_name=name, tool_call_public_id=tool_call_row.public_id,
        )
        self.repository.add_message(
            db, agent_run_id=run.id, workspace_id=run.workspace_id, role="tool",
            content=self._tool_message_content(db, run, name, tool_type, bounded),
            tool_name=name, tool_call_public_id=tool_call_row.public_id,
        )

    def _tool_message_content(
        self,
        db: Session,
        run: AgentRun,
        tool_name: str,
        tool_type: str,
        result: dict[str, Any],
    ) -> str:
        """Render one tool result for the model.

        RESEARCH and RAG results are third-party content, so they go back
        inside an untrusted envelope rather than as bare JSON. READ results
        come from this system's own deterministic tables and are passed
        through unwrapped -- but any injection-looking string found in
        either is recorded as an event, so an attempt is visible in the
        audit trail even though nothing is ever blocked on that basis.
        """
        serialized = json.dumps(result, default=str)
        markers = detect_injection_markers(serialized)
        if markers:
            self.repository.add_event(
                db,
                agent_run_id=run.id,
                workspace_id=run.workspace_id,
                run_public_id=run.public_id,
                event_type=events.TOOL_COMPLETED,
                payload={
                    "tool_name": tool_name,
                    "status": "injection_markers_detected",
                    "marker_count": len(markers),
                },
            )
        if tool_type in {RESEARCH, RAG}:
            kind = "KNOWLEDGE_CONTEXT" if tool_type == RAG else "WEB_CONTENT"
            return wrap_untrusted(serialized, kind=kind, source=tool_name)
        return serialized

    def _fail_run(self, db: Session, run: AgentRun, *, code: str, message: str) -> AgentRun:
        """Record a run that could not continue.

        No final answer is written. A failed run must not carry a
        zero-confidence conclusion that could be mistaken for one the model
        actually reached.
        """
        run.status = "failed"
        run.error_code = code
        run.error_message = message[:2000]
        run.completed_at = datetime.now(tz=UTC)
        self.repository.save_run(db, run)
        self.repository.add_event(
            db,
            agent_run_id=run.id,
            workspace_id=run.workspace_id,
            run_public_id=run.public_id,
            event_type=events.AGENT_FAILED,
            payload={"error_code": code},
        )
        return run

    def _finish_with_note(
        self, db: Session, run: AgentRun, note: str, *, budget: str | None = None
    ) -> AgentRun:
        """Stop the run early but *honestly*: the run completes with a
        zero-confidence structured answer stating why it stopped, rather
        than fabricating a conclusion it never reached.
        """
        if budget is not None:
            run.stop_reason = budget
            self.repository.add_event(
                db,
                agent_run_id=run.id,
                workspace_id=run.workspace_id,
                run_public_id=run.public_id,
                event_type=events.BUDGET_EXHAUSTED,
                payload={"budget": budget},
            )
        run.status = "completed"
        run.final_answer_json = AgentFinalAnswer(
            answer=note, confidence=0.0, research_coverage=0.0
        ).model_dump(mode="json")
        run.completed_at = datetime.now(tz=UTC)
        self.repository.save_run(db, run)
        self.repository.add_event(
            db, agent_run_id=run.id, workspace_id=run.workspace_id, run_public_id=run.public_id, event_type=events.AGENT_COMPLETED,
            payload={"note": note},
        )
        return run

    def _complete(self, db: Session, run: AgentRun, lead: Lead | None, raw_content: str) -> AgentRun:
        final = self._ground_final_answer(
            db, run, lead, self._validate_final_answer(raw_content, lead)
        )
        run.final_answer_json = final.model_dump(mode="json")
        run.status = "completed"
        run.completed_at = datetime.now(tz=UTC)
        self.repository.save_run(db, run)
        self.repository.add_message(
            db, agent_run_id=run.id, workspace_id=run.workspace_id, role="assistant",
            content=raw_content,
        )
        self.repository.add_event(
            db, agent_run_id=run.id, workspace_id=run.workspace_id, run_public_id=run.public_id, event_type=events.AGENT_COMPLETED,
            payload={"confidence": final.confidence},
        )
        return run

    def _ground_final_answer(
        self, db: Session, run: AgentRun, lead: Lead | None, final: AgentFinalAnswer
    ) -> AgentFinalAnswer:
        """Replaces every field the backend owns with the backend's value.

        The model writes the prose; coverage, which knowledge was cited and
        which actions ran are facts this run recorded, so the model's claims
        about them are discarded rather than trusted.
        """
        from sqlalchemy import select

        from app.modules.agents.models import AgentAction
        from app.modules.leads.service import LeadsService

        selected_ids = {
            str(citation.get("document_id"))
            for event in self.repository.list_events(db, run.id)
            if event.event_type == events.KNOWLEDGE_SELECTED
            for citation in (event.payload_json or {}).get("citations", [])
            if isinstance(citation, dict) and citation.get("document_id") is not None
        }
        actions = db.scalars(
            select(AgentAction).where(AgentAction.agent_run_id == run.id).order_by(AgentAction.id)
        ).all()
        coverage = 0.0
        if lead is not None:
            try:
                graph = LeadsService().evidence_graph(db, run.workspace_id, lead.public_id)
                coverage = float(graph.research_coverage)
            except Exception:  # noqa: BLE001 - grounding must never fail completion
                logger.warning("Could not compute research coverage for run %s", run.public_id)
        from app.modules.agents.grounding import ground_evidence_refs

        evidence_refs, dropped_refs = ground_evidence_refs(
            db,
            agent_run_id=run.id,
            workspace_id=run.workspace_id,
            lead_id=run.lead_id,
            requested=final.evidence_refs,
        )
        if dropped_refs:
            # Audit only: the refs themselves (ids, never content) and a count.
            self.repository.add_event(
                db, agent_run_id=run.id, workspace_id=run.workspace_id,
                run_public_id=run.public_id, event_type=events.FINAL_EVIDENCE_REF_DROPPED,
                payload={"dropped_count": len(dropped_refs), "dropped": [r[:64] for r in dropped_refs[:20]]},
            )
        return final.model_copy(
            update={
                "lead_id": lead.public_id if lead is not None else None,
                "evidence_refs": evidence_refs,
                "research_coverage": max(0.0, min(1.0, coverage)),
                "knowledge_refs": [ref for ref in final.knowledge_refs if ref in selected_ids],
                "completed_actions": [
                    f"{action.tool_name}:{action.public_id}"
                    for action in actions
                    if action.status == "executed"
                ],
                "pending_actions": [
                    f"{action.tool_name}:{action.public_id}"
                    for action in actions
                    if action.status == "pending"
                ],
            }
        )

    def _validate_final_answer(self, raw_content: str, lead: Lead | None) -> AgentFinalAnswer:
        try:
            data = json.loads(raw_content)
            if not isinstance(data, dict):
                raise ValueError("Final answer JSON must be an object.")
            data.setdefault("lead_id", lead.public_id if lead is not None else None)
            return AgentFinalAnswer.model_validate(data)
        except (json.JSONDecodeError, ValidationError, ValueError):
            return AgentFinalAnswer(
                answer=raw_content or "The agent finished without a structured final answer.",
                lead_id=lead.public_id if lead is not None else None,
                confidence=0.0,
                research_coverage=0.0,
            )

    def _build_system_prompt(
        self, lead: Lead | None, profile: AgentProfile, base: str
    ) -> str:
        lead_line = (
            f"Bound lead: {lead.company_name} (id={lead.public_id}, city={lead.city or 'unknown'})."
            if lead is not None
            else "No lead is bound to this run."
        )
        # `base` is the versioned operating prompt from the Prompt Registry.
        # The run records which version it ran under, so activating a new
        # version never changes how an already-finished run is explained.
        return (
            f"{SECURITY_PREAMBLE}\n\n"
            f"{base}\n\n"
            f"{profile.prompt_guidance}\n\n"
            "You are the ProspectIQ operational agent. Use the available tools to gather "
            "information and, when appropriate, propose lead-scoped changes. Any tool that "
            "mutates data will pause this run for human approval before anything is written. "
            "You never supply a workspace id, lead id, or user id to any tool -- they are "
            "always bound to this run server-side. When you are done, reply with a plain JSON "
            "object (no markdown fences) matching: {\"answer\": str, \"confidence\": float 0-1, "
            "\"research_coverage\": float 0-1, \"evidence_refs\": [evidence_ref/change_id/run_id values from tool results], "
            "\"knowledge_refs\": [document_id from search_sales_knowledge], \"opportunities\": [str], "
            "\"risks\": [str], \"recommended_actions\": [str], \"completed_actions\": [str], "
            "\"pending_actions\": [str], \"follow_up_questions\": [str]}. "
            f"{lead_line}"
        )

    def _to_provider_messages(self, messages: list[Any]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for message in messages:
            if message.role in {"system", "user"}:
                out.append({"role": message.role, "content": message.content})
            elif message.role == "assistant" and message.tool_call_public_id is not None:
                out.append(
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": message.tool_call_public_id,
                                "type": "function",
                                "function": {
                                    "name": message.tool_name,
                                    "arguments": message.content or "{}",
                                },
                            }
                        ],
                    }
                )
            elif message.role == "tool":
                out.append(
                    {
                        "role": "tool",
                        "tool_call_id": message.tool_call_public_id,
                        "content": message.content or "{}",
                    }
                )
            elif message.role == "assistant":
                out.append({"role": "assistant", "content": message.content})
        return out


__all__ = ["AgentRuntime", "AgentTurn", "ToolCallRequest"]
