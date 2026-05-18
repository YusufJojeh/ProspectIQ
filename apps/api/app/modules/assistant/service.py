from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import NotFoundError, ServiceUnavailableError
from app.modules.ai_analysis.repository import AIAnalysisRepository
from app.modules.ai_analysis.schemas import LeadAnalysisResult
from app.modules.assistant.models import ChatSession
from app.modules.assistant.repository import ChatSessionRepository
from app.modules.assistant.schemas import AssistantMessageInput, AssistantMessagePartInput
from app.modules.leads.models import Lead
from app.modules.leads.repository import LeadsRepository
from app.modules.provider_serpapi.exceptions import ProviderConfigError
from app.modules.provider_serpapi.service import SerpApiService
from app.shared.enums.jobs import ProviderFetchStatus
from app.shared.services.lead_intelligence import LeadIntelligenceService

logger = logging.getLogger(__name__)

_MAX_CONTEXT_MESSAGES = 24
_MAX_CONTEXT_CHARS = 12000
_MAX_SEARCH_SOURCES = 5

SearchStatus = str


@dataclass(frozen=True)
class StreamingRuntimeCandidate:
    provider_name: str
    stream_fn: str


@dataclass(frozen=True)
class AssistantSearchSource:
    title: str
    url: str
    snippet: str | None
    provider: str = "serpapi"

    def model_dump(self) -> dict[str, str | None]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "provider": self.provider,
        }


@dataclass(frozen=True)
class AssistantSearchContext:
    used_search: bool
    search_status: SearchStatus
    sources: list[AssistantSearchSource]
    query: str | None = None
    error_message: str | None = None

    def model_dump(self) -> dict[str, Any]:
        return {
            "used_search": self.used_search,
            "search_status": self.search_status,
            "sources": [source.model_dump() for source in self.sources],
        }


@dataclass(frozen=True)
class AssistantStreamChunk:
    type: str
    data: dict[str, Any]


class AssistantService:
    def __init__(self) -> None:
        self.leads_repository = LeadsRepository()
        self.lead_intelligence = LeadIntelligenceService()
        self.analysis_repository = AIAnalysisRepository()
        self.session_repository = ChatSessionRepository()
        self._active_search_context: AssistantSearchContext | None = None

    def resolve_lead(
        self,
        db: Session,
        *,
        workspace_id: int,
        lead_public_id: str | None,
    ) -> Lead | None:
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
            requested_lead_id = lead.id if lead else None
            if session.lead_id != requested_lead_id:
                raise NotFoundError("Chat session was not found for this lead context.")
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
    ) -> Iterator[str | AssistantStreamChunk]:
        """Persist user message, yield tokens, then persist the assembled response."""
        user_text = self._latest_user_message(messages)
        self.session_repository.add_message(
            db, session_id=session.id, role="user", content=user_text
        )
        generation_messages = self._messages_from_session_history(db, session=session)
        search_context = self._resolve_search_context(
            db,
            workspace_id=workspace_id,
            messages=generation_messages,
            lead=lead,
        )
        yield AssistantStreamChunk(type="search", data=search_context.model_dump())

        assembled: list[str] = []
        self._active_search_context = search_context
        try:
            for token in self._generate_tokens(
                db, workspace_id=workspace_id, messages=generation_messages, lead=lead
            ):
                assembled.append(token)
                yield token
        finally:
            self._active_search_context = None

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
        search_context = self._get_active_search_context()
        if lead is None:
            yield self._build_workspace_response(messages, search_context=search_context)
            return

        context = self.lead_intelligence.build(db, lead=lead)
        latest_analysis = self.analysis_repository.get_latest_snapshot_for_lead(db, lead_id=lead.id)
        latest_analysis_result = (
            LeadAnalysisResult.model_validate(latest_analysis.output_json)
            if latest_analysis is not None
            else None
        )

        llm_messages = self._build_llm_messages(
            lead=lead,
            messages=messages,
            facts=context.facts.model_dump(mode="json"),
            score_context=context.score_context.model_dump(mode="json") if context.score_context else None,
            latest_analysis=latest_analysis_result.model_dump(mode="json") if latest_analysis_result else None,
            search_context=search_context,
        )
        settings = get_settings()
        candidates = self._resolve_runtime_candidates(settings)
        if not candidates:
            raise ServiceUnavailableError(
                "Assistant replies are unavailable because no AI provider is configured."
            )

        last_error: Exception | None = None
        for candidate in candidates:
            try:
                if candidate.stream_fn == "ollama":
                    yield from self._stream_with_ollama(settings=settings, llm_messages=llm_messages)
                else:
                    yield from self._stream_with_openai(settings=settings, llm_messages=llm_messages)
                return
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "assistant.stream_failed provider=%s -- trying next runtime if available",
                    candidate.provider_name,
                    exc_info=True,
                )

        detail = "Assistant replies failed because all configured AI providers were unavailable."
        if last_error is not None:
            detail += f" Last error: {last_error}"
        raise ServiceUnavailableError(detail)

    def _resolve_runtime_candidates(self, settings: Settings) -> list[StreamingRuntimeCandidate]:
        if settings.analysis_runtime == "demo":
            return []
        if settings.analysis_runtime == "ollama":
            candidates = [StreamingRuntimeCandidate(provider_name="ollama", stream_fn="ollama")]
            if settings.analysis_fallback_runtime == "openai":
                candidates.append(
                    StreamingRuntimeCandidate(provider_name="openai", stream_fn="openai")
                )
            return candidates
        if settings.analysis_runtime == "openai":
            candidates = [StreamingRuntimeCandidate(provider_name="openai", stream_fn="openai")]
            if settings.analysis_fallback_runtime == "ollama":
                candidates.append(
                    StreamingRuntimeCandidate(provider_name="ollama", stream_fn="ollama")
                )
            return candidates
        return []

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

    def _get_active_search_context(self) -> AssistantSearchContext:
        context = getattr(self, "_active_search_context", None)
        if isinstance(context, AssistantSearchContext):
            return context
        return AssistantSearchContext(used_search=False, search_status="not_needed", sources=[])

    def _resolve_search_context(
        self,
        db: Session,
        *,
        workspace_id: int,
        messages: list[AssistantMessageInput],
        lead: Lead | None,
    ) -> AssistantSearchContext:
        latest_text = self._latest_user_message(messages)
        if not self._should_use_search(latest_text, lead=lead):
            return AssistantSearchContext(used_search=False, search_status="not_needed", sources=[])

        query = self._build_search_query(latest_text, lead=lead)
        try:
            fetch, payload = SerpApiService().web_search(
                db,
                workspace_id=workspace_id,
                search_job_id=lead.search_job_id if lead is not None else None,
                query=query,
            )
            if fetch.status != ProviderFetchStatus.OK.value:
                return AssistantSearchContext(
                    used_search=False,
                    search_status="failed",
                    sources=[],
                    query=query,
                    error_message="External search failed; answer from stored CRM evidence only.",
                )
        except ProviderConfigError:
            logger.info(
                "assistant.search.unavailable provider=serpapi workspace_id=%s lead_id=%s",
                workspace_id,
                lead.id if lead is not None else None,
            )
            return AssistantSearchContext(
                used_search=False,
                search_status="unavailable",
                sources=[],
                query=query,
                error_message="External search is unavailable because SerpAPI is not configured.",
            )
        except Exception as exc:
            logger.warning(
                "assistant.search.failed provider=serpapi workspace_id=%s lead_id=%s error_type=%s",
                workspace_id,
                lead.id if lead is not None else None,
                type(exc).__name__,
                exc_info=True,
            )
            return AssistantSearchContext(
                used_search=False,
                search_status="failed",
                sources=[],
                query=query,
                error_message="External search failed; answer from stored CRM evidence only.",
            )

        sources = self._extract_search_sources(payload)
        return AssistantSearchContext(
            used_search=True,
            search_status="used",
            sources=sources,
            query=query,
        )

    def _should_use_search(self, text: str, *, lead: Lead | None) -> bool:
        normalized = text.casefold()
        stripped = normalized.strip()
        if not stripped:
            return False

        internal_terms = (
            "stored",
            "saved",
            "crm",
            "score",
            "scored",
            "rating",
            "review count",
            "reviews",
            "follow-up",
            "follow up",
            "remember",
            "previous",
            "summary",
            "summarize",
            "why did",
            "why was",
            "درجة",
            "التقييم",
            "المحفوظ",
            "السابق",
            "تذكر",
            "لخص",
        )
        explicit_search_terms = (
            "search",
            "latest",
            "current",
            "competitor",
            "competitors",
            "market",
            "website",
            "seo",
            "public web",
            "web presence",
            "online presence",
            "enrich",
            "ابحث",
            "بحث",
            "الأحدث",
            "حالي",
            "المنافس",
            "المنافسين",
            "السوق",
            "الموقع",
            "المواقع",
            "تحسين محركات",
            "الويب",
        )
        if any(term in stripped for term in explicit_search_terms):
            if lead is not None and any(term in stripped for term in internal_terms):
                if not any(
                    term in stripped
                    for term in (
                        "search",
                        "latest",
                        "competitor",
                        "market",
                        "seo",
                        "ابحث",
                        "الأحدث",
                        "المنافس",
                        "السوق",
                    )
                ):
                    return False
            return True
        return False

    def _build_search_query(self, text: str, *, lead: Lead | None) -> str:
        cleaned_text = " ".join(text.split()).strip()
        if lead is None:
            return cleaned_text
        parts = [
            lead.company_name,
            lead.category,
            lead.city,
            "official website competitors SEO market",
            cleaned_text,
        ]
        return " ".join(str(part).strip() for part in parts if part)

    def _extract_search_sources(self, payload: dict[str, Any]) -> list[AssistantSearchSource]:
        organic_results = payload.get("organic_results")
        if not isinstance(organic_results, list):
            return []

        seen_urls: set[str] = set()
        sources: list[AssistantSearchSource] = []
        for item in organic_results:
            if not isinstance(item, dict):
                continue
            link = item.get("link")
            if not isinstance(link, str) or not link.strip():
                continue
            normalized_url = self._normalize_source_url(link)
            if not normalized_url or normalized_url in seen_urls:
                continue
            seen_urls.add(normalized_url)
            title_value = item.get("title")
            snippet_value = item.get("snippet")
            title = (
                str(title_value).strip()
                if isinstance(title_value, str) and title_value.strip()
                else normalized_url
            )
            snippet = (
                str(snippet_value).strip()
                if isinstance(snippet_value, str) and snippet_value.strip()
                else None
            )
            sources.append(
                AssistantSearchSource(
                    title=title[:180],
                    url=normalized_url,
                    snippet=snippet[:320] if snippet else None,
                )
            )
            if len(sources) >= _MAX_SEARCH_SOURCES:
                break
        return sources

    def _normalize_source_url(self, value: str) -> str | None:
        stripped = value.strip()
        parsed = urlparse(stripped)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return None
        return stripped

    def _messages_from_session_history(
        self, db: Session, *, session: ChatSession
    ) -> list[AssistantMessageInput]:
        stored_messages = self.session_repository.list_recent_messages(
            db, session_id=session.id, limit=_MAX_CONTEXT_MESSAGES
        )
        messages: list[AssistantMessageInput] = []
        used_chars = 0
        for stored in reversed(stored_messages):
            content = stored.content.strip()
            if not content:
                continue
            remaining = _MAX_CONTEXT_CHARS - used_chars
            if remaining <= 0:
                break
            if len(content) > remaining:
                content = content[-remaining:]
            messages.append(
                AssistantMessageInput(
                    id=stored.public_id,
                    role=stored.role,
                    parts=[AssistantMessagePartInput(type="text", text=content)],
                )
            )
            used_chars += len(content)
        return list(reversed(messages))

    def _conversation_transcript(self, messages: list[AssistantMessageInput]) -> str:
        lines: list[str] = []
        for message in messages:
            text = self._message_text(message)
            if not text:
                continue
            role = message.role.capitalize()
            lines.append(f"{role}: {text}")
        return "\n\n".join(lines)

    def _build_workspace_response(
        self,
        messages: list[AssistantMessageInput],
        *,
        search_context: AssistantSearchContext,
    ) -> str:
        user_need = self._latest_user_message(messages)
        search_line = ""
        if search_context.search_status == "unavailable":
            search_line = "\nExternal search is unavailable, so this answer is limited to stored system context.\n"
        elif search_context.search_status == "failed":
            search_line = "\nExternal search failed, so this answer is limited to stored system context.\n"
        elif search_context.used_search:
            search_line = "\nI used external search evidence where available and kept it separate from system data.\n"
        return "\n".join(
            [
                "## Workspace assistant",
                "",
                "I can help with lead qualification, outreach planning, and evidence review.",
                search_line,
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
        search_context: AssistantSearchContext,
    ) -> list[dict[str, str]]:
        system_prompt = "\n".join(
            [
                "You are an evidence-first sales assistant for ProspectIQ.",
                "Use only the supplied lead record, deterministic score context, and latest stored analysis.",
                "When external search evidence is supplied, clearly distinguish it from stored CRM/system data.",
                "If external search was unavailable or failed, say that briefly and do not invent web evidence.",
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
            "external_search": search_context.model_dump(),
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
                f"{settings.openai_base_url.rstrip('/')}/responses",
                json={
                    "model": settings.openai_model,
                    "input": llm_messages,
                    "stream": True,
                    "store": False,
                },
            ) as response:
                response.raise_for_status()
                event_type = ""
                for line in response.iter_lines():
                    if not line:
                        event_type = ""
                        continue
                    if line.startswith("event: "):
                        event_type = line[7:]
                        continue
                    if not line.startswith("data: "):
                        continue

                    data = line[6:]
                    if data.strip() == "[DONE]":
                        break

                    payload = json.loads(data)
                    payload_type = payload.get("type") or event_type
                    if payload_type == "response.output_text.delta":
                        delta = payload.get("delta", "")
                        if isinstance(delta, str) and delta:
                            yield delta
                    elif payload_type == "response.refusal.delta":
                        delta = payload.get("delta", "")
                        if isinstance(delta, str) and delta:
                            yield delta
                    elif payload_type == "error":
                        message = payload.get("message") or payload.get("error") or "OpenAI streaming failed."
                        raise ServiceUnavailableError(str(message))

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
                    chunk = json.loads(line)
                    token = chunk.get("response", "")
                    if token:
                        yield token
                    if chunk.get("done"):
                        break
