"""Shared doubles for provider-driven agent tests.

`TranscriptProvider` is a model double with NO script: every call it
parses the transcript the runtime sent (tool calls made, tool results
returned) and hands that state to a `decide` function, which chooses the
next step from what the tools actually returned. Tests using it prove the
runtime follows model choices; they cannot pass by replaying a sequence.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.modules.provider_serpapi.models import ProviderFetch, ProviderNormalizedFact
from app.modules.research.models import ResearchChangeEvent, ResearchRun
from app.shared.enums.jobs import ProviderFetchStatus

_REAL_HTTPX_CLIENT = httpx.Client


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


def parse_tool_content(value: str) -> Any:
    """Tool results reach the model fenced as untrusted context; a model
    reads the JSON inside the fence, so the double does the same."""
    start, end = value.find("{"), value.rfind("}")
    if start == -1:
        return {}
    try:
        return json.loads(value[start : end + 1])
    except ValueError:
        return {}


@dataclass
class Transcript:
    called: list[str] = field(default_factory=list)
    #: Latest result per tool name.
    results: dict[str, Any] = field(default_factory=dict)
    #: Every (tool, result) in order, for tools called more than once.
    history: list[tuple[str, Any]] = field(default_factory=list)
    user_goal: str = ""

    def count(self, tool: str) -> int:
        return self.called.count(tool)

    def refs(self, key: str = "evidence_ref") -> list[str]:
        found: list[str] = []

        def walk(value: Any) -> None:
            if isinstance(value, dict):
                for item_key, item in value.items():
                    if item_key == key and isinstance(item, str):
                        found.append(item)
                    else:
                        walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)

        for _, result in self.history:
            walk(result)
        return list(dict.fromkeys(found))


Decision = tuple[str, dict[str, Any]]


class TranscriptProvider:
    def __init__(self, decide: Callable[[Transcript], Decision]) -> None:
        self._decide = decide
        self.decisions: list[str] = []

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        if "Authorization" in (kwargs.get("headers") or {}):
            return self
        return _REAL_HTTPX_CLIENT(*args, **kwargs)

    def __enter__(self) -> TranscriptProvider:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def post(self, url: str, json: dict[str, Any] | None = None, **kwargs: Any) -> FakeResponse:
        state = _read(json or {})
        name, arguments = self._decide(state)
        self.decisions.append(name)
        usage = {"prompt_tokens": 150, "completion_tokens": 40}
        if name == "final":
            message: dict[str, Any] = {"role": "assistant", "content": _dumps(arguments)}
        else:
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": f"call_{len(state.called) + 1}",
                        "type": "function",
                        "function": {"name": name, "arguments": _dumps(arguments)},
                    }
                ],
            }
        return FakeResponse({"choices": [{"message": message}], "usage": usage})


def _read(body: dict[str, Any]) -> Transcript:
    state = Transcript()
    names_by_id: dict[str, str] = {}
    for message in body.get("messages", []):
        role = message.get("role")
        if role == "user" and not state.user_goal:
            state.user_goal = str(message.get("content") or "")
        if role == "assistant":
            for call in message.get("tool_calls") or []:
                names_by_id[call["id"]] = call["function"]["name"]
                state.called.append(call["function"]["name"])
        if role == "tool":
            name = names_by_id.get(message.get("tool_call_id", ""), "")
            result = parse_tool_content(str(message.get("content") or ""))
            state.results[name] = result
            state.history.append((name, result))
    return state


def _dumps(value: dict[str, Any]) -> str:
    return json.dumps(value)


# --- seeding --------------------------------------------------------------


def add_fact(
    db: Session,
    *,
    workspace_id: int,
    lead_id: int,
    age_days: int = 0,
    **overrides: Any,
) -> ProviderNormalizedFact:
    fetch = ProviderFetch(
        workspace_id=workspace_id,
        provider="tavily",
        engine="web_search",
        mode="research",
        request_fingerprint=f"fp-{datetime.now(tz=UTC).timestamp()}-{lead_id}-{age_days}",
        request_params_json={},
        status=ProviderFetchStatus.OK.value,
    )
    db.add(fetch)
    db.flush()
    values: dict[str, Any] = {
        "workspace_id": workspace_id,
        "lead_id": lead_id,
        "provider_fetch_id": fetch.id,
        "source_type": "apify_company_website_crawler",
        "company_name": "Acme Dental",
        "website_url": "https://acme-dental.example",
        "confidence": 0.8,
        "freshness_score": 1.0,
        "created_at": datetime.now(tz=UTC) - timedelta(days=age_days),
    }
    values.update(overrides)
    fact = ProviderNormalizedFact(**values)
    db.add(fact)
    db.commit()
    db.refresh(fact)
    return fact


def add_research_run_with_change(
    db: Session,
    *,
    workspace_id: int,
    lead_id: int,
    claim_type: str,
    before: str,
    after: str,
    significance: float = 0.6,
    minutes_ago: int = 0,
) -> tuple[ResearchRun, ResearchChangeEvent]:
    run = ResearchRun(
        workspace_id=workspace_id,
        lead_id=lead_id,
        depth="standard",
        mode="planned",
        status="ok",
        providers_used_json=["tavily"],
        evidence_confidence=0.8,
        research_coverage=0.7,
        created_at=datetime.now(tz=UTC) - timedelta(minutes=minutes_ago),
    )
    db.add(run)
    db.flush()
    change = ResearchChangeEvent(
        workspace_id=workspace_id,
        lead_id=lead_id,
        current_research_run_id=run.id,
        claim_type=claim_type,
        previous_value=before,
        new_value=after,
        event_type="digital_capability_changed",
        direction="improved",
        significance=significance,
        explanation=f"{claim_type} changed from {before} to {after}.",
    )
    db.add(change)
    db.commit()
    db.refresh(run)
    db.refresh(change)
    return run, change
