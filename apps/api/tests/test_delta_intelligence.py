from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.modules.research.delta import ChangeCandidate, ChangeExplainer, FactDiffEngine
from app.modules.research.repository import ResearchRepository
from app.modules.search_jobs.models import SearchJob  # noqa: F401
from app.modules.users.models import Workspace  # noqa: F401


def _build_session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session
    )


# --- FactDiffEngine ---------------------------------------------------------


def test_diff_engine_emits_evidence_added_for_new_claim_type() -> None:
    candidates = FactDiffEngine().diff(
        previous={}, current={"phone": ("+15550100", 0.8)}
    )

    assert len(candidates) == 1
    assert candidates[0].claim_type == "phone"
    assert candidates[0].previous_value is None
    assert candidates[0].new_value == "+15550100"
    assert candidates[0].event_type == "contact_info_changed"
    assert candidates[0].direction == "neutral"


def test_diff_engine_emits_no_event_when_value_is_unchanged() -> None:
    candidates = FactDiffEngine().diff(
        previous={"phone": ("+15550100", 0.8)}, current={"phone": ("+15550100", 0.9)}
    )

    assert candidates == []


def test_diff_engine_emits_no_event_when_claim_disappears_in_current_run() -> None:
    candidates = FactDiffEngine().diff(
        previous={"phone": ("+15550100", 0.8)}, current={}
    )

    assert candidates == []


def test_diff_engine_rating_improved_above_noise_threshold() -> None:
    candidates = FactDiffEngine().diff(
        previous={"rating": ("3.8", 0.8)}, current={"rating": ("4.6", 0.8)}
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.event_type == "rating_changed"
    assert candidate.direction == "improved"
    assert candidate.significance > 0.0


def test_diff_engine_rating_declined_above_noise_threshold() -> None:
    candidates = FactDiffEngine().diff(
        previous={"rating": ("4.6", 0.8)}, current={"rating": ("3.8", 0.8)}
    )

    assert len(candidates) == 1
    assert candidates[0].direction == "declined"


def test_diff_engine_drops_rating_change_below_noise_threshold() -> None:
    candidates = FactDiffEngine().diff(
        previous={"rating": ("4.60", 0.8)}, current={"rating": ("4.61", 0.8)}
    )

    assert candidates == []


def test_diff_engine_review_count_improved_and_declined() -> None:
    improved = FactDiffEngine().diff(
        previous={"review_count": ("100", 0.8)}, current={"review_count": ("140", 0.8)}
    )
    declined = FactDiffEngine().diff(
        previous={"review_count": ("140", 0.8)}, current={"review_count": ("100", 0.8)}
    )

    assert improved[0].direction == "improved"
    assert improved[0].event_type == "review_count_changed"
    assert declined[0].direction == "declined"


def test_diff_engine_drops_review_count_change_below_noise_threshold() -> None:
    candidates = FactDiffEngine().diff(
        previous={"review_count": ("100", 0.8)}, current={"review_count": ("101", 0.8)}
    )

    assert candidates == []


def test_diff_engine_categorical_change_is_neutral_direction() -> None:
    candidates = FactDiffEngine().diff(
        previous={"website_url": ("https://old.example", 0.8)},
        current={"website_url": ("https://new.example", 0.8)},
    )

    assert len(candidates) == 1
    assert candidates[0].direction == "neutral"
    assert candidates[0].event_type == "website_changed"


def test_diff_engine_unmapped_claim_type_falls_back_to_value_changed() -> None:
    candidates = FactDiffEngine().diff(
        previous={"opening_hours": ("9-5", 0.8)}, current={"opening_hours": ("8-6", 0.8)}
    )

    assert candidates[0].event_type == "value_changed"


def test_diff_engine_classifies_new_business_intelligence_claims() -> None:
    engine = FactDiffEngine()
    booking = engine.diff(
        previous={"online_booking": ("false", 0.8)},
        current={"online_booking": ("true", 0.8)},
    )[0]
    branches = engine.diff(
        previous={"branch_count": ("2", 0.8)}, current={"branch_count": ("4", 0.8)}
    )[0]
    services = engine.diff(
        previous={"services": ('["Cleaning"]', 0.8)},
        current={"services": ('["Cleaning","Implants"]', 0.8)},
    )[0]
    hiring = engine.diff(
        previous={"hiring_signal": ('{"active":false,"roles_count":0}', 0.8)},
        current={"hiring_signal": ('{"active":true,"roles_count":4}', 0.8)},
    )[0]
    maturity = engine.diff(
        previous={"digital_maturity": ('{"score":42}', 0.8)},
        current={"digital_maturity": ('{"score":71}', 0.8)},
    )[0]

    assert booking.direction == "improved" and booking.event_type == "digital_capability_changed"
    assert branches.direction == "improved" and branches.event_type == "branch_count_changed"
    assert services.direction == "improved" and services.event_type == "services_changed"
    assert hiring.direction == "improved" and hiring.event_type == "hiring_signal_changed"
    assert maturity.direction == "improved" and maturity.significance == 0.725


# --- ChangeExplainer ---------------------------------------------------------


def test_explainer_uses_template_fallback_when_runtime_is_not_openai(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.modules.research import delta as delta_module

    class _StubSettings:
        research_agent_runtime = "stub"
        openai_api_key = ""

    monkeypatch.setattr(delta_module, "get_settings", lambda: _StubSettings())

    candidate = ChangeCandidate(
        claim_type="rating",
        previous_value="3.8",
        new_value="4.6",
        event_type="rating_changed",
        direction="improved",
        significance=0.8,
    )
    explanation = ChangeExplainer().explain(candidate, company_name="Acme Dental")

    assert "Acme Dental" in explanation
    assert "3.8" in explanation
    assert "4.6" in explanation
    assert "improved" in explanation


def test_explainer_falls_back_to_template_on_llm_exception(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.modules.research import delta as delta_module

    class _OpenAISettings:
        research_agent_runtime = "openai"
        openai_api_key = "sk-test"
        research_agent_max_runtime_seconds = 30

    monkeypatch.setattr(delta_module, "get_settings", lambda: _OpenAISettings())

    def _boom(self: ChangeExplainer, candidate: ChangeCandidate, *, company_name: str) -> str:
        raise RuntimeError("network unavailable")

    monkeypatch.setattr(ChangeExplainer, "_explain_with_llm", _boom)

    candidate = ChangeCandidate(
        claim_type="phone",
        previous_value=None,
        new_value="+15550100",
        event_type="contact_info_changed",
        direction="neutral",
        significance=0.2,
    )
    explanation = ChangeExplainer().explain(candidate, company_name="Acme Dental")

    assert "Acme Dental" in explanation
    assert "+15550100" in explanation


def test_explainer_template_handles_new_evidence_with_no_previous_value() -> None:
    candidate = ChangeCandidate(
        claim_type="website_url",
        previous_value=None,
        new_value="https://acme.example",
        event_type="website_changed",
        direction="neutral",
        significance=0.2,
    )

    explanation = ChangeExplainer()._explain_with_template(candidate, company_name="Acme Dental")

    assert explanation == (
        "New evidence found for Acme Dental: website_url is now 'https://acme.example'."
    )


# --- ResearchRepository run/snapshot/event persistence ----------------------


def test_research_repository_persists_and_reloads_runs_snapshots_and_events() -> None:
    session_factory = _build_session_factory()
    repository = ResearchRepository()

    with session_factory() as db:
        assert repository.get_latest_ok_run(db, lead_id=1) is None

        first_run = repository.create_run(
            db,
            workspace_id=1,
            lead_id=1,
            depth="quick",
            mode="planned",
            status="ok",
            providers_used=["tavily"],
            evidence_confidence=0.5,
            research_coverage=0.5,
        )
        repository.save_snapshot(
            db,
            research_run_id=first_run.id,
            workspace_id=1,
            lead_id=1,
            snapshot_map={"rating": ("3.8", 0.7)},
        )

        second_run = repository.create_run(
            db,
            workspace_id=1,
            lead_id=1,
            depth="quick",
            mode="planned",
            status="ok",
            providers_used=["tavily"],
            evidence_confidence=0.6,
            research_coverage=0.6,
        )
        repository.save_snapshot(
            db,
            research_run_id=second_run.id,
            workspace_id=1,
            lead_id=1,
            snapshot_map={"rating": ("4.6", 0.8)},
        )

        latest = repository.get_latest_ok_run(db, lead_id=1)
        assert latest is not None
        assert latest.id == second_run.id

        previous_snapshot = repository.load_snapshot_map(db, first_run.id)
        assert previous_snapshot == {"rating": ("3.8", 0.7)}

        event = repository.save_change_event(
            db,
            workspace_id=1,
            lead_id=1,
            previous_research_run_id=first_run.id,
            current_research_run_id=second_run.id,
            claim_type="rating",
            previous_value="3.8",
            new_value="4.6",
            event_type="rating_changed",
            direction="improved",
            significance=0.8,
            explanation="Acme Dental's rating improved from '3.8' to '4.6'.",
            triggered_rescore=True,
        )

        assert event.id is not None
        assert event.triggered_rescore is True
        assert event.direction == "improved"
