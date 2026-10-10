from __future__ import annotations

import json
from datetime import UTC, datetime

from app.modules.provider_serpapi.models import ProviderFetch, ProviderNormalizedFact
from app.modules.research.business_intelligence import BusinessIntelligenceProjector
from app.modules.research.evidence_graph import (
    CanonicalFact,
    EvidenceGraph,
    EvidenceGraphBuilder,
    FactResolver,
    source_quality,
)
from app.modules.signals.models import LeadSignal
from app.shared.enums.jobs import ProviderFetchStatus


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
        "source_type": "apify_company_website_crawler",
        "company_name": "Acme Dental",
        "confidence": 0.7,
        "freshness_score": 1.0,
        "created_at": datetime.now(tz=UTC),
    }
    defaults.update(overrides)
    return ProviderNormalizedFact(**defaults)


def test_source_quality_returns_known_weight_and_default_for_unknown() -> None:
    assert source_quality("apify_company_website_crawler") == 1.00
    assert source_quality("tavily_search") == 0.55
    assert source_quality("some_never_seen_source") == 0.35


def test_fact_resolver_resolves_majority_value_and_flags_minority_as_contradicting() -> None:
    fetches_by_id = {1: _fetch(1, "apify"), 2: _fetch(2, "apify"), 3: _fetch(3, "tavily")}
    facts = [
        _fact(provider_fetch_id=1, phone="+15550100", source_type="apify_company_website_crawler"),
        _fact(provider_fetch_id=2, phone="+15550100", source_type="apify_company_website_crawler"),
        _fact(provider_fetch_id=3, phone="+19995550101", source_type="tavily_research"),
    ]

    canonical = FactResolver().resolve("phone", facts, fetches_by_id)

    assert canonical is not None
    assert canonical.value == "+15550100"
    assert canonical.status == "conflicting"
    assert len(canonical.contradicting_values) == 1
    assert canonical.contradicting_values[0].value == "+19995550101"
    assert canonical.contradicting_values[0].providers == ["tavily"]
    assert 0.0 < canonical.confidence <= 1.0


def test_fact_resolver_returns_none_when_no_facts_have_a_value() -> None:
    fetches_by_id = {1: _fetch(1, "apify")}
    facts = [_fact(provider_fetch_id=1, phone=None)]

    assert FactResolver().resolve("phone", facts, fetches_by_id) is None


def test_fact_resolver_marks_single_source_agreement_as_supported() -> None:
    fetches_by_id = {1: _fetch(1, "apify")}
    facts = [_fact(provider_fetch_id=1, phone="+15550100")]

    canonical = FactResolver().resolve("phone", facts, fetches_by_id)

    assert canonical is not None
    assert canonical.status == "supported"
    assert canonical.contradicting_values == []


def test_evidence_graph_builder_groups_facts_and_signals_and_computes_confidence_and_coverage() -> None:
    fetches_by_id = {1: _fetch(1, "apify")}
    facts = [
        _fact(
            provider_fetch_id=1,
            phone="+15550100",
            website_url="https://acmedental.example",
            website_domain="acmedental.example",
            category="Dentist",
        )
    ]
    signal = LeadSignal(
        workspace_id=1,
        lead_id=1,
        signal_type="no_website",
        signal_strength=0.8,
        evidence_text="No website found for this lead.",
        source_url=None,
        detected_at=datetime.now(tz=UTC),
    )

    graph = EvidenceGraphBuilder().build(
        lead_public_id="lead-1",
        facts=facts,
        fetches_by_id=fetches_by_id,
        signals=[signal],
    )

    group_names = {group.group for group in graph.groups}
    assert "business_identity" in group_names
    assert "digital_presence" in group_names
    assert "contactability" in group_names
    assert "pain_signals" in group_names
    assert 0.0 < graph.evidence_confidence <= 1.0
    assert 0.0 < graph.research_coverage <= 1.0


def test_evidence_graph_builder_returns_zero_scores_with_no_evidence() -> None:
    graph = EvidenceGraphBuilder().build(
        lead_public_id="lead-1", facts=[], fetches_by_id={}, signals=[]
    )

    assert graph.groups == []
    assert graph.evidence_confidence == 0.0
    assert graph.research_coverage == 0.0


def _resolved(graph: EvidenceGraph) -> dict[str, CanonicalFact]:
    return {fact.claim_type: fact for group in graph.groups for fact in group.facts}


def test_business_claims_detect_booking_whatsapp_ecommerce_and_contact_channels() -> None:
    fact = _fact(
        provider_fetch_id=1,
        website_url="https://acme.example/shop",
        phone="+15550100",
        facts_json={
            "evidence": {
                "url": "https://acme.example/contact",
                "snippet": "Book an appointment. Buy now. WhatsApp https://wa.me/15550100 info@acme.example",
            }
        },
    )
    graph = EvidenceGraphBuilder().build(
        lead_public_id="lead-1", facts=[fact], fetches_by_id={1: _fetch(1, "apify")}, signals=[]
    )
    resolved = _resolved(graph)

    assert resolved["online_booking"].value == "true"
    assert resolved["has_whatsapp"].value == "true"
    assert resolved["has_ecommerce"].value == "true"
    channels = json.loads(resolved["contact_channels"].value)
    assert {"phone", "email", "whatsapp", "contact_form", "online_booking"} <= set(channels)


def test_branch_count_prefers_official_agreement_and_preserves_contradiction_sources() -> None:
    facts = [
        _fact(provider_fetch_id=1, facts_json={"branch_count": 4}),
        _fact(provider_fetch_id=2, source_type="maps_place", facts_json={"location_count": 4}),
        _fact(provider_fetch_id=3, source_type="tavily_research", facts_json={"branch_count": 3}),
    ]
    graph = EvidenceGraphBuilder().build(
        lead_public_id="lead-1",
        facts=facts,
        fetches_by_id={1: _fetch(1, "apify"), 2: _fetch(2, "serpapi"), 3: _fetch(3, "tavily")},
        signals=[],
    )
    branch_count = _resolved(graph)["branch_count"]

    assert branch_count.value == "4"
    assert branch_count.status == "conflicting"
    assert branch_count.contradicting_values[0].value == "3"
    assert branch_count.contradicting_values[0].sources[0].provider == "tavily"


def test_services_are_case_insensitively_deduplicated_across_sources() -> None:
    facts = [
        _fact(provider_fetch_id=1, facts_json={"services": ["Teeth Whitening", "Implants"]}),
        _fact(provider_fetch_id=2, facts_json={"services": ["teeth whitening", "Emergency Care"]}),
    ]
    graph = EvidenceGraphBuilder().build(
        lead_public_id="lead-1",
        facts=facts,
        fetches_by_id={1: _fetch(1, "apify"), 2: _fetch(2, "tavily")},
        signals=[],
    )

    assert json.loads(_resolved(graph)["services"].value) == [
        "Emergency Care",
        "Implants",
        "Teeth Whitening",
    ]


def test_social_hiring_reviews_and_digital_maturity_are_deterministic() -> None:
    fact = _fact(
        provider_fetch_id=1,
        website_url="https://acme.example",
        review_count=30,
        facts_json={
            "mobile_responsive": True,
            "online_booking": True,
            "has_ecommerce": True,
            "has_whatsapp": True,
            "social_links": ["https://instagram.com/acme", "https://linkedin.com/company/acme"],
            "services": ["Consulting"],
            "open_roles": ["Designer", "Engineer"],
            "reviews": [
                "Great team but slow response",
                "Excellent work, slow response",
                "Friendly and professional",
            ],
        },
    )
    graph = EvidenceGraphBuilder().build(
        lead_public_id="lead-1", facts=[fact], fetches_by_id={1: _fetch(1, "apify")}, signals=[]
    )
    resolved = _resolved(graph)

    assert json.loads(resolved["social_presence"].value) == {"instagram": True, "linkedin": True}
    assert json.loads(resolved["hiring_signal"].value) == {"active": True, "roles_count": 2}
    assert resolved["review_sentiment"].value == "positive"
    pain = json.loads(resolved["recurring_review_pain_points"].value)
    assert pain[0]["category"] == "slow response"
    maturity = json.loads(resolved["digital_maturity"].value)
    assert maturity["score"] == 100
    assert maturity["band"] == "high"
    assert maturity["components"] == {
        "contact_channels": 12,
        "ecommerce": 15,
        "mobile_responsive": 10,
        "official_website": 20,
        "online_booking": 15,
        "review_volume": 5,
        "social_presence": 10,
        "structured_services": 5,
        "whatsapp": 10,
    }


def test_review_claims_remain_unknown_without_sufficient_review_text() -> None:
    graph = EvidenceGraphBuilder().build(
        lead_public_id="lead-1",
        facts=[_fact(provider_fetch_id=1, facts_json={"reviews": ["Great"]})],
        fetches_by_id={1: _fetch(1, "apify")},
        signals=[],
    )

    assert _resolved(graph)["review_sentiment"].status == "unknown"
    assert _resolved(graph)["recurring_review_pain_points"].status == "unknown"


def test_source_quality_and_freshness_reduce_projected_claim_confidence() -> None:
    fresh = _fact(provider_fetch_id=1, facts_json={"online_booking": True}, freshness_score=1.0)
    stale = _fact(
        provider_fetch_id=2,
        source_type="tavily_search",
        facts_json={"online_booking": True},
        freshness_score=0.2,
    )
    resolver = FactResolver()
    projector = BusinessIntelligenceProjector()
    fresh_fact = resolver.resolve_observations(
        "online_booking", projector.project([fresh])["online_booking"], {1: _fetch(1, "apify")}
    )
    stale_fact = resolver.resolve_observations(
        "online_booking", projector.project([stale])["online_booking"], {2: _fetch(2, "tavily")}
    )

    assert fresh_fact is not None and stale_fact is not None
    assert fresh_fact.confidence > stale_fact.confidence
