from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import NotFoundError, ServiceUnavailableError
from app.modules.ai_analysis.repository import AIAnalysisRepository
from app.modules.ai_analysis.schemas import LeadAnalysisResult
from app.modules.assistant.models import ChatSession
from app.modules.assistant.repository import ChatSessionRepository
from app.modules.assistant.schemas import AssistantMessageInput
from app.modules.leads.models import Lead
from app.modules.leads.repository import LeadsRepository
from app.shared.services.lead_intelligence import LeadIntelligenceService

logger = logging.getLogger(__name__)


class AssistantService:
    def __init__(self) -> None:
        self.leads_repository = LeadsRepository()
        self.lead_intelligence = LeadIntelligenceService()
        self.analysis_repository = AIAnalysisRepository()
        self.session_repository = ChatSessionRepository()

    def resolve_lead(
        self,
        db: Session,
        *,
        workspace_id: int,
        lead_public_id: str | None,
    ) -> Lead | None:
        """Validate and fetch the lead before streaming starts.

        Raises NotFoundError synchronously so the HTTP layer can return 404
        before the StreamingResponse headers are committed.
        """
        if not lead_public_id:
            return None
        lead = self.leads_repository.get_by_public_id_for_workspace(
            db,
            workspace_id=workspace_id,
            public_id=lead_public_id,
        )
        if lead is None:
            raise NotFoundError("Lead was not found.")
        return lead

    def get_or_create_session(
        self,
        db: Session,
        *,
        workspace_id: int,
        session_public_id: str | None,
        lead: Lead | None,
        first_user_message: str,
    ) -> ChatSession:
        if session_public_id:
            session = self.session_repository.get_session_by_public_id(
                db, workspace_id=workspace_id, public_id=session_public_id
            )
            if session is None:
                raise NotFoundError("Chat session was not found.")
            return session
        title = (first_user_message[:80].strip()) or "New Chat"
        return self.session_repository.create_session(
            db,
            workspace_id=workspace_id,
            lead_id=lead.id if lead else None,
            title=title,
        )

    def list_sessions(self, db: Session, *, workspace_id: int) -> list[ChatSession]:
        return self.session_repository.list_sessions(db, workspace_id=workspace_id)

    def get_session_detail(
        self, db: Session, *, workspace_id: int, session_public_id: str
    ) -> ChatSession:
        session = self.session_repository.get_session_by_public_id(
            db, workspace_id=workspace_id, public_id=session_public_id
        )
        if session is None:
            raise NotFoundError("Chat session was not found.")
        return session

    def delete_session(
        self, db: Session, *, workspace_id: int, session_public_id: str
    ) -> None:
        session = self.get_session_detail(
            db, workspace_id=workspace_id, session_public_id=session_public_id
        )
        self.session_repository.delete_session(db, session)

    def stream_response(
        self,
        db: Session,
        *,
        workspace_id: int,
        messages: list[AssistantMessageInput],
        lead: Lead | None,
        session: ChatSession,
    ) -> Iterator[str]:
        """Persist user message, yield tokens, then persist the assembled response."""
        user_text = self._latest_user_message(messages)
        self.session_repository.add_message(
            db, session_id=session.id, role="user", content=user_text
        )

        assembled: list[str] = []
        for token in self._generate_tokens(
            db, workspace_id=workspace_id, messages=messages, lead=lead
        ):
            assembled.append(token)
            yield token

        full_response = "".join(assembled)
        self.session_repository.add_message(
            db, session_id=session.id, role="assistant", content=full_response
        )

    def _generate_tokens(
        self,
        db: Session,
        *,
        workspace_id: int,
        messages: list[AssistantMessageInput],
        lead: Lead | None,
    ) -> Iterator[str]:
        """Yield raw text tokens from the LLM or the deterministic fallback."""
        if lead is None:
            yield self._build_workspace_response(messages)
            return

        context = self.lead_intelligence.build(db, lead=lead)
        latest_analysis = self.analysis_repository.get_latest_snapshot_for_lead(db, lead_id=lead.id)
        latest_analysis_result = (
            LeadAnalysisResult.model_validate(latest_analysis.output_json)
            if latest_analysis is not None
            else None
        )

        settings = get_settings()
        runtime = settings.analysis_runtime

        llm_messages = self._build_llm_messages(
            lead=lead,
            messages=messages,
            facts=context.facts.model_dump(mode="json"),
            score_context=context.score_context.model_dump(mode="json") if context.score_context else None,
            latest_analysis=latest_analysis_result.model_dump(mode="json") if latest_analysis_result else None,
        )

        if runtime == "openai" and settings.has_openai_configured:
            try:
                yield from self._stream_with_openai(settings=settings, llm_messages=llm_messages)
                return
            except Exception:
                logger.warning("assistant.openai_stream_failed", exc_info=True)

        elif runtime == "ollama" and settings.has_ollama_configured:
            try:
                yield from self._stream_with_ollama(settings=settings, llm_messages=llm_messages)
                return
            except Exception:
                logger.warning("assistant.ollama_stream_failed", exc_info=True)

        elif runtime == "blocked":
            raise ServiceUnavailableError(
                "Assistant replies are unavailable because the configured AI provider is blocked."
            )

        yield self._build_lead_response(
            lead=lead,
            messages=messages,
            facts=context.facts.model_dump(mode="json"),
            score_context=context.score_context.model_dump(mode="json") if context.score_context else None,
            latest_analysis=latest_analysis_result,
        )

    def _latest_user_message(self, messages: list[AssistantMessageInput]) -> str:
        for message in reversed(messages):
            if message.role != "user":
                continue
            text = self._message_text(message)
            if text:
                return text
        return "Give me the most important takeaways."

    def _message_text(self, message: AssistantMessageInput) -> str:
        return "\n".join(
            part.text.strip()
            for part in message.parts
            if part.type == "text" and part.text and part.text.strip()
        )

    def _conversation_transcript(self, messages: list[AssistantMessageInput]) -> str:
        lines: list[str] = []
        for message in messages:
            text = self._message_text(message)
            if not text:
                continue
            role = message.role.capitalize()
            lines.append(f"{role}: {text}")
        return "\n\n".join(lines)

    def _build_workspace_response(self, messages: list[AssistantMessageInput]) -> str:
        user_need = self._latest_user_message(messages)
        return "\n".join(
            [
                "## Workspace assistant",
                "",
                "I can help with lead qualification, outreach planning, and evidence review.",
                "",
                f"Your latest request: **{user_need}**",
                "",
                "To ground the answer in stored evidence, open the assistant from a lead detail page or pass a `lead_id` context.",
                "",
                "### Useful next prompts",
                "- Summarize the strongest evidence for this lead.",
                "- Explain why this lead scored high or low.",
                "- Draft a more specific outreach angle from the stored signals.",
            ]
        )

    def _build_lead_response(
        self,
        *,
        lead: Lead,
        messages: list[AssistantMessageInput],
        facts: dict[str, Any],
        score_context: dict[str, Any] | None,
        latest_analysis: LeadAnalysisResult | None,
    ) -> str:
        user_need = self._latest_user_message(messages)
        local_business: dict[str, Any] = facts.get("local_business") or {}
        web_visibility: dict[str, Any] = facts.get("web_visibility") or {}
        place_enrichment: dict[str, Any] = facts.get("place_enrichment") or {}
        score: dict[str, Any] = score_context or {}

        company_name = str(local_business.get("company_name") or lead.company_name)
        city = str(local_business.get("city") or lead.city or "the target market")
        review_count = int(local_business.get("review_count") or lead.review_count or 0)
        rating = local_business.get("rating") or lead.rating
        rating_text = f"{rating:.1f}" if isinstance(rating, (float, int)) else "unrated"
        discoverability = web_visibility.get("official_site_discoverability")
        discoverability_text = (
            f"{round(float(discoverability) * 100)}%"
            if isinstance(discoverability, (float, int))
            else "unknown"
        )
        official_site_found = bool(place_enrichment.get("official_website_found") or lead.has_website)
        qualified = bool(score.get("qualified"))
        score_total: float | int | None = score.get("total_score")
        score_band: str = score.get("band") or "unscored"
        raw_reasons = score.get("reasons")
        top_reasons: list[Any] = list(raw_reasons) if isinstance(raw_reasons, list) else []

        lines = [
            f"## {company_name} brief",
            "",
            f"I'm answering with the stored lead evidence for **{company_name}** in **{city}**.",
            "",
            "### Direct answer",
            f"Your request was: **{user_need}**",
            "",
            f"- Current deterministic score: **{round(float(score_total)) if score_total is not None else 'Unscored'}**",
            f"- Score band: **{score_band.title() if isinstance(score_band, str) else score_band}**",
            f"- Qualified: **{'Yes' if qualified else 'Not yet'}**",
            f"- Public reputation: **{review_count} reviews** at **{rating_text}**",
            f"- Official website confirmed: **{'Yes' if official_site_found else 'No'}**",
            f"- Official site discoverability: **{discoverability_text}**",
        ]

        if top_reasons:
            lines.extend(
                [
                    "",
                    "### Score drivers",
                    *[f"- {reason}" for reason in top_reasons[:3] if isinstance(reason, str) and reason.strip()],
                ]
            )

        if latest_analysis is not None:
            lines.extend(
                [
                    "",
                    "### Latest stored analysis",
                    latest_analysis.summary,
                ]
            )

        next_actions: list[str] = []
        if not official_site_found:
            next_actions.append("Verify or create an official website before scaling outbound activity.")
        if review_count < 15:
            next_actions.append("Treat reputation-building as an early service angle because review volume is still light.")
        if isinstance(discoverability, (float, int)) and float(discoverability) < 0.5:
            next_actions.append("Position local SEO or profile cleanup as a concrete visibility fix.")
        if latest_analysis is not None and latest_analysis.recommended_services:
            next_actions.append(
                "Use the latest analysis service recommendations as the default outreach angle: "
                + ", ".join(latest_analysis.recommended_services[:3])
                + "."
            )
        if not next_actions:
            next_actions.append("Lead with proof of maturity and propose a narrow, evidence-backed growth audit.")

        lines.extend(["", "### Suggested next moves", *[f"- {item}" for item in next_actions]])
        return "\n".join(lines)

    def _build_llm_messages(
        self,
        *,
        lead: Lead,
        messages: list[AssistantMessageInput],
        facts: dict[str, Any],
        score_context: dict[str, Any] | None,
        latest_analysis: dict[str, Any] | None,
    ) -> list[dict[str, str]]:
        system_prompt = "\n".join(
            [
                "You are an evidence-first sales assistant for ProspectIQ.",
                "Use only the supplied lead record, deterministic score context, and latest stored analysis.",
                "Do not invent facts, providers, or outcomes that are not present in the supplied context.",
                "Reply in concise markdown with direct recommendations.",
                "When the evidence is incomplete, say so explicitly.",
                "Never mention internal JSON keys or implementation details.",
                "Support Arabic and English: reply in the same language the user writes in.",
            ]
        )
        context_payload: dict[str, Any] = {
            "lead": {
                "company_name": lead.company_name,
                "category": lead.category,
                "city": lead.city,
                "website_domain": lead.website_domain,
                "review_count": lead.review_count,
                "rating": lead.rating,
            },
            "facts": facts,
            "score_context": score_context,
            "latest_analysis": latest_analysis,
        }
        chat_messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        chat_messages.append(
            {
                "role": "system",
                "content": "Grounding context:\n" + json.dumps(context_payload, ensure_ascii=True, sort_keys=True),
            }
        )
        transcript = self._conversation_transcript(messages)
        if transcript:
            chat_messages.append({"role": "user", "content": transcript})
        else:
            chat_messages.append({"role": "user", "content": "Summarize this lead and recommend the next best action."})
        return chat_messages

    def _stream_with_openai(
        self,
        *,
        settings: Settings,
        llm_messages: list[dict[str, str]],
    ) -> Iterator[str]:
        with httpx.Client(
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
        ) as client:
            with client.stream(
                "POST",
                "https://api.openai.com/v1/chat/completions",
                json={
                    "model": settings.openai_model,
                    "temperature": 0.3,
                    "stream": True,
                    "messages": llm_messages,
                },
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data = line[6:]
                        if data.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            delta = (
                                chunk.get("choices", [{}])[0]
                                .get("delta", {})
                                .get("content", "")
                            )
                            if delta:
                                yield delta
                        except json.JSONDecodeError:
                            continue

    def _stream_with_ollama(
        self,
        *,
        settings: Settings,
        llm_messages: list[dict[str, str]],
    ) -> Iterator[str]:
        prompt = "\n\n".join(msg["content"] for msg in llm_messages)
        with httpx.Client(timeout=httpx.Timeout(45.0, connect=10.0)) as client:
            with client.stream(
                "POST",
                f"{settings.ollama_base_url.rstrip('/')}/api/generate",
                json={
                    "model": settings.ollama_model,
                    "prompt": prompt,
                    "stream": True,
                },
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                        token = chunk.get("response", "")
                        if token:
                            yield token
                        if chunk.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue
