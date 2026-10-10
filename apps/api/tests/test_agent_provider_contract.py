from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from agent_api_helpers import start_agent_run
from test_workspace_e2e import _build_session_factory, _login, _override_client, _seed_workspace

import app.modules.agents.runtime as runtime_module
from app.core.config import clear_settings_cache

_REAL_HTTPX_CLIENT = httpx.Client


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class _ProviderDouble:
    """A stand-in for the OpenAI chat-completions endpoint.

    The point of this double is that the *provider* decides the sequence,
    one call at a time, by looking at the tool results it has been given so
    far -- exactly as a real model does. The runtime is never told what is
    coming next, so if the runtime were secretly scripting a business
    sequence, these assertions would not hold.
    """

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.offered_tool_names: list[list[str]] = []

    # httpx.Client context-manager protocol. Patching httpx.Client replaces
    # it process-wide, so anything that is *not* the agent's chat-completions
    # client (health probes, provider connectivity checks) must still get a
    # real client -- the double only claims calls that carry the agent
    # caller's Authorization header.
    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        headers = kwargs.get("headers") or {}
        if "Authorization" in headers:
            return self
        return _REAL_HTTPX_CLIENT(*args, **kwargs)

    def __enter__(self) -> _ProviderDouble:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def post(self, url: str, json: dict[str, Any] | None = None, **kwargs: Any) -> _FakeResponse:
        body = json or {}
        self.requests.append(body)
        messages: list[dict[str, Any]] = body.get("messages", [])
        self.offered_tool_names.append(
            [tool["function"]["name"] for tool in body.get("tools", [])]
        )
        return _FakeResponse(self._decide(messages))

    def _tool_results(self, messages: list[dict[str, Any]]) -> dict[str, str]:
        """Map tool name -> result content, as the provider actually saw it."""
        results: dict[str, str] = {}
        pending_name: str | None = None
        for message in messages:
            if message.get("role") == "assistant" and message.get("tool_calls"):
                pending_name = message["tool_calls"][0]["function"]["name"]
            elif message.get("role") == "tool" and pending_name:
                results[pending_name] = message.get("content") or ""
                pending_name = None
        return results

    def _decide(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        seen = self._tool_results(messages)

        if "get_lead_context" not in seen:
            return self._tool_call("get_lead_context", {})

        # Branch on the *content* of the first result: this is the
        # behaviour that proves results feed the next decision.
        context = seen["get_lead_context"]
        if "website_url" in context and "get_evidence_graph" not in seen:
            return self._tool_call("get_evidence_graph", {})

        if "get_score_breakdown" not in seen:
            return self._tool_call("get_score_breakdown", {})

        if "add_lead_note" not in seen:
            return self._tool_call(
                "add_lead_note", {"note": "Grounded opportunity summary for this lead."}
            )

        return self._final(
            {
                "answer": "Analysis complete.",
                "confidence": 0.6,
                "research_coverage": 0.5,
                "completed_actions": ["add_lead_note"],
            }
        )

    @staticmethod
    def _tool_call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": f"call_{name}",
                                "type": "function",
                                "function": {
                                    "name": name,
                                    "arguments": json.dumps(arguments),
                                },
                            }
                        ],
                    }
                }
            ],
            "usage": {"prompt_tokens": 120, "completion_tokens": 20},
        }

    @staticmethod
    def _final(answer: dict[str, Any]) -> dict[str, Any]:
        return {
            "choices": [{"message": {"role": "assistant", "content": json.dumps(answer)}}],
            "usage": {"prompt_tokens": 150, "completion_tokens": 40},
        }


@pytest.fixture()
def provider_double(monkeypatch: pytest.MonkeyPatch) -> _ProviderDouble:
    double = _ProviderDouble()
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-a-real-key")
    monkeypatch.setenv("AGENT_RUNTIME_MODE", "openai")
    monkeypatch.setenv("TAVILY_RUNTIME_MODE", "demo")
    monkeypatch.setenv("APIFY_RUNTIME_MODE", "demo")
    clear_settings_cache()
    monkeypatch.setattr(runtime_module.httpx, "Client", double)
    return double


def test_runtime_follows_the_providers_dynamic_tool_choices(
    provider_double: _ProviderDouble, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real provider adapter contract: the model picks each tool one
    call at a time, and every pick lands as a persisted AgentToolCall in the
    order the provider chose -- not in any order the runtime knows."""
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        headers = {"Authorization": f"Bearer {token}"}
        run = start_agent_run(client,
            "/api/v1/agent/runs",
            json={"goal": "Analyse and summarise.", "lead_id": seed.lead_public_id},
            headers=headers,
        ).json()

        # The provider asked for a mutation, so the run must be parked.
        assert run["status"] == "waiting_for_approval"

        events = client.get(f"/api/v1/agent/runs/{run['run_id']}/events", headers=headers).json()
        requested = [
            event["payload"]["tool_name"]
            for event in events["events"]
            if event["event_type"] == "tool_requested"
        ]

    assert requested == [
        "get_lead_context",
        "get_evidence_graph",
        "get_score_breakdown",
        "add_lead_note",
    ]
    # More than one provider round-trip happened: the loop really is
    # call -> result -> next call, not one planned batch.
    assert len(provider_double.requests) == 4


def test_provider_sees_growing_message_history_and_the_registry_tool_schemas(
    provider_double: _ProviderDouble,
) -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        headers = {"Authorization": f"Bearer {token}"}
        start_agent_run(client,
            "/api/v1/agent/runs",
            json={"goal": "Analyse and summarise.", "lead_id": seed.lead_public_id},
            headers=headers,
        )

    lengths = [len(request["messages"]) for request in provider_double.requests]
    assert lengths == sorted(lengths) and lengths[-1] > lengths[0]

    offered = provider_double.offered_tool_names[0]
    assert "get_lead_context" in offered
    assert "add_lead_note" in offered
    # No tool schema may expose tenancy or identity parameters to the model.
    for request in provider_double.requests:
        for tool in request["tools"]:
            properties = tool["function"]["parameters"].get("properties", {})
            assert not {"workspace_id", "lead_id", "user_id", "actor_id", "url"} & set(properties)


def test_unknown_tool_from_provider_is_rejected_not_executed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A provider that hallucinates a tool name gets an error result back and
    the run keeps going -- it never reaches an executor."""

    class _HallucinatingProvider(_ProviderDouble):
        def _decide(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
            seen = self._tool_results(messages)
            if "run_sql" not in seen:
                return self._tool_call("run_sql", {"query": "SELECT * FROM leads"})
            return self._final(
                {"answer": "Could not use that tool.", "confidence": 0.1, "research_coverage": 0.0}
            )

    double = _HallucinatingProvider()
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-a-real-key")
    monkeypatch.setenv("AGENT_RUNTIME_MODE", "openai")
    clear_settings_cache()
    monkeypatch.setattr(runtime_module.httpx, "Client", double)

    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    with _override_client(session_factory) as client:
        token = _login(client, seed)
        headers = {"Authorization": f"Bearer {token}"}
        run = start_agent_run(client,
            "/api/v1/agent/runs",
            json={"goal": "Try something unsupported.", "lead_id": seed.lead_public_id},
            headers=headers,
        ).json()
        assert run["status"] == "completed"
        events = client.get(f"/api/v1/agent/runs/{run['run_id']}/events", headers=headers).json()
        failed = [
            event for event in events["events"] if event["event_type"] == "tool_failed"
        ]
        assert failed, "an unknown tool must be recorded as a failed call"
        assert failed[0]["payload"]["tool_name"] == "run_sql"
