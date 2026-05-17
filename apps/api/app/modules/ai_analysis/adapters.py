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
            "summary, weaknesses, opportunities, recommended_services, outreach_subject, outreach_message, confidence, recommended_tone",
            "weaknesses/opportunities/recommended_services must be arrays of strings.",
            "confidence must be between 0 and 1.",
            "recommended_tone must be one of: formal, friendly, consultative, short_pitch (or omit if unknown).",
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

        score = payload.deterministic_score
        band = score.band if score else None
        has_website = payload.place_enrichment.official_website_found
        review_count = business.review_count

        if band == "high":
            recommended_tone = "consultative"
        elif band == "medium" and review_count < 15:
            recommended_tone = "friendly"
        elif not has_website:
            recommended_tone = "short_pitch"
        else:
            recommended_tone = "formal"

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
            "recommended_tone": recommended_tone,
        }
