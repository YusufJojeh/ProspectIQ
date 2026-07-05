from __future__ import annotations

import os

import pytest


@pytest.mark.skipif(
    os.getenv("TAVILY_LIVE_E2E") != "1",
    reason="Set TAVILY_LIVE_E2E=1 and TAVILY_API_KEY to run the live Tavily smoke test.",
)
def test_live_tavily_search_smoke() -> None:
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        pytest.skip("TAVILY_API_KEY is required for the live Tavily smoke test.")

    try:
        from tavily import TavilyClient  # type: ignore[import-untyped]
    except ImportError:
        pytest.skip("tavily-python is not installed.")

    max_results = max(1, min(int(os.getenv("TAVILY_LIVE_MAX_CALLS", "3")), 3))
    client = TavilyClient(api_key=api_key)
    response = client.search(
        query="official OpenAI API documentation",
        search_depth=os.getenv("TAVILY_SEARCH_DEPTH", "basic"),
        max_results=max_results,
        include_answer=False,
    )

    assert isinstance(response, dict)
    results = response.get("results")
    assert isinstance(results, list)
    assert results
    for result in results:
        assert isinstance(result, dict)
        assert isinstance(result.get("url"), str)
        assert isinstance(result.get("title"), str)
        content = result.get("content")
        if content is not None:
            assert isinstance(content, str)
