from app.modules.scoring.schemas import ScoringThresholds, ScoringWeights
from app.modules.scoring.service import ScoringEngine
from app.shared.dto.lead_facts import NormalizedLeadFacts
from app.shared.enums.jobs import LeadScoreBand


def test_scoring_engine_prioritizes_missing_website_and_low_reviews() -> None:
    engine = ScoringEngine()
    weights = ScoringWeights()
    thresholds = ScoringThresholds(high_min=70, medium_min=55, low_min=35, confidence_min=0.2)

    result = engine.evaluate(
        NormalizedLeadFacts(
            company_name="Example Prospect",
            city="Istanbul",
            website_domain=None,
            review_count=8,
            rating=4.0,
            data_completeness=0.35,
            data_confidence=0.8,
            has_website=False,
            visibility_confidence=0.0,
            visibility_source="none",
        ),
        weights=weights,
        thresholds=thresholds,
    )

    assert result.qualified is True
    assert result.band in (LeadScoreBand.HIGH, LeadScoreBand.MEDIUM)
    assert result.total_score >= 55
    assert any(item.key == "website_presence" for item in result.breakdown)


def test_scoring_engine_disqualifies_low_confidence() -> None:
    engine = ScoringEngine()
    weights = ScoringWeights()
    thresholds = ScoringThresholds(confidence_min=0.7)

    result = engine.evaluate(
        NormalizedLeadFacts(
            company_name="Low Confidence",
            city="Istanbul",
            website_domain="example.com",
            review_count=50,
            rating=4.6,
            data_completeness=0.9,
            data_confidence=0.3,
            has_website=True,
        ),
        weights=weights,
        thresholds=thresholds,
    )

    assert result.qualified is False
    assert result.band == LeadScoreBand.NOT_QUALIFIED

