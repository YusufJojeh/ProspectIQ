from __future__ import annotations

import pytest

from app.core.config import clear_settings_cache
from app.modules.search_jobs.prompt_parser import SearchPromptParser


@pytest.mark.asyncio
async def test_search_prompt_parser_uses_local_fallback_without_openai(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Empty value overrides any key sourced from .env, forcing the local parser
    monkeypatch.setenv("OPENAI_API_KEY", "")
    clear_settings_cache()

    parsed = await SearchPromptParser().parse(
        "Find dentists in Dubai with 4+ stars and at least 50 reviews without website"
    )

    assert parsed.business_type == "dentists"
    assert parsed.city == "Dubai"
    assert parsed.max_results == 25
    assert parsed.min_rating == 4
    assert parsed.min_reviews == 50
    assert parsed.website_preference == "must_be_missing"

    clear_settings_cache()


@pytest.mark.asyncio
async def test_search_prompt_parser_uses_local_fallback_for_arabic_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Empty value overrides any key sourced from .env, forcing the local parser
    monkeypatch.setenv("OPENAI_API_KEY", "")
    clear_settings_cache()

    parsed = await SearchPromptParser().parse(
        "\u0627\u0628\u062d\u062b \u0639\u0646 "
        "\u0635\u0627\u0644\u0648\u0646\u0627\u062a \u062a\u062c\u0645\u064a\u0644 "
        "\u0641\u064a \u062c\u062f\u0629 "
        "\u0628\u062f\u0648\u0646 \u0645\u0648\u0642\u0639 "
        "\u0628\u062a\u0642\u064a\u064a\u0645 4 "
        "\u0646\u062c\u0648\u0645 \u0623\u0648 \u0623\u0643\u062b\u0631 "
        "\u064850 \u0645\u0631\u0627\u062c\u0639\u0629 "
        "\u0639\u0644\u0649 \u0627\u0644\u0623\u0642\u0644"
    )

    assert parsed.business_type == "\u0635\u0627\u0644\u0648\u0646\u0627\u062a \u062a\u062c\u0645\u064a\u0644"
    assert parsed.city == "\u062c\u062f\u0629"
    assert parsed.min_rating == 4
    assert parsed.min_reviews == 50
    assert parsed.website_preference == "must_be_missing"

    clear_settings_cache()


@pytest.mark.asyncio
async def test_search_prompt_parser_arabic_review_range_and_min_rating(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Empty value overrides any key sourced from .env, forcing the local parser
    monkeypatch.setenv("OPENAI_API_KEY", "")
    clear_settings_cache()

    # "Find fitness centers in Riyadh with a review count between 20 and 150
    #  and a rating higher than 4."
    parsed = await SearchPromptParser().parse(
        "\u0627\u0628\u062d\u062b \u0639\u0646 "
        "\u0645\u0631\u0627\u0643\u0632 \u0644\u064a\u0627\u0642\u0629 "
        "\u0628\u062f\u0646\u064a\u0629 "
        "\u0641\u064a \u0627\u0644\u0631\u064a\u0627\u0636 "
        "\u0628\u0639\u062f\u062f \u0645\u0631\u0627\u062c\u0639\u0627\u062a "
        "\u0628\u064a\u0646 20 \u0648150 "
        "\u0648\u062a\u0642\u064a\u064a\u0645 \u0623\u0639\u0644\u0649 "
        "\u0645\u0646 4."
    )

    assert parsed.business_type == (
        "\u0645\u0631\u0627\u0643\u0632 \u0644\u064a\u0627\u0642\u0629 \u0628\u062f\u0646\u064a\u0629"
    )
    assert parsed.city == "\u0627\u0644\u0631\u064a\u0627\u0636"
    assert parsed.min_reviews == 20
    assert parsed.max_reviews == 150
    assert parsed.min_rating == 4

    clear_settings_cache()
