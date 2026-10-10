from __future__ import annotations

from app.core.config import get_settings
from app.modules.research.schemas import ResearchDepth, ResearchPlan, ResearchStep

_MAX_STEPS_SETTING = {
    "quick": "research_max_steps_quick",
    "standard": "research_max_steps_standard",
    "deep": "research_max_steps_deep",
}


class ResearchPlanner:
    """Decides which provider steps a research request may run.

    Depth controls scope, not just provider count:
      - quick: Tavily web search only -- fast, cheap, always available.
      - standard: adds an Apify crawl of the lead's own site (skipped by the
        orchestrator at run time if no website URL is known yet).
      - deep: adds a SerpAPI cross-check and, when the lead already has a
        Google Place identity, an Apify reviews crawl.

    `available_providers` excludes any provider whose runtime is "blocked"
    (unconfigured) -- unconfigured optional providers are simply excluded
    from the plan rather than causing a hard failure, matching how
    DISCOVERY_ENGINE_LIST already treats an unconfigured Tavily.
    """

    def plan(
        self,
        *,
        depth: ResearchDepth,
        has_place_identity: bool,
        available_providers: set[str],
    ) -> ResearchPlan:
        candidates: list[ResearchStep] = [
            ResearchStep(
                provider="tavily", mode="web_search", reason="Baseline web discovery/research."
            ),
        ]

        if depth in {"standard", "deep"}:
            candidates.append(
                ResearchStep(
                    provider="apify",
                    mode="company_website_crawler",
                    reason="Deep-extract the lead's own official website.",
                )
            )

        if depth == "deep":
            candidates.append(
                ResearchStep(
                    provider="serpapi",
                    mode="web_search",
                    reason="Cross-check with Google-oriented signals.",
                )
            )
            if has_place_identity:
                candidates.append(
                    ResearchStep(
                        provider="apify",
                        mode="reviews_crawler",
                        reason="Pull reviews for sentiment/contradiction signals.",
                    )
                )

        available_steps = [step for step in candidates if step.provider in available_providers]
        settings = get_settings()
        max_steps = getattr(settings, _MAX_STEPS_SETTING[depth])
        return ResearchPlan(depth=depth, steps=available_steps[:max_steps])
