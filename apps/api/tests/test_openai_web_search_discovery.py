from __future__ import annotations

import pytest

from app.modules.provider_openai.web_search_discovery import OpenAIWebSearchDiscovery


def test_parse_businesses_handles_code_fence_and_prose() -> None:
    raw = (
        "Here are the results I found:\n"
        "```json\n"
        '{"businesses": [{"company_name": "Gym A"}, {"company_name": "Gym B"}]}\n'
        "```\n"
        "Let me know if you need more."
    )
    parsed = OpenAIWebSearchDiscovery._parse_businesses(raw)
    assert [b["company_name"] for b in parsed] == ["Gym A", "Gym B"]


def test_parse_businesses_returns_empty_for_garbage() -> None:
    assert OpenAIWebSearchDiscovery._parse_businesses("no json here") == []
    assert OpenAIWebSearchDiscovery._parse_businesses("") == []


def test_extract_output_text_from_responses_payload() -> None:
    payload = {
        "output": [
            {"type": "reasoning", "content": []},
            {
                "type": "message",
                "content": [
                    {"type": "output_text", "text": '{"businesses": []}'},
                ],
            },
        ]
    }
    assert OpenAIWebSearchDiscovery._extract_output_text(payload) == '{"businesses": []}'


def test_to_candidate_normalizes_fields_and_builds_identities() -> None:
    candidate = OpenAIWebSearchDiscovery._to_candidate(
        {
            "company_name": "  Q _FIT  ستوديو  ",
            "address": "King Fahd Rd, Riyadh",
            "city": None,
            "phone": "+966 59 546 6466",
            "website_url": "https://www.qfitksa.com/home",
            "rating": 6.0,  # out of range -> clamped to 5.0
            "review_count": "16",
            "category": "Gym",
        },
        default_city="الرياض",
    )
    assert candidate is not None
    assert candidate.company_name == "Q _FIT ستوديو"
    assert candidate.city == "الرياض"  # falls back to default
    assert candidate.phone == "+966595466466"
    assert candidate.website_domain == "qfitksa.com"
    assert candidate.rating == 5.0
    assert candidate.review_count == 16
    # at least a fingerprint + domain + phone identity
    types = {i.identity_type for i in candidate.identities}
    assert "website_domain" in types
    assert "phone" in types
    assert "fingerprint" in types


def test_to_candidate_rejects_rows_without_company_name() -> None:
    assert OpenAIWebSearchDiscovery._to_candidate({"company_name": ""}, default_city="X") is None


def test_discover_uses_stubbed_web_search(monkeypatch: pytest.MonkeyPatch) -> None:
    discovery = OpenAIWebSearchDiscovery()
    monkeypatch.setattr(discovery, "is_available", lambda: True)
    monkeypatch.setattr(
        discovery,
        "_call_responses_api",
        lambda settings, prompt: (
            '{"businesses": ['
            '{"company_name": "Riyadh Fit", "city": "الرياض", "rating": 4.5, '
            '"review_count": 80, "website_url": "https://riyadhfit.sa"}]}'
        ),
    )

    candidates = discovery.discover(
        business_type="مراكز لياقة بدنية",
        city="الرياض",
        region=None,
        max_results=25,
        min_rating=4.0,
        max_rating=None,
        min_reviews=20,
        max_reviews=150,
    )

    assert len(candidates) == 1
    assert candidates[0].company_name == "Riyadh Fit"
    assert candidates[0].rating == 4.5
    assert candidates[0].review_count == 80
    assert candidates[0].website_domain == "riyadhfit.sa"


def test_discover_returns_empty_when_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    discovery = OpenAIWebSearchDiscovery()
    monkeypatch.setattr(discovery, "is_available", lambda: False)
    result = discovery.discover(
        business_type="x",
        city="y",
        region=None,
        max_results=25,
        min_rating=None,
        max_rating=None,
        min_reviews=None,
        max_reviews=None,
    )
    assert result == []
