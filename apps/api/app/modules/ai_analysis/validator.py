from app.modules.ai_analysis.schemas import LeadAnalysisResult

_VALID_TONES = {"formal", "friendly", "consultative", "short_pitch"}


class LLMOutputValidator:
    def validate(self, payload: dict[str, object]) -> LeadAnalysisResult:
        tone = payload.get("recommended_tone")
        if isinstance(tone, str) and tone not in _VALID_TONES:
            payload = {**payload, "recommended_tone": None}
        return LeadAnalysisResult.model_validate(payload)
