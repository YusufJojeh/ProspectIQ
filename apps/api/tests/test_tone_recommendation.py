from __future__ import annotations

from app.modules.ai_analysis.adapters import FallbackAnalysisBuilder
from app.modules.ai_analysis.schemas import LeadAnalysisResult
from app.modules.ai_analysis.validator import LLMOutputValidator
from app.shared.dto.lead_facts import NormalizedLeadFacts
from tests.test_workspace_e2e import (
    _build_session_factory,
    _login,
    _override_client,
    _seed_workspace,
)


def _make_facts(**kwargs) -> NormalizedLeadFacts:
    defaults = dict(
        company_name="Test Co",
        category="Dentist",
        city="Istanbul",
        website_url="https://test.example",
        website_domain="test.example",
        review_count=20,
        rating=4.5,
        data_completeness=0.8,
        data_confidence=0.8,
        has_website=True,
        visibility_confidence=0.5,
        visibility_source="web_search",
    )
    defaults.update(kwargs)
    return NormalizedLeadFacts(**defaults)


def test_fallback_builder_returns_consultative_for_high_band() -> None:
    builder = FallbackAnalysisBuilder()
    facts = _make_facts(has_website=True, review_count=30)

    from app.modules.ai_analysis.schemas import LeadScoreContext
    from app.modules.ai_analysis.prompt_builder import PromptBuilder

    input_payload = PromptBuilder().build_input_payload(
        facts,
        score_context=LeadScoreContext(total_score=85, band="high", qualified=True),
        allowed_service_catalog=["SEO", "PPC"],
    )
    result_dict = builder.analyze(input_payload)

    assert result_dict.get("recommended_tone") == "consultative"


def test_fallback_builder_returns_friendly_for_medium_band_low_reviews() -> None:
    builder = FallbackAnalysisBuilder()
    facts = _make_facts(has_website=True, review_count=8)

    from app.modules.ai_analysis.schemas import LeadScoreContext
    from app.modules.ai_analysis.prompt_builder import PromptBuilder

    input_payload = PromptBuilder().build_input_payload(
        facts,
        score_context=LeadScoreContext(total_score=60, band="medium", qualified=True),
        allowed_service_catalog=["SEO"],
    )
    result_dict = builder.analyze(input_payload)

    assert result_dict.get("recommended_tone") == "friendly"


def test_fallback_builder_returns_short_pitch_when_no_website() -> None:
    builder = FallbackAnalysisBuilder()
    facts = _make_facts(has_website=False, website_url=None, official_website_found=False, review_count=5)

    from app.modules.ai_analysis.prompt_builder import PromptBuilder

    input_payload = PromptBuilder().build_input_payload(
        facts,
        allowed_service_catalog=["SEO"],
    )
    result_dict = builder.analyze(input_payload)

    assert result_dict.get("recommended_tone") == "short_pitch"


def test_validator_strips_invalid_tone_value() -> None:
    validator = LLMOutputValidator()
    payload = {
        "summary": "A good lead",
        "weaknesses": [],
        "opportunities": [],
        "recommended_services": ["SEO"],
        "outreach_subject": "Hello",
        "outreach_message": "Hi there",
        "confidence": 0.7,
        "recommended_tone": "aggressive",
    }
    result = validator.validate(payload)
    assert result.recommended_tone is None


def test_analysis_snapshot_response_includes_recommended_tone() -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        response = client.post(
            f"/api/v1/ai-analysis/leads/{seed.lead_public_id}/generate",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    analysis = response.json().get("analysis", {})
    assert "recommended_tone" in analysis
    assert analysis["recommended_tone"] in (None, "formal", "friendly", "consultative", "short_pitch")
