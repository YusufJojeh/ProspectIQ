from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Literal

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

# --- Deterministic model routing -----------------------------------------
#
# The model does not choose its own model. That is not a stylistic
# preference: a model that can select a more expensive model is a model that
# can spend money, and a model that can select a weaker one can quietly
# degrade tool-calling reliability in the middle of a run. Selection is a
# pure function of the task and the configuration, computable before the
# first token is generated and reproducible afterwards from the AgentRun
# row alone.
#
# Fallback is the one place routing changes mid-run, and it is deliberately
# narrow: a fallback candidate must itself be declared tool-call capable
# when the task requires tool calling, because silently dropping to a model
# that cannot call tools turns an agent into a chatbot without saying so.

AgentTask = Literal[
    "tool_selection",
    "research_synthesis",
    "outreach_writing",
    "extraction",
    "summarization",
]

TASKS: tuple[AgentTask, ...] = (
    "tool_selection",
    "research_synthesis",
    "outreach_writing",
    "extraction",
    "summarization",
)

#: Tasks that cannot run on a model without native tool calling.
_TOOL_CALLING_TASKS: frozenset[str] = frozenset({"tool_selection"})


@dataclass(frozen=True, slots=True)
class ModelChoice:
    provider: str
    model: str
    #: Why this model, in terms a human reading an audit trail can check:
    #: the task, and whether this was the primary route or a fallback.
    task: str
    reason: str
    supports_tools: bool
    fallback_from: str | None = None


@dataclass(frozen=True, slots=True)
class ModelCandidate:
    provider: str
    model: str
    supports_tools: bool = True


def _parse_candidates(raw: object) -> tuple[ModelCandidate, ...]:
    if not isinstance(raw, list):
        return ()
    out: list[ModelCandidate] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        provider = str(item.get("provider") or "").strip()
        model = str(item.get("model") or "").strip()
        if not provider or not model:
            continue
        out.append(
            ModelCandidate(
                provider=provider,
                model=model,
                supports_tools=bool(item.get("supports_tools", True)),
            )
        )
    return tuple(out)


def parse_routing(raw_json: str) -> dict[str, tuple[ModelCandidate, ...]]:
    """Parse {task: [candidate, ...]} routing configuration.

    An unreadable configuration yields no routes rather than a guess: the
    router then falls back to the platform default model, which is at least
    a known quantity.
    """
    if not raw_json.strip():
        return {}
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError:
        logger.warning("agent_model_routing_json_invalid")
        return {}
    if not isinstance(payload, dict):
        logger.warning("agent_model_routing_json_not_an_object")
        return {}
    return {
        str(task): _parse_candidates(candidates)
        for task, candidates in payload.items()
        if str(task) in TASKS
    }


@dataclass
class AgentModelRouter:
    """Chooses provider and model for a task, deterministically."""

    settings: Settings = field(default_factory=get_settings)

    def __post_init__(self) -> None:
        self._routes = parse_routing(self.settings.agent_model_routing_json)

    def _default(self) -> ModelCandidate:
        return ModelCandidate(
            provider="openai", model=self.settings.openai_model, supports_tools=True
        )

    def candidates(self, task: str) -> tuple[ModelCandidate, ...]:
        configured = self._routes.get(task, ())
        return configured or (self._default(),)

    def choose(self, task: str, *, attempt: int = 0) -> ModelChoice:
        """The model for `task` on attempt `attempt` (0 = primary route).

        Raises IndexError only if a caller asks past the configured
        fallbacks; callers use `has_fallback` to decide whether to retry, so
        exhaustion is a decision made by the caller, not a silent downgrade
        here.
        """
        options = self._eligible(task)
        if attempt >= len(options):
            raise IndexError(f"No model candidate at attempt {attempt} for task '{task}'.")
        chosen = options[attempt]
        primary = options[0]
        return ModelChoice(
            provider=chosen.provider,
            model=chosen.model,
            task=task,
            reason=("primary route" if attempt == 0 else f"fallback #{attempt}"),
            supports_tools=chosen.supports_tools,
            fallback_from=None if attempt == 0 else primary.model,
        )

    def has_fallback(self, task: str, *, attempt: int) -> bool:
        return attempt + 1 < len(self._eligible(task))

    def _eligible(self, task: str) -> tuple[ModelCandidate, ...]:
        options = self.candidates(task)
        if task not in _TOOL_CALLING_TASKS:
            return options
        # A tool-selection task must never fall back to a model that cannot
        # call tools: the loop would keep running and stop proposing
        # actions, which looks like the agent deciding nothing needs doing.
        eligible = tuple(option for option in options if option.supports_tools)
        return eligible or (self._default(),)


__all__ = [
    "TASKS",
    "AgentModelRouter",
    "AgentTask",
    "ModelCandidate",
    "ModelChoice",
    "parse_routing",
]
