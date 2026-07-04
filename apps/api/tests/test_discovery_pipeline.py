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

    assert [item.key for item in variants] == [
        "original",
        "normalized",
        "bilingual_keyword_expansion",
    ]
    assert any("\u0627\u0644\u0639\u0642\u0627\u0631\u0627\u062a" in item.text for item in variants)


def test_query_planner_handles_arabic_input_deterministically() -> None:
    planner = QueryPlanner()
    variants = planner.plan(
        business_type="\u0627\u0644\u062a\u0637\u0648\u064a\u0631 \u0627\u0644\u0639\u0642\u0627\u0631\u064a",
        city="\u0627\u0644\u0631\u064a\u0627\u0636",
        region=None,
        keyword_filter="\u062a\u0645\u0648\u064a\u0644",
        bilingual_enabled=True,
    )

    assert variants[0].language in {"ar", "mixed"}
    assert variants[0].text
    assert len({item.text for item in variants}) == len(variants)
    assert any("real estate development" in item.text for item in variants)


def test_query_planner_expands_arabic_salons_to_english_keyword() -> None:
    planner = QueryPlanner()
    variants = planner.plan(
        business_type="\u0635\u0627\u0644\u0648\u0646\u0627\u062a \u062a\u062c\u0645\u064a\u0644",
        city="\u062c\u062f\u0629",
        region=None,
        keyword_filter=None,
        bilingual_enabled=True,
    )

    assert variants[0].text == (
        "\u0635\u0627\u0644\u0648\u0646\u0627\u062a \u062a\u062c\u0645\u064a\u0644 "
        "\u062c\u062f\u0629"
    )
    assert any("beauty salon" in item.text for item in variants)


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
    low = LeadCandidate(
        company_name="Acme",
        city="Istanbul",
        phone="+90 555 111 22 33",
        confidence=0.6,
        completeness=0.7,
        review_count=2,
    )
    high = LeadCandidate(
        company_name="Acme",
        city="Istanbul",
        phone="+90 555 1112233",
        confidence=0.9,
        completeness=0.9,
        review_count=20,
    )
    merged = merger.merge([[low], [high]], max_candidates=10)
    deduped = deduper.dedupe(merged)
    ranked = ranker.rank(deduped, max_candidates=10)
    assert len(deduped) == 1
    assert ranked[0].confidence == 0.9
