from __future__ import annotations

from app.modules.provider_serpapi.schemas import LeadCandidate
from app.workers.orchestration.discovery_pipeline import (
    CandidateRanker,
    CrossSourceDeduper,
    EngineExecutionPlanner,
    QueryPlanner,
    QueryVariant,
    ResultMerger,
)


def test_query_planner_expands_english_with_arabic_keywords() -> None:
    planner = QueryPlanner()
    variants = planner.plan(
        business_type="real estate development",
        city="Riyadh",
        region=None,
        keyword_filter="financing",
        bilingual_enabled=True,
    )
    assert [item.key for item in variants] == ["original", "normalized", "bilingual_keyword_expansion"]
    assert any("العقارات" in item.text for item in variants)


def test_query_planner_handles_arabic_input_deterministically() -> None:
    planner = QueryPlanner()
    variants = planner.plan(
        business_type="التطوير العقاري",
        city="الرياض",
        region=None,
        keyword_filter="تمويل",
        bilingual_enabled=True,
    )
    assert variants[0].language in {"ar", "mixed"}
    assert variants[0].text
    assert len({item.text for item in variants}) == len(variants)


def test_engine_execution_planner_enforces_mode_and_budget() -> None:
    planner = EngineExecutionPlanner()
    variants = [
        QueryVariant(key="original", text="dentist istanbul", language="en"),
        QueryVariant(key="normalized", text="dentist istanbul turkey", language="en"),
    ]
    tasks = planner.plan(
        mode="multi_engine_multi_query",
        enabled_engines=["google_maps_search", "google_web"],
        query_variants=variants,
        max_calls_per_job=3,
        max_concurrency=2,
    )
    assert len(tasks) == 3
    assert {task.adapter_name for task in tasks}.issubset({"google_maps_search", "google_web"})


def test_merge_dedupe_rank_is_deterministic() -> None:
    merger = ResultMerger()
    deduper = CrossSourceDeduper()
    ranker = CandidateRanker()
    low = LeadCandidate(company_name="Acme", city="Istanbul", phone="+90 555 111 22 33", confidence=0.6, completeness=0.7, review_count=2)
    high = LeadCandidate(company_name="Acme", city="Istanbul", phone="+90 555 1112233", confidence=0.9, completeness=0.9, review_count=20)
    merged = merger.merge([[low], [high]], max_candidates=10)
    deduped = deduper.dedupe(merged)
    ranked = ranker.rank(deduped, max_candidates=10)
    assert len(deduped) == 1
    assert ranked[0].confidence == 0.9
