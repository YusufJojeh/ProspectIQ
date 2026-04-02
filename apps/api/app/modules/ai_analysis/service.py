from app.core.errors import FeatureNotReadyError
from app.modules.ai_analysis.schemas import LeadAnalysisResult
from app.shared.dto.lead_facts import NormalizedLeadFacts


class AIAnalysisService:
    def analyze(self, facts: NormalizedLeadFacts) -> LeadAnalysisResult:
        raise FeatureNotReadyError(
            f"AI analysis is not configured yet for lead '{facts.company_name}'."
        )
