from app.modules.scoring.schemas import ScoringThresholds, ScoringWeights
from app.modules.scoring.service import ScoringEngine
from app.shared.dto.lead_facts import NormalizedLeadFacts
from app.shared.enums.jobs import LeadScoreBand


def _weights() -> ScoringWeights:
    return ScoringWeights(
        local_trust=0.25,
        website_presence=0.2,
        search_visibility=0.2,
        opportunity=0.2,
        data_confidence=0.15,
    )


def _thresholds() -> ScoringThresholds:
    return ScoringThresholds(high_min=72, medium_min=55, low_min=40, confidence_min=0.45)


def test_scoring_engine_rewards_trusted_business_with_auditable_presence() -> None:
    engine = ScoringEngine()
    result = engine.evaluate(
        NormalizedLeadFacts(
            company_name="Acme Dental",
            city="Istanbul",
            category="Dentist",
            review_count=84,
            rating=4.8,
            data_completeness=0.92,
            data_confidence=0.9,
            has_website=True,
            phone_present=True,
            address_present=True,
            hours_present=True,
            category_clarity=1.0,
            official_website_found=True,
            official_website_source="maps_place",
            website_domain="acmedental.com",
            website_domain_matches_brand=True,
            website_evidence_consistent=True,
            official_site_discoverability=0.9,
            directory_dominance=0.1,
            local_presence_signal=0.95,
            source_agreement=0.92,
            evidence_sources_count=3,
        ),
        weights=_weights(),
        thresholds=_thresholds(),
    )

    assert result.qualified is True
    assert result.band == LeadScoreBand.HIGH
    assert result.total_score >= 72
    assert any(item.key == "local_trust" and item.contribution > 18 for item in result.breakdown)


def test_scoring_engine_keeps_high_opportunity_lead_qualified_when_confidence_is_good() -> None:
    engine = ScoringEngine()
    result = engine.evaluate(
        NormalizedLeadFacts(
            company_name="North Clinic",
            city="Ankara",
            category="Clinic",
            review_count=8,
            rating=4.2,
            data_completeness=0.58,
            data_confidence=0.74,
            has_website=False,
            phone_present=True,
            address_present=True,
            hours_present=False,
            category_clarity=0.8,
            official_website_found=False,
            official_site_discoverability=0.2,
            directory_dominance=0.95,
            local_presence_signal=0.7,
            weak_website_signal=1.0,
            digital_footprint_gap=0.78,
            source_agreement=0.78,
            evidence_sources_count=2,
        ),
        weights=_weights(),
        thresholds=_thresholds(),
    )

    assert result.qualified is True
    assert result.band in {LeadScoreBand.LOW, LeadScoreBand.MEDIUM, LeadScoreBand.HIGH}
    assert any(item.key == "opportunity" and item.contribution >= 14 for item in result.breakdown)


def test_scoring_engine_disqualifies_low_confidence_even_when_business_signals_are_strong() -> None:
    engine = ScoringEngine()
    result = engine.evaluate(
        NormalizedLeadFacts(
            company_name="Signal Mismatch",
            city="Izmir",
            category="Lawyer",
            review_count=52,
            rating=4.7,
            data_completeness=0.9,
            data_confidence=0.25,
            has_website=True,
            phone_present=True,
            address_present=True,
            hours_present=True,
            category_clarity=1.0,
            official_website_found=True,
            official_website_source="maps_place",
            website_domain="brand-law.com",
            website_domain_matches_brand=True,
            website_evidence_consistent=False,
            official_site_discoverability=0.82,
            directory_dominance=0.15,
            local_presence_signal=0.9,
            source_agreement=0.2,
            evidence_sources_count=3,
        ),
        weights=_weights(),
        thresholds=_thresholds(),
    )

    assert result.qualified is False
    assert result.band == LeadScoreBand.NOT_QUALIFIED


def test_scoring_engine_penalizes_directory_heavy_visibility_even_when_a_website_exists() -> None:
    engine = ScoringEngine()
    result = engine.evaluate(
        NormalizedLeadFacts(
            company_name="Visibility Gap Dental",
            city="Bursa",
            category="Dentist",
            review_count=18,
            rating=4.1,
            data_completeness=0.72,
            data_confidence=0.71,
            has_website=True,
            phone_present=True,
            address_present=True,
            hours_present=False,
            category_clarity=0.9,
            official_website_found=True,
            official_website_source="web_search",
            website_domain="visibilitygapdental.com",
            website_domain_matches_brand=True,
            website_evidence_consistent=True,
            official_site_discoverability=0.42,
            directory_dominance=0.9,
            local_presence_signal=0.45,
            weak_website_signal=0.7,
            digital_footprint_gap=0.68,
            source_agreement=0.7,
            evidence_sources_count=2,
        ),
        weights=_weights(),
        thresholds=_thresholds(),
    )

    search_visibility = next(item for item in result.breakdown if item.key == "search_visibility")
    opportunity = next(item for item in result.breakdown if item.key == "opportunity")

    assert result.qualified is True
    assert search_visibility.contribution < 8
    assert opportunity.contribution > search_visibility.contribution


def test_scoring_config_requires_weight_sum_and_threshold_order() -> None:
    try:
        ScoringWeights(
            local_trust=0.3,
            website_presence=0.3,
            search_visibility=0.2,
            opportunity=0.2,
            data_confidence=0.2,
        )
    except ValueError as exc:
        assert "sum to 1.0" in str(exc)
    else:
        raise AssertionError("Expected invalid weight sum to fail validation.")

    try:
        ScoringThresholds(high_min=50, medium_min=60, low_min=40, confidence_min=0.45)
    except ValueError as exc:
        assert "high_min >= medium_min >= low_min" in str(exc)
    else:
        raise AssertionError("Expected threshold ordering validation to fail.")
