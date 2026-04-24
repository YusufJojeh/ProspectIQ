from __future__ import annotations

import json
from typing import Protocol

import httpx

from app.modules.ai_analysis.schemas import LeadAnalysisInput


class LLMClient(Protocol):
    def analyze(self, payload: LeadAnalysisInput) -> dict[str, object]: ...


def _coerce_json_object(raw_content: str) -> dict[str, object]:
    stripped = raw_content.strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("LLM response did not contain a JSON object.") from None
        parsed = json.loads(stripped[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("LLM response JSON was not an object.")
    return parsed


def _build_llm_prompt(payload: LeadAnalysisInput) -> str:
    score = payload.deterministic_score
    score_block = (
        {
            "total_score": score.total_score,
            "band": score.band,
            "qualified": score.qualified,
            "reasons": score.reasons,
        }
        if score
        else None
    )
    return "\n".join(
        [
            payload.prompt_instructions
            or "Use only the supplied evidence. Do not invent facts or claims.",
            "Return a single JSON object with keys:",
            "summary, weaknesses, opportunities, recommended_services, outreach_subject, outreach_message, confidence",
            "weaknesses/opportunities/recommended_services must be arrays of strings.",
            "confidence must be between 0 and 1.",
            "Input:",
            json.dumps(
                {
                    "local_business": payload.local_business.model_dump(mode="json"),
                    "place_enrichment": payload.place_enrichment.model_dump(mode="json"),
                    "web_visibility": payload.web_visibility.model_dump(mode="json"),
                    "deterministic_score": score_block,
                    "allowed_service_catalog": payload.allowed_service_catalog,
                },
                ensure_ascii=True,
                sort_keys=True,
            ),
        ]
    )


class DeterministicLLMAdapter:
    def analyze(self, payload: LeadAnalysisInput) -> dict[str, object]:
        business = payload.local_business
        place = payload.place_enrichment
        visibility = payload.web_visibility
        score = payload.deterministic_score

        summary_parts = [
            f"{business.company_name} is listed in {business.city or 'the target market'}.",
            f"Public evidence shows {business.review_count} Google reviews"
            + (f" with a {business.rating:.1f} rating." if business.rating is not None else "."),
        ]
        if place.official_website_found and business.website_domain:
            summary_parts.append(
                f"An official website is present at {business.website_domain} via {place.official_website_source or 'stored evidence'}."
            )
        else:
            summary_parts.append("No official website was confirmed in the normalized evidence.")
        summary_parts.append(
            f"Data completeness is {self._percent(business.data_completeness)} and evidence confidence is {self._percent(business.data_confidence)}."
        )
        if score and score.total_score is not None:
            summary_parts.append(
                f"The latest deterministic score is {score.total_score:.0f}/100 in the {score.band or 'unknown'} band."
            )

        weaknesses: list[str] = []
        opportunities: list[str] = []

        if not place.official_website_found:
            weaknesses.append("No official website was verified from maps or web-search evidence.")
            opportunities.append(
                "A website or campaign landing page would give search traffic a clear conversion destination."
            )
        elif not place.website_domain_matches_brand:
            weaknesses.append(
                "The detected website domain does not strongly match the business brand."
            )
            opportunities.append(
                "Brand/domain alignment and trust presentation should be tightened before scaling outreach."
            )

        if business.review_count < 15:
            weaknesses.append(
                f"Review volume is only {business.review_count}, which weakens visible local trust."
            )
            opportunities.append(
                "A review-generation workflow could strengthen local proof quickly."
            )

        discoverability = visibility.official_site_discoverability or 0.0
        if discoverability < 0.5:
            weaknesses.append(
                "Official-site discoverability is weak relative to directories and local listings."
            )
            opportunities.append(
                "Local SEO and branded-search cleanup could improve official-site visibility."
            )

        if business.data_completeness < 0.7 or not business.hours_present:
            weaknesses.append(
                "The digital footprint is incomplete across the stored local-business evidence."
            )
            opportunities.append(
                "Profile enrichment and listing cleanup would improve conversion readiness."
            )

        if business.rating is not None and business.rating >= 4.5 and business.review_count >= 20:
            opportunities.append(
                "Strong sentiment can be reused as testimonial and case-study proof in campaigns."
            )

        if not weaknesses:
            weaknesses.append(
                "The stored evidence shows no major structural gap, so messaging should focus on growth upside."
            )
        if not opportunities:
            opportunities.append(
                "A short evidence-led audit would clarify the next most valuable service to pitch."
            )

        recommended_services = self._recommend_services(payload, weaknesses, opportunities)
        outreach_subject = self._build_subject(payload, recommended_services)
        outreach_message = self._build_message(payload, opportunities, recommended_services)
        confidence = round(
            min(
                0.95,
                max(
                    0.35,
                    (business.data_confidence * 0.45)
                    + (business.data_completeness * 0.2)
                    + ((payload.web_visibility.official_site_discoverability or 0.0) * 0.15)
                    + (payload.place_enrichment.local_presence_signal * 0.2),
                ),
            ),
            2,
        )

        return {
            "summary": " ".join(summary_parts),
            "weaknesses": weaknesses[:4],
            "opportunities": opportunities[:4],
            "recommended_services": recommended_services,
            "outreach_subject": outreach_subject,
            "outreach_message": outreach_message,
            "confidence": confidence,
        }

    def _recommend_services(
        self,
        payload: LeadAnalysisInput,
        weaknesses: list[str],
        opportunities: list[str],
    ) -> list[str]:
        catalog = payload.allowed_service_catalog
        ranked: list[str] = []

        def add_if_present(service_name: str) -> None:
            if service_name in catalog and service_name not in ranked:
                ranked.append(service_name)

        weakness_blob = " ".join(weaknesses).casefold()
        opportunity_blob = " ".join(opportunities).casefold()

        if "website" in weakness_blob or "landing page" in opportunity_blob:
            add_if_present("Website Refresh")
            add_if_present("Conversion Landing Page Build")
        if "review" in weakness_blob or "review" in opportunity_blob:
            add_if_present("Review Generation and Reputation Management")
        if "seo" in opportunity_blob or "visibility" in weakness_blob:
            add_if_present("Local SEO Sprint")
            add_if_present("Google Business Profile Optimization")
        if "tracking" in opportunity_blob or "conversion" in opportunity_blob:
            add_if_present("Call Tracking and Analytics Setup")
        if not ranked and catalog:
            ranked.extend(list(catalog[:3]))
        return ranked[:3]

    def _build_subject(self, payload: LeadAnalysisInput, recommended_services: list[str]) -> str:
        business = payload.local_business
        if not payload.place_enrichment.official_website_found:
            return f"Quick idea to strengthen {business.company_name}'s online presence"
        if recommended_services:
            return f"{business.company_name}: one evidence-backed growth idea"
        return f"Short local visibility note for {business.company_name}"

    def _build_message(
        self,
        payload: LeadAnalysisInput,
        opportunities: list[str],
        recommended_services: list[str],
    ) -> str:
        business = payload.local_business
        place = payload.place_enrichment
        service_text = ", ".join(recommended_services[:2]) or "a short local acquisition audit"
        opportunity_text = opportunities[0]
        website_text = (
            f"We found an official site at {business.website_domain}."
            if place.official_website_found and business.website_domain
            else "We did not verify an official website from the stored public evidence."
        )
        return (
            f"Hi {business.company_name} team,\n\n"
            f"I reviewed the public evidence we captured for your business in {business.city or 'your market'}. "
            f"It currently shows {business.review_count} Google reviews"
            + (f" at {business.rating:.1f} stars. " if business.rating is not None else ". ")
            + f"{website_text}\n\n"
            f"The clearest opportunity from the normalized evidence is: {opportunity_text} "
            f"If useful, I can share a short plan focused on {service_text}."
        )

    def _percent(self, value: float | None) -> str:
        if value is None:
            return "unknown"
        return f"{round(value * 100)}%"


class OpenAILLMAdapter:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    def close(self) -> None:
        self._client.close()

    def __del__(self) -> None:
        self._client.close()

    def analyze(self, payload: LeadAnalysisInput) -> dict[str, object]:
        prompt = _build_llm_prompt(payload)
        response = self._client.post(
            f"{self.base_url}/chat/completions",
            json={
                "model": self.model,
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an evidence-first lead-analysis assistant. Return only JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
            },
        )
        response.raise_for_status()
        payload_json = response.json()
        content = (
            payload_json.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        if not isinstance(content, str) or not content.strip():
            raise ValueError("OpenAI response did not include message content.")
        return _coerce_json_object(content)


class OllamaLLMAdapter:
    def __init__(self, *, base_url: str, model: str) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            timeout=httpx.Timeout(45.0, connect=10.0),
            headers={"Content-Type": "application/json"},
        )

    def close(self) -> None:
        self._client.close()

    def __del__(self) -> None:
        self._client.close()

    def analyze(self, payload: LeadAnalysisInput) -> dict[str, object]:
        response = self._client.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": _build_llm_prompt(payload),
                "stream": False,
                "format": "json",
            },
        )
        response.raise_for_status()
        payload_json = response.json()
        content = payload_json.get("response", "")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Ollama response did not include generated text.")
        return _coerce_json_object(content)


class FallbackAnalysisBuilder:
    def analyze(self, payload: LeadAnalysisInput) -> dict[str, object]:
        business = payload.local_business
        gaps: list[str] = []
        if not payload.place_enrichment.official_website_found:
            gaps.append("No official website was confirmed.")
        if business.review_count < 15:
            gaps.append(f"Review count is only {business.review_count}.")
        if (payload.web_visibility.official_site_discoverability or 0.0) < 0.5:
            gaps.append("Official-site discoverability is weak.")
        if not gaps:
            gaps.append(
                "The stored evidence suggests the business is reasonably complete but still worth auditing."
            )

        recommended_services = list(payload.allowed_service_catalog[:2]) or [
            "Local SEO Sprint",
            "Google Business Profile Optimization",
        ]
        return {
            "summary": (
                f"{business.company_name} was analyzed from stored SerpAPI-derived facts only. "
                f"The fallback path was used because the primary AI adapter did not return a valid payload."
            ),
            "weaknesses": gaps[:4],
            "opportunities": [
                "Run a short evidence-led audit before proposing a broader engagement."
            ],
            "recommended_services": recommended_services[:3],
            "outreach_subject": f"Evidence-backed growth ideas for {business.company_name}",
            "outreach_message": (
                f"Hi {business.company_name} team,\n\n"
                "We reviewed your public search presence and identified a few evidence-backed opportunities. "
                "If useful, we can share a concise audit and proposed next steps."
            ),
            "confidence": max(0.35, round(business.data_confidence, 2)),
        }
