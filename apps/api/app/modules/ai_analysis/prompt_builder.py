from __future__ import annotations

from app.modules.ai_analysis.schemas import (
    LeadAnalysisInput,
    LeadScoreContext,
    LocalBusinessFactsInput,
    PlaceEnrichmentSummary,
    WebVisibilitySummary,
)
from app.shared.dto.lead_facts import NormalizedLeadFacts


class PromptBuilder:
    def build_input_payload(
        self,
        facts: NormalizedLeadFacts,
        *,
        score_context: LeadScoreContext | None = None,
        allowed_service_catalog: list[str],
    ) -> LeadAnalysisInput:
        return LeadAnalysisInput(
            local_business=LocalBusinessFactsInput(
                company_name=facts.company_name,
                category=facts.category,
                city=facts.city,
                address=facts.address,
                phone=facts.phone,
                website_url=facts.website_url,
                website_domain=facts.website_domain,
                rating=facts.rating,
                review_count=facts.review_count,
                data_completeness=facts.data_completeness,
                data_confidence=facts.data_confidence,
                phone_present=facts.phone_present,
                address_present=facts.address_present,
                hours_present=facts.hours_present,
                category_clarity=facts.category_clarity,
            ),
            place_enrichment=PlaceEnrichmentSummary(
                maps_search_present=facts.maps_search_present,
                maps_place_present=facts.maps_place_present,
                official_website_found=facts.official_website_found,
                official_website_source=facts.official_website_source,
                website_domain_matches_brand=facts.website_domain_matches_brand,
                local_presence_signal=facts.local_presence_signal,
            ),
            web_visibility=WebVisibilitySummary(
                web_search_present=facts.web_search_present,
                official_site_discoverability=facts.official_site_discoverability,
                official_site_position=facts.official_site_position,
                directory_results_before_official=facts.directory_results_before_official,
                directory_dominance=facts.directory_dominance,
                knowledge_graph_present=facts.knowledge_graph_present,
                visibility_source=facts.visibility_source,
            ),
            deterministic_score=score_context,
            allowed_service_catalog=allowed_service_catalog,
        )

    def build_prompt(self, payload: LeadAnalysisInput) -> str:
        business = payload.local_business
        visibility = payload.web_visibility
        score = payload.deterministic_score
        return (
            "Use only the documented SerpAPI-derived evidence below. "
            "Do not invent facts and do not overwrite source-of-truth lead data.\n"
            f"Company: {business.company_name}\n"
            f"Category: {business.category or 'Unknown'}\n"
            f"City: {business.city or 'Unknown'}\n"
            f"Website: {business.website_url or 'Missing'}\n"
            f"Reviews: {business.review_count}\n"
            f"Rating: {business.rating if business.rating is not None else 'Unknown'}\n"
            f"Completeness: {business.data_completeness}\n"
            f"Confidence: {business.data_confidence}\n"
            f"Official site discoverability: {visibility.official_site_discoverability}\n"
            f"Directory dominance: {visibility.directory_dominance}\n"
            f"Allowed services: {', '.join(payload.allowed_service_catalog)}\n"
            + (
                (
                    f"Deterministic score: {score.total_score}\n"
                    f"Band: {score.band}\n"
                    f"Qualified: {score.qualified}\n"
                    f"Top score reasons: {' | '.join(score.reasons)}\n"
                )
                if score
                else ""
            )
        )
