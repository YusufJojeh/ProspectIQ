from app.modules.ai_analysis.schemas import LeadAnalysisResult


class LLMOutputValidator:
    def validate(self, payload: dict[str, object]) -> LeadAnalysisResult:
        return LeadAnalysisResult.model_validate(payload)

