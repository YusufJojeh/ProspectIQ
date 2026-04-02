from app.core.errors import FeatureNotReadyError
from app.shared.dto.lead_facts import NormalizedLeadFacts


class DeterministicLLMAdapter:
    def analyze(self, facts: NormalizedLeadFacts) -> dict[str, object]:
        raise FeatureNotReadyError(
            f"Deterministic AI adapter is disabled in the foundation phase for lead '{facts.company_name}'."
        )
