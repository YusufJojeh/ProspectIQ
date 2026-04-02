from app.core.errors import FeatureNotReadyError
from app.modules.outreach.schemas import OutreachMessageResult
from app.shared.dto.lead_facts import NormalizedLeadFacts


class OutreachGenerationService:
    def __init__(self, analysis_service) -> None:
        self.analysis_service = analysis_service

    def generate(self, facts: NormalizedLeadFacts) -> OutreachMessageResult:
        raise FeatureNotReadyError(
            f"Outreach generation is not configured yet for lead '{facts.company_name}'."
        )
