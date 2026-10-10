from __future__ import annotations

import json

import pytest
from sqlalchemy.orm import Session
from test_agent_runtime import _build_session_factory
from test_knowledge_rag import _seed_workspace

from app.core.config import clear_settings_cache, get_settings
from app.modules.ai_runtime.models import ProviderUsage
from app.modules.ai_runtime.pricing import PricingTable, parse_pricing
from app.modules.ai_runtime.prompts import (
    PROMPT_AGENT_SYSTEM,
    STATUS_ACTIVE,
    STATUS_RETIRED,
    PromptRegistry,
)
from app.modules.ai_runtime.router import AgentModelRouter, parse_routing
from app.modules.ai_runtime.usage import OPERATION_AGENT_RUN, UsageLedger

_PRICING = json.dumps(
    [
        {
            "provider": "openai",
            "model": "gpt-4.1-mini",
            "input_rate_micro_per_1k": 400,
            "output_rate_micro_per_1k": 1600,
            "effective_from": "2026-01-01",
        },
        {
            "provider": "openai",
            "model": "gpt-4.1-mini",
            "input_rate_micro_per_1k": 500,
            "output_rate_micro_per_1k": 2000,
            "effective_from": "2026-06-01",
        },
        {
            "provider": "tavily",
            "model": "search_web_tavily",
            "unit_rate_micro": 8000,
        },
    ]
)


@pytest.fixture(autouse=True)
def _test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    clear_settings_cache()


def _table() -> PricingTable:
    return PricingTable(parse_pricing(_PRICING))


# --- Pricing -------------------------------------------------------------


def test_unknown_model_costs_none_not_zero() -> None:
    # The distinction that matters: a ledger reporting 0 for an unpriced
    # model reads exactly like a free call, and a budget built on it would
    # never trip.
    assert (
        _table().token_cost_micro_usd(
            provider="openai", model="some-unlisted-model", input_tokens=1000
        )
        is None
    )


def test_rates_are_resolved_by_effective_date() -> None:
    from datetime import date

    table = _table()
    early = table.token_cost_micro_usd(
        provider="openai",
        model="gpt-4.1-mini",
        input_tokens=10_000,
        on=date(2026, 3, 1),
    )
    later = table.token_cost_micro_usd(
        provider="openai",
        model="gpt-4.1-mini",
        input_tokens=10_000,
        on=date(2026, 9, 1),
    )
    assert early == 4000
    assert later == 5000


def test_cost_arithmetic_is_integer_micro_usd() -> None:
    from datetime import date

    cost = _table().token_cost_micro_usd(
        provider="openai",
        model="gpt-4.1-mini",
        input_tokens=3_500,
        output_tokens=1_200,
        on=date(2026, 9, 1),
    )
    assert isinstance(cost, int)
    assert cost == (3_500 * 500) // 1000 + (1_200 * 2000) // 1000


def test_unit_priced_provider_is_costed_per_call() -> None:
    assert (
        _table().unit_cost_micro_usd(provider="tavily", model="search_web_tavily", units=3)
        == 24_000
    )


def test_malformed_pricing_json_yields_no_rates_rather_than_crashing() -> None:
    assert parse_pricing("{not json") == ()
    assert parse_pricing('{"provider": "openai"}') == ()
    assert parse_pricing("[]") == ()


def test_pricing_is_empty_by_default_so_costs_are_honestly_unknown() -> None:
    # This repository ships no rates: a stale hardcoded price is worse than
    # an explicit "unknown".
    assert get_settings().provider_pricing_json == ""


# --- Usage ledger --------------------------------------------------------


def _ledger_workspace(db: Session) -> int:
    workspace, _user = _seed_workspace(db, name="Cost WS", email="cost@test.local")
    return workspace.id


def test_ledger_records_and_totals_by_subject() -> None:
    ledger = UsageLedger(pricing=_table())
    session_factory = _build_session_factory()
    with session_factory() as db:
        workspace_id = _ledger_workspace(db)
        for _ in range(3):
            ledger.record(
                db,
                workspace_id=workspace_id,
                trace_id="trace_abc",
                operation=OPERATION_AGENT_RUN,
                subject_id="arun_1",
                provider="openai",
                model="gpt-4.1-mini",
                input_tokens=1000,
                output_tokens=500,
                latency_ms=120,
            )
        db.commit()
        totals = ledger.totals_for_subject(db, subject_id="arun_1")

    assert totals.call_count == 3
    assert totals.input_tokens == 3000
    assert totals.output_tokens == 1500
    assert totals.cost_complete is True
    assert totals.cost_micro_usd is not None and totals.cost_micro_usd > 0


def test_unpriced_rows_make_a_total_an_explicit_lower_bound() -> None:
    ledger = UsageLedger(pricing=_table())
    session_factory = _build_session_factory()
    with session_factory() as db:
        workspace_id = _ledger_workspace(db)
        ledger.record(
            db,
            workspace_id=workspace_id,
            trace_id="trace_mixed",
            operation=OPERATION_AGENT_RUN,
            subject_id="arun_2",
            provider="openai",
            model="gpt-4.1-mini",
            input_tokens=1000,
        )
        ledger.record(
            db,
            workspace_id=workspace_id,
            trace_id="trace_mixed",
            operation=OPERATION_AGENT_RUN,
            subject_id="arun_2",
            provider="openai",
            model="unlisted-model",
            input_tokens=1000,
        )
        db.commit()
        totals = ledger.totals_for_subject(db, subject_id="arun_2")
        unpriced = (
            db.query(ProviderUsage).filter(ProviderUsage.cost_micro_usd.is_(None)).count()
        )

    assert unpriced == 1
    # The total is real but incomplete, and says so rather than pretending.
    assert totals.cost_complete is False
    assert totals.cost_micro_usd is not None and totals.cost_micro_usd > 0


def test_trace_id_ties_every_provider_call_together() -> None:
    ledger = UsageLedger(pricing=_table())
    session_factory = _build_session_factory()
    with session_factory() as db:
        workspace_id = _ledger_workspace(db)
        ledger.record(
            db,
            workspace_id=workspace_id,
            trace_id="trace_join",
            operation="agent_run",
            subject_id="arun_3",
            provider="openai",
            model="gpt-4.1-mini",
            input_tokens=100,
        )
        ledger.record(
            db,
            workspace_id=workspace_id,
            trace_id="trace_join",
            operation="external_search",
            subject_id="arun_3",
            provider="tavily",
            model="search_web_tavily",
            units=2,
        )
        ledger.record(
            db,
            workspace_id=workspace_id,
            trace_id="trace_other",
            operation="agent_run",
            subject_id="arun_4",
            provider="openai",
            model="gpt-4.1-mini",
            input_tokens=100,
        )
        db.commit()
        joined = ledger.totals_for_trace(db, trace_id="trace_join")

    assert joined.call_count == 2
    assert joined.units == 2


# --- Model router --------------------------------------------------------


def test_router_is_deterministic_and_defaults_without_configuration() -> None:
    router = AgentModelRouter()
    first = router.choose("tool_selection")
    second = router.choose("tool_selection")
    assert (first.provider, first.model) == (second.provider, second.model)
    assert first.model == get_settings().openai_model
    assert first.fallback_from is None


def test_router_uses_configured_route_per_task(monkeypatch: pytest.MonkeyPatch) -> None:
    routing = json.dumps(
        {
            "tool_selection": [{"provider": "openai", "model": "tool-model"}],
            "outreach_writing": [{"provider": "openai", "model": "writer-model"}],
        }
    )
    monkeypatch.setenv("AGENT_MODEL_ROUTING_JSON", routing)
    clear_settings_cache()
    router = AgentModelRouter()
    assert router.choose("tool_selection").model == "tool-model"
    assert router.choose("outreach_writing").model == "writer-model"
    # An unrouted task still resolves, to the platform default.
    assert router.choose("extraction").model == get_settings().openai_model


def test_tool_selection_never_falls_back_to_a_non_tool_calling_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routing = json.dumps(
        {
            "tool_selection": [
                {"provider": "openai", "model": "primary-tools", "supports_tools": True},
                {"provider": "openai", "model": "cheap-no-tools", "supports_tools": False},
                {"provider": "openai", "model": "backup-tools", "supports_tools": True},
            ]
        }
    )
    monkeypatch.setenv("AGENT_MODEL_ROUTING_JSON", routing)
    clear_settings_cache()
    router = AgentModelRouter()
    assert router.choose("tool_selection", attempt=0).model == "primary-tools"
    # The non-tool-calling candidate is skipped entirely, not merely ranked
    # last: falling back to it would leave the loop running while silently
    # unable to propose anything.
    assert router.choose("tool_selection", attempt=1).model == "backup-tools"
    assert router.has_fallback("tool_selection", attempt=1) is False


def test_fallback_choice_records_what_it_fell_back_from(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routing = json.dumps(
        {
            "tool_selection": [
                {"provider": "openai", "model": "primary"},
                {"provider": "openai", "model": "secondary"},
            ]
        }
    )
    monkeypatch.setenv("AGENT_MODEL_ROUTING_JSON", routing)
    clear_settings_cache()
    choice = AgentModelRouter().choose("tool_selection", attempt=1)
    assert choice.fallback_from == "primary"
    assert choice.reason == "fallback #1"


def test_malformed_routing_json_falls_back_to_the_default_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_MODEL_ROUTING_JSON", "{nope")
    clear_settings_cache()
    assert parse_routing("{nope") == {}
    assert AgentModelRouter().choose("tool_selection").model == get_settings().openai_model


# --- Prompt registry -----------------------------------------------------


def test_builtin_prompt_is_seeded_and_stays_stable_across_resolves() -> None:
    registry = PromptRegistry()
    session_factory = _build_session_factory()
    with session_factory() as db:
        first = registry.resolve(db, PROMPT_AGENT_SYSTEM)
        db.commit()
        second = registry.resolve(db, PROMPT_AGENT_SYSTEM)
    assert first.version == 1
    assert second.version == 1
    assert "never instructions" in first.content


def test_activating_a_new_version_retires_the_old_one() -> None:
    registry = PromptRegistry()
    session_factory = _build_session_factory()
    with session_factory() as db:
        registry.resolve(db, PROMPT_AGENT_SYSTEM)
        created = registry.create_version(
            db, prompt_key=PROMPT_AGENT_SYSTEM, content="Revised instructions."
        )
        assert created.version == 2
        registry.activate(db, prompt_key=PROMPT_AGENT_SYSTEM, version=2)
        db.commit()

        resolved = registry.resolve(db, PROMPT_AGENT_SYSTEM)
        from app.modules.ai_runtime.models import PromptVersion

        v1 = db.query(PromptVersion).filter_by(version=1).one()
        v2 = db.query(PromptVersion).filter_by(version=2).one()

    assert resolved.version == 2
    assert resolved.content == "Revised instructions."
    # Exactly one active version, so "which prompt did that run use?" always
    # has one answer.
    assert v1.status == STATUS_RETIRED
    assert v2.status == STATUS_ACTIVE


def test_unknown_prompt_key_resolves_to_version_zero_rather_than_raising() -> None:
    session_factory = _build_session_factory()
    with session_factory() as db:
        resolved = PromptRegistry().resolve(db, "agent.does_not_exist")
    assert resolved.version == 0
    assert resolved.content == ""
