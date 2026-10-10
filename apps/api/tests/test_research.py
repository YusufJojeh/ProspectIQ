from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.modules.leads.models import Lead
from app.modules.provider_serpapi.models import ProviderFetch, ProviderNormalizedFact
from app.modules.research.contradiction import ContradictionDetector
from app.modules.research.models import ResearchContradiction
from app.modules.research.orchestrator import ResearchOrchestrator
from app.modules.research.planner import ResearchPlanner
from app.modules.research.schemas import ResearchPlan, ResearchStep
from app.modules.search_jobs.models import SearchJob  # noqa: F401
from app.modules.users.models import Workspace
from app.shared.enums.jobs import ProviderFetchStatus


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


# --- ResearchPlanner -------------------------------------------------------


def test_planner_quick_depth_only_uses_tavily() -> None:
    plan = ResearchPlanner().plan(
        depth="quick", has_place_identity=False, available_providers={"tavily", "serpapi", "apify"}
    )

    assert [step.provider for step in plan.steps] == ["tavily"]


def test_planner_standard_depth_adds_apify_company_website_crawler() -> None:
    plan = ResearchPlanner().plan(
        depth="standard", has_place_identity=False, available_providers={"tavily", "apify"}
    )

    assert [(step.provider, step.mode) for step in plan.steps] == [
        ("tavily", "web_search"),
        ("apify", "company_website_crawler"),
    ]


def test_planner_deep_depth_with_place_identity_adds_serpapi_and_reviews_crawl() -> None:
    plan = ResearchPlanner().plan(
        depth="deep",
        has_place_identity=True,
        available_providers={"tavily", "serpapi", "apify"},
    )

    assert [(step.provider, step.mode) for step in plan.steps] == [
        ("tavily", "web_search"),
        ("apify", "company_website_crawler"),
        ("serpapi", "web_search"),
        ("apify", "reviews_crawler"),
    ]


def test_planner_deep_depth_without_place_identity_skips_reviews_crawl() -> None:
    plan = ResearchPlanner().plan(
        depth="deep",
        has_place_identity=False,
        available_providers={"tavily", "serpapi", "apify"},
    )

    assert [(step.provider, step.mode) for step in plan.steps] == [
        ("tavily", "web_search"),
        ("apify", "company_website_crawler"),
        ("serpapi", "web_search"),
    ]


def test_planner_excludes_unavailable_providers_instead_of_failing() -> None:
    plan = ResearchPlanner().plan(depth="standard", has_place_identity=False, available_providers=set())

    assert plan.steps == []


# --- ContradictionDetector ---------------------------------------------------


def _fetch(fetch_id: int, provider: str) -> ProviderFetch:
    fetch = ProviderFetch(
        workspace_id=1,
        provider=provider,
        engine="web_search",
        mode="research",
        request_fingerprint=f"fp-{fetch_id}",
        request_params_json={},
        status=ProviderFetchStatus.OK.value,
    )
    fetch.id = fetch_id
    return fetch


def _fact(*, provider_fetch_id: int, **overrides: object) -> ProviderNormalizedFact:
    defaults: dict[str, object] = {
        "workspace_id": 1,
        "lead_id": 1,
        "provider_fetch_id": provider_fetch_id,
        "source_type": "test",
        "company_name": "Acme Dental",
        "confidence": 0.5,
    }
    defaults.update(overrides)
    return ProviderNormalizedFact(**defaults)


def test_contradiction_detector_flags_disagreeing_phone_across_two_providers() -> None:
    fetches_by_id = {1: _fetch(1, "tavily"), 2: _fetch(2, "apify")}
    facts = [
        _fact(provider_fetch_id=1, phone="+15550100"),
        _fact(provider_fetch_id=2, phone="+19995550101"),
    ]

    contradictions = ContradictionDetector().detect(facts, fetches_by_id)

    assert len(contradictions) == 1
    assert contradictions[0].claim_type == "phone"
    providers = {value.provider for value in contradictions[0].values}
    assert providers == {"tavily", "apify"}


def test_contradiction_detector_ignores_same_value_or_single_provider() -> None:
    fetches_by_id = {1: _fetch(1, "tavily"), 2: _fetch(2, "apify")}
    same_value_facts = [
        _fact(provider_fetch_id=1, phone="+15550100"),
        _fact(provider_fetch_id=2, phone="+15550100"),
    ]
    assert ContradictionDetector().detect(same_value_facts, fetches_by_id) == []

    single_provider_fetches = {1: _fetch(1, "apify"), 2: _fetch(2, "apify")}
    disagreeing_same_provider_facts = [
        _fact(provider_fetch_id=1, phone="+15550100"),
        _fact(provider_fetch_id=2, phone="+19995550101"),
    ]
    assert (
        ContradictionDetector().detect(disagreeing_same_provider_facts, single_provider_fetches)
        == []
    )


# --- ResearchOrchestrator ----------------------------------------------------


class _FixedPlanner:
    def __init__(self, plan: ResearchPlan) -> None:
        self._plan = plan

    def plan(self, *, depth, has_place_identity, available_providers):  # noqa: ANN001
        return self._plan


class _ScriptedRouter:
    """Fake ResearchProviderRouter that returns a canned StepOutcome per step
    and persists a real ProviderFetch row so orchestrator id/public_id
    plumbing behaves like the real router."""

    def __init__(self, outcomes: dict[tuple[str, str], object]) -> None:
        self._outcomes = outcomes
        self.calls: list[tuple[str, str, str | None]] = []

    def run_step(self, db, *, workspace_id, search_job_id, lead, query, step, known_website_url):  # noqa: ANN001
        self.calls.append((step.provider, step.mode, known_website_url))
        build_outcome = self._outcomes[(step.provider, step.mode)]
        return build_outcome(db, workspace_id)


def _make_fetch_outcome_builder(provider: str, mode: str, *, normalized_facts, discovered_website_url=None):
    from app.modules.research.router import StepOutcome

    def build(db, workspace_id):  # noqa: ANN001
        fetch = ProviderFetch(
            workspace_id=workspace_id,
            provider=provider,
            engine=mode,
            mode="research" if provider != "apify" else "crawl",
            request_fingerprint=f"fp-{provider}-{mode}",
            request_params_json={},
            status=ProviderFetchStatus.OK.value,
            started_at=datetime.now(tz=UTC),
            finished_at=datetime.now(tz=UTC),
        )
        db.add(fetch)
        db.commit()
        db.refresh(fetch)
        return StepOutcome(
            step=ResearchStep(provider=provider, mode=mode, reason="test"),
            fetch=fetch,
            payload={},
            normalized_facts=normalized_facts,
            discovered_website_url=discovered_website_url,
        )

    return build


def test_orchestrator_sequences_tavily_discovery_into_apify_crawl_and_detects_contradiction() -> None:
    session_factory = _build_session_factory()
    with session_factory() as db:
        workspace = Workspace(name="LeadScope Workspace")
        db.add(workspace)
        db.commit()
        db.refresh(workspace)

        lead = Lead(workspace_id=workspace.id, company_name="Acme Dental", website_url=None)
        db.add(lead)
        db.commit()
        db.refresh(lead)

        plan = ResearchPlan(
            depth="standard",
            steps=[
                ResearchStep(provider="tavily", mode="web_search", reason="baseline"),
                ResearchStep(
                    provider="apify", mode="company_website_crawler", reason="crawl own site"
                ),
            ],
        )
        outcomes = {
            ("tavily", "web_search"): _make_fetch_outcome_builder(
                "tavily",
                "web_search",
                normalized_facts=[
                    {
                        "source_type": "tavily_research",
                        "company_name": "Acme Dental",
                        "website_url": "https://acmedental.example",
                        "website_domain": "acmedental.example",
                        "phone": "+15550100",
                        "confidence": 0.6,
                        "completeness": 0.5,
                        "facts": {},
                    }
                ],
                discovered_website_url="https://acmedental.example",
            ),
            ("apify", "company_website_crawler"): _make_fetch_outcome_builder(
                "apify",
                "company_website_crawler",
                normalized_facts=[
                    {
                        "source_type": "apify_company_website_crawler",
                        "company_name": "Acme Dental",
                        "phone": "+19995550101",
                        "confidence": 0.7,
                        "completeness": 0.6,
                        "facts": {},
                        "actor_run_id": "run-1",
                    }
                ],
            ),
        }
        router = _ScriptedRouter(outcomes)

        orchestrator = ResearchOrchestrator()
        orchestrator.planner = _FixedPlanner(plan)
        orchestrator.router = router

        result = orchestrator.run(db, workspace_id=workspace.id, lead=lead, depth="standard")

        assert router.calls[0] == ("tavily", "web_search", None)
        assert router.calls[1] == ("apify", "company_website_crawler", "https://acmedental.example")
        assert result.status == ProviderFetchStatus.OK.value
        assert result.providers_used == ["tavily", "apify"]
        assert result.steps_executed == 2
        assert result.facts_created == 2
        assert len(result.contradictions) == 1
        assert result.contradictions[0].claim_type == "phone"
        assert result.last_provider_fetch_public_id is not None

        persisted_facts = db.query(ProviderNormalizedFact).all()
        assert len(persisted_facts) == 2
        apify_fact = next(f for f in persisted_facts if f.source_type == "apify_company_website_crawler")
        assert apify_fact.actor_run_id == "run-1"
        assert apify_fact.freshness_score == 1.0

        assert db.query(ResearchContradiction).count() == 1


def test_orchestrator_skips_apify_company_crawl_when_no_website_is_known() -> None:
    session_factory = _build_session_factory()
    with session_factory() as db:
        workspace = Workspace(name="LeadScope Workspace")
        db.add(workspace)
        db.commit()
        db.refresh(workspace)

        lead = Lead(workspace_id=workspace.id, company_name="Acme Dental", website_url=None)
        db.add(lead)
        db.commit()
        db.refresh(lead)

        plan = ResearchPlan(
            depth="standard",
            steps=[
                ResearchStep(
                    provider="apify", mode="company_website_crawler", reason="crawl own site"
                )
            ],
        )

        def _unexpected_call(*args, **kwargs):  # noqa: ANN002, ANN003
            raise AssertionError("router.run_step should not be called when no website is known.")

        router = _ScriptedRouter({})
        router.run_step = _unexpected_call  # type: ignore[method-assign]

        orchestrator = ResearchOrchestrator()
        orchestrator.planner = _FixedPlanner(plan)
        orchestrator.router = router

        result = orchestrator.run(db, workspace_id=workspace.id, lead=lead, depth="standard")

        assert result.providers_used == []
        assert result.steps_executed == 0
        assert result.status == ProviderFetchStatus.ERROR.value
        assert result.last_provider_fetch_public_id is None


def test_orchestrator_returns_error_result_when_plan_has_no_steps() -> None:
    session_factory = _build_session_factory()
    with session_factory() as db:
        workspace = Workspace(name="LeadScope Workspace")
        db.add(workspace)
        db.commit()
        db.refresh(workspace)

        lead = Lead(workspace_id=workspace.id, company_name="Acme Dental", website_url=None)
        db.add(lead)
        db.commit()
        db.refresh(lead)

        orchestrator = ResearchOrchestrator()
        orchestrator.planner = _FixedPlanner(ResearchPlan(depth="quick", steps=[]))

        result = orchestrator.run(db, workspace_id=workspace.id, lead=lead, depth="quick")

        assert result.status == ProviderFetchStatus.ERROR.value
        assert result.last_provider_fetch_public_id is None
        assert "No research providers are configured" in result.message
