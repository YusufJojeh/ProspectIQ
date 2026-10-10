from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from test_workspace_e2e import _build_session_factory, _login, _override_client, _seed_workspace

import app.modules.agents.runtime as runtime_module
from app.core.config import clear_settings_cache
from app.modules.agents.models import AgentRun
from app.modules.ai_runtime.models import ProviderUsage

_REAL_HTTPX_CLIENT = httpx.Client

_READ_ROTATION: tuple[str, ...] = (
    "get_lead_context",
    "get_score_breakdown",
    "get_evidence_graph",
    "get_icp_profile",
    "get_research_history",
    "get_delta_changes",
    "get_outreach_history",
    "get_lead_notes",
    "get_lead_activity",
    "get_contact_channels",
    "get_service_catalog",
    "get_previous_research",
    "get_existing_evidence",
)

_PRICING = json.dumps(
    [
        {
            "provider": "openai",
            "model": "gpt-4.1-mini",
            "input_rate_micro_per_1k": 400,
            "output_rate_micro_per_1k": 1600,
        }
    ]
)


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class _LoopingProvider:
    """A provider that always asks for another read tool and never finishes.

    Useful precisely because it never stops on its own: whatever stops the
    run is the budget, not the model deciding it is done.
    """

    def __init__(self, *, fail_first_n: int = 0) -> None:
        self.calls = 0
        self.failures = 0
        self._fail_first_n = fail_first_n
        self.models_used: list[str] = []

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        headers = kwargs.get("headers") or {}
        if "Authorization" in headers:
            return self
        return _REAL_HTTPX_CLIENT(*args, **kwargs)

    def __enter__(self) -> _LoopingProvider:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def post(self, url: str, json: dict[str, Any] | None = None, **kwargs: Any) -> _FakeResponse:
        body = json or {}
        self.models_used.append(str(body.get("model")))
        if self.failures < self._fail_first_n:
            self.failures += 1
            raise httpx.ConnectError("provider unavailable")
        self.calls += 1
        # Rotate through distinct read tools so the duplicate-call guard
        # does not end the run before the budget does -- the budget has to
        # be what stops it, or the test proves nothing.
        name = _READ_ROTATION[(self.calls - 1) % len(_READ_ROTATION)]
        return _FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": f"call_{self.calls}",
                                    "type": "function",
                                    "function": {"name": name, "arguments": "{}"},
                                }
                            ],
                        }
                    }
                ],
                "usage": {"prompt_tokens": 500, "completion_tokens": 100},
            }
        )


def _env(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-a-real-key")
    monkeypatch.setenv("AGENT_RUNTIME_MODE", "openai")
    monkeypatch.setenv("TAVILY_RUNTIME_MODE", "demo")
    monkeypatch.setenv("APIFY_RUNTIME_MODE", "demo")
    monkeypatch.setenv("PROVIDER_PRICING_JSON", _PRICING)
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)
    clear_settings_cache()


def _run_agent(session_factory: Any, seed: Any) -> dict[str, Any]:
    with _override_client(session_factory) as client:
        token = _login(client, seed)
        headers = {"Authorization": f"Bearer {token}"}
        return dict(
            client.post(
                "/api/v1/agent/runs",
                json={"goal": "Keep looking at this lead.", "lead_id": seed.lead_public_id},
                headers=headers,
            ).json()
        )


# --- Budget enforcement --------------------------------------------------


def test_model_call_budget_stops_the_run_and_records_the_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch, AGENT_MAX_MODEL_CALLS="3")
    provider = _LoopingProvider()
    monkeypatch.setattr(runtime_module.httpx, "Client", provider)
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    payload = _run_agent(session_factory, seed)

    assert payload["status"] == "completed"
    with session_factory() as db:
        run = db.query(AgentRun).filter_by(public_id=payload["run_id"]).one()
    assert run.stop_reason == "max_model_calls"
    # The budget bounded the spend rather than reporting it afterwards.
    assert provider.calls == 3
    # A partial but honest answer, not a fabricated completion.
    assert run.final_answer_json is not None
    assert "budget" in json.dumps(run.final_answer_json).lower()


def test_output_token_budget_stops_the_run(monkeypatch: pytest.MonkeyPatch) -> None:
    _env(monkeypatch, AGENT_MAX_OUTPUT_TOKENS="500", AGENT_MAX_MODEL_CALLS="20")
    provider = _LoopingProvider()
    monkeypatch.setattr(runtime_module.httpx, "Client", provider)
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    payload = _run_agent(session_factory, seed)

    with session_factory() as db:
        run = db.query(AgentRun).filter_by(public_id=payload["run_id"]).one()
    assert run.stop_reason == "max_output_tokens"
    assert run.output_tokens >= 500


def test_cost_budget_stops_the_run_once_priced_spend_passes_the_ceiling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 500 in + 100 out per call at the configured rates = 360 micro-USD.
    _env(
        monkeypatch,
        AGENT_MAX_COST_MICRO_USD="700",
        AGENT_MAX_MODEL_CALLS="20",
        AGENT_MAX_OUTPUT_TOKENS="100000",
    )
    provider = _LoopingProvider()
    monkeypatch.setattr(runtime_module.httpx, "Client", provider)
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    payload = _run_agent(session_factory, seed)

    with session_factory() as db:
        run = db.query(AgentRun).filter_by(public_id=payload["run_id"]).one()
    assert run.stop_reason == "max_cost"
    assert run.cost_micro_usd >= 700


def test_cost_ceiling_is_disabled_by_default_while_pricing_is_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # With no pricing configured every cost is unknown, and a ceiling
    # computed from unknown costs would either never trip or trip at once.
    _env(monkeypatch, AGENT_MAX_MODEL_CALLS="2")
    monkeypatch.setenv("PROVIDER_PRICING_JSON", "")
    clear_settings_cache()
    provider = _LoopingProvider()
    monkeypatch.setattr(runtime_module.httpx, "Client", provider)
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    payload = _run_agent(session_factory, seed)

    with session_factory() as db:
        run = db.query(AgentRun).filter_by(public_id=payload["run_id"]).one()
        rows = db.query(ProviderUsage).filter_by(subject_id=run.public_id).all()
    assert run.stop_reason == "max_model_calls"
    assert rows and all(row.cost_micro_usd is None for row in rows)


# --- Usage ledger integration -------------------------------------------


def test_every_model_call_lands_in_the_ledger_under_the_runs_trace_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch, AGENT_MAX_MODEL_CALLS="3")
    provider = _LoopingProvider()
    monkeypatch.setattr(runtime_module.httpx, "Client", provider)
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    payload = _run_agent(session_factory, seed)

    with session_factory() as db:
        run = db.query(AgentRun).filter_by(public_id=payload["run_id"]).one()
        rows = db.query(ProviderUsage).filter_by(subject_id=run.public_id).all()

    model_rows = [row for row in rows if row.operation == "agent_run"]
    assert len(model_rows) == 3
    assert {row.trace_id for row in model_rows} == {run.trace_id}
    assert all(row.input_tokens == 500 for row in model_rows)
    assert run.cost_micro_usd == sum(row.cost_micro_usd or 0 for row in model_rows)


def test_run_records_its_prompt_version(monkeypatch: pytest.MonkeyPatch) -> None:
    _env(monkeypatch, AGENT_MAX_MODEL_CALLS="1")
    provider = _LoopingProvider()
    monkeypatch.setattr(runtime_module.httpx, "Client", provider)
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    payload = _run_agent(session_factory, seed)

    with session_factory() as db:
        run = db.query(AgentRun).filter_by(public_id=payload["run_id"]).one()
    assert run.prompt_key == "agent.system"
    assert run.prompt_version == 1


# --- Fallback ------------------------------------------------------------


def test_provider_failure_falls_back_to_the_next_routed_model_and_records_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routing = json.dumps(
        {
            "tool_selection": [
                {"provider": "openai", "model": "primary-model"},
                {"provider": "openai", "model": "backup-model"},
            ]
        }
    )
    _env(
        monkeypatch,
        AGENT_MODEL_ROUTING_JSON=routing,
        AGENT_MAX_MODEL_CALLS="2",
        AGENT_MAX_MODEL_FALLBACKS="1",
    )
    provider = _LoopingProvider(fail_first_n=1)
    monkeypatch.setattr(runtime_module.httpx, "Client", provider)
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    payload = _run_agent(session_factory, seed)

    with session_factory() as db:
        run = db.query(AgentRun).filter_by(public_id=payload["run_id"]).one()
        rows = db.query(ProviderUsage).filter_by(subject_id=run.public_id).all()

    assert provider.models_used[0] == "primary-model"
    assert "backup-model" in provider.models_used
    assert run.fallback_used is True
    assert run.model == "backup-model"
    # The failed attempt is in the ledger too: a fallback is a behaviour
    # change, and an audit that only shows the successful call hides it.
    errors = [row for row in rows if row.status == "error"]
    assert len(errors) == 1
    assert errors[0].model == "primary-model"


def test_run_fails_when_fallbacks_are_exhausted_rather_than_inventing_an_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch, AGENT_MAX_MODEL_FALLBACKS="0")
    provider = _LoopingProvider(fail_first_n=5)
    monkeypatch.setattr(runtime_module.httpx, "Client", provider)
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    payload = _run_agent(session_factory, seed)

    # The run is recorded as failed, with the provider error in the ledger.
    # It carries no final answer: a failed run must not hand back a
    # zero-confidence conclusion that reads like one the model reached.
    assert payload["status"] == "failed"
    with session_factory() as db:
        run = db.query(AgentRun).filter_by(public_id=payload["run_id"]).one()
        rows = db.query(ProviderUsage).filter_by(status="error").all()
    assert run.error_code == "model_provider_unavailable"
    assert run.final_answer_json is None
    assert len(rows) == 1
