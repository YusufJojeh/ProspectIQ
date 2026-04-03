from app.modules.ai_analysis.schemas import LeadScoreContext
from app.shared.dto.lead_facts import NormalizedLeadFacts


class DeterministicLLMAdapter:
    def analyze(
        self,
        facts: NormalizedLeadFacts,
        *,
        score_context: LeadScoreContext | None = None,
    ) -> dict[str, object]:
        summary_parts = [
            f"{facts.company_name} is listed in {facts.city or 'the current target market'}."
        ]
        if facts.category:
            summary_parts.append(f"The primary category captured is {facts.category}.")
        if facts.rating is not None:
            summary_parts.append(
                f"It currently shows {facts.review_count} Google reviews with a {facts.rating:.1f} average rating."
            )
        else:
            summary_parts.append(f"It currently shows {facts.review_count} Google reviews.")
        if facts.has_website and facts.website_domain:
            summary_parts.append(f"A website is present at {facts.website_domain}.")
        else:
            summary_parts.append("No verified website was found in the stored evidence.")
        summary_parts.append(
            f"Dataset completeness is {self._percent(facts.data_completeness)} and confidence is {self._percent(facts.data_confidence)}."
        )
        if score_context and score_context.total_score is not None and score_context.band:
            summary_parts.append(
                f"The latest deterministic lead score is {score_context.total_score:.0f}/100 in the {score_context.band.replace('_', ' ')} band."
            )

        weaknesses: list[str] = []
        opportunities: list[str] = []
        services: list[str] = []

        if not facts.has_website:
            weaknesses.append("No verified website is attached to the lead record.")
            opportunities.append(
                "A focused website or landing page would give local search and paid traffic a clear conversion destination."
            )
            services.append("Website build and conversion landing pages")
        if facts.visibility_confidence is None or facts.visibility_confidence < 0.55:
            weaknesses.append("Search visibility evidence is weak or missing.")
            opportunities.append(
                "Local SEO and Google Business Profile work could improve discoverability."
            )
            services.append("Local SEO and Google Business Profile optimization")
        if facts.review_count < 15:
            weaknesses.append(
                f"Review volume is currently {facts.review_count}, which limits visible trust signals."
            )
            opportunities.append("A review-generation workflow could strengthen reputation proof.")
            services.append("Review generation and reputation management")
        if facts.rating is not None and facts.rating < 4.3:
            weaknesses.append(
                f"Average rating is {facts.rating:.1f}, leaving room for stronger review sentiment."
            )
            opportunities.append(
                "Reputation cleanup and follow-up systems could improve the average rating."
            )
            services.append("Reputation recovery and follow-up automation")
        if facts.has_website:
            opportunities.append(
                "The existing website can be tightened around lead capture, calls to action, and tracking."
            )
            services.append("Conversion optimization and analytics instrumentation")
        if facts.data_completeness < 0.7:
            weaknesses.append(
                f"Data completeness is only {self._percent(facts.data_completeness)}, so enrichment should continue before heavy outreach."
            )
        if facts.rating is not None and facts.rating >= 4.5 and facts.review_count >= 20:
            opportunities.append(
                "Strong customer sentiment can be reused as social proof in acquisition campaigns."
            )
            services.append("Case-study and testimonial repackaging")

        if not weaknesses:
            weaknesses.append(
                "The stored facts do not show a major operational gap, so outreach should emphasize growth upside."
            )
        if not opportunities:
            opportunities.append(
                "Run a short audit of local acquisition channels before proposing a larger engagement."
            )
        recommended_services = self._dedupe(services)[:3]
        if not recommended_services:
            recommended_services = ["Local lead capture audit"]

        outreach_subject = self._build_subject(facts)
        outreach_message = self._build_message(
            facts,
            opportunities=opportunities,
            recommended_services=recommended_services,
        )
        confidence = round(
            min(0.95, max(0.35, (facts.data_confidence * 0.65) + (facts.data_completeness * 0.35))),
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

    def _build_subject(self, facts: NormalizedLeadFacts) -> str:
        if not facts.has_website:
            return f"Quick idea to strengthen {facts.company_name}'s web presence"
        return f"Idea to improve {facts.company_name}'s local lead capture"

    def _build_message(
        self,
        facts: NormalizedLeadFacts,
        *,
        opportunities: list[str],
        recommended_services: list[str],
    ) -> str:
        rating_text = (
            f"{facts.review_count} Google reviews at {facts.rating:.1f} stars"
            if facts.rating is not None
            else f"{facts.review_count} Google reviews"
        )
        website_text = (
            f"I also found a website at {facts.website_domain}."
            if facts.has_website and facts.website_domain
            else "I did not find a verified website in the public evidence."
        )
        service_text = ", ".join(recommended_services[:2])
        opportunity_text = opportunities[0]
        return (
            f"Hi {facts.company_name} team,\n\n"
            f"I reviewed your current public presence in {facts.city or 'your market'} and found {rating_text}. "
            f"{website_text}\n\n"
            f"The clearest opportunity from the stored evidence is: {opportunity_text} "
            f"If helpful, my agency can share a short plan focused on {service_text}."
        )

    def _dedupe(self, values: list[str]) -> list[str]:
        deduped: list[str] = []
        for value in values:
            if value not in deduped:
                deduped.append(value)
        return deduped

    def _percent(self, value: float | None) -> str:
        if value is None:
            return "unknown"
        return f"{round(value * 100)}%"
