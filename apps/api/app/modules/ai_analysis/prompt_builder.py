from app.shared.dto.lead_facts import NormalizedLeadFacts


class PromptBuilder:
    def build(self, facts: NormalizedLeadFacts) -> str:
        return (
            "Analyze only the documented facts.\n"
            f"Company: {facts.company_name}\n"
            f"City: {facts.city or 'Unknown'}\n"
            f"Website: {facts.website_url or 'Missing'}\n"
            f"Reviews: {facts.review_count}\n"
            f"Average rating: {facts.rating or 'Unknown'}\n"
            f"Website domain: {facts.website_domain or 'Unknown'}\n"
            f"Data completeness: {facts.data_completeness}\n"
            f"Data confidence: {facts.data_confidence}\n"
        )
