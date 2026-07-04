from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
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
from app.modules.leads.schemas import LeadSortOption
from app.modules.provider_serpapi.engines.google_jobs import (
    build_google_jobs_params,
    extract_jobs_items,
    run_google_jobs,
)
from app.modules.provider_serpapi.engines.google_news import (
    build_google_news_params,
    extract_news_items,
    run_google_news,
)
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
    news_results: list[dict[str, Any]] | None = None
    hiring_signals: list[dict[str, Any]] | None = None

    def model_dump(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "used_search": self.used_search,
            "search_status": self.search_status,
            "sources": [source.model_dump() for source in self.sources],
        }
        if self.news_results:
            result["news_results"] = self.news_results
        if self.hiring_signals:
            result["hiring_signals"] = self.hiring_signals
        return result


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

    def list_sessions(
        self,
        db: Session,
        *,
        workspace_id: int,
        lead_id: int | None = None,
    ) -> list[ChatSession]:
        return self.session_repository.list_sessions(db, workspace_id=workspace_id, lead_id=lead_id)

    def get_session_detail(
        self, db: Session, *, workspace_id: int, session_public_id: str
    ) -> ChatSession:
        session = self.session_repository.get_session_by_public_id(
            db, workspace_id=workspace_id, public_id=session_public_id
        )
        if session is None:
            raise NotFoundError("Chat session was not found.")
        return session

    def delete_session(self, db: Session, *, workspace_id: int, session_public_id: str) -> None:
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
            # Workspace-level question: answer from the LLM grounded on real stored
            # leads/scores. Deterministic builders are only a fallback for when no AI
            # provider is configured (demo / offline mode).
            settings = get_settings()
            candidates = self._resolve_runtime_candidates(settings)
            if candidates:
                llm_messages = self._build_workspace_llm_messages(
                    db,
                    workspace_id=workspace_id,
                    messages=messages,
                    search_context=search_context,
                )
                yield from self._stream_from_llm(
                    settings=settings, candidates=candidates, llm_messages=llm_messages
                )
                return
            yield from self._workspace_fallback_tokens(
                db,
                workspace_id=workspace_id,
                messages=messages,
                search_context=search_context,
            )
            return

        context = self.lead_intelligence.build(db, lead=lead)
        latest_analysis = self.analysis_repository.get_latest_snapshot_for_lead(db, lead_id=lead.id)
        latest_analysis_result = (
            LeadAnalysisResult.model_validate(latest_analysis.output_json)
            if latest_analysis is not None
            else None
        )
        facts_payload = context.facts.model_dump(mode="json")
        score_context_payload = (
            context.score_context.model_dump(mode="json") if context.score_context else None
        )

        if score_context_payload is None and self._is_score_related_request(
            self._latest_user_message(messages)
        ):
            yield self._build_unscored_score_response(
                lead=lead,
                messages=messages,
                facts=facts_payload,
                latest_analysis=latest_analysis_result,
            )
            return

        llm_messages = self._build_llm_messages(
            lead=lead,
            messages=messages,
            facts=facts_payload,
            score_context=score_context_payload,
            latest_analysis=latest_analysis_result.model_dump(mode="json")
            if latest_analysis_result
            else None,
            search_context=search_context,
        )
        settings = get_settings()
        candidates = self._resolve_runtime_candidates(settings)
        if not candidates:
            raise ServiceUnavailableError(
                "Assistant replies are unavailable because no AI provider is configured."
            )
        yield from self._stream_from_llm(
            settings=settings, candidates=candidates, llm_messages=llm_messages
        )

    def _stream_from_llm(
        self,
        *,
        settings: Settings,
        candidates: list[StreamingRuntimeCandidate],
        llm_messages: list[dict[str, str]],
    ) -> Iterator[str]:
        """Stream from the first healthy runtime, failing over to the next candidate."""
        last_error: Exception | None = None
        for candidate in candidates:
            try:
                if candidate.stream_fn == "ollama":
                    yield from self._stream_with_ollama(
                        settings=settings, llm_messages=llm_messages
                    )
                else:
                    yield from self._stream_with_openai(
                        settings=settings, llm_messages=llm_messages
                    )
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

    def _is_score_related_request(self, text: str) -> bool:
        normalized = text.casefold()
        score_terms = (
            "score",
            "scored",
            "scoring",
            "rank",
            "rating score",
            "درجة",
            "درجه",
            "التقييم",
            "تقييم",
            "مقيّم",
            "مقيم",
            "غير مقيّم",
            "غير مقيم",
        )
        return any(term in normalized for term in score_terms)

    def _prefers_arabic(self, text: str) -> bool:
        return any("\u0600" <= char <= "\u06ff" for char in text)

    def _is_qualified_leads_question(self, text: str) -> bool:
        """Detect if asking about qualified leads to contact."""
        text_lower = text.lower()
        keywords_en = ["qualified leads", "which leads", "who should i contact",
                      "prioritize", "first", "outreach", "reach out"]
        keywords_ar = ["عملاء مؤهلين", "أي العملاء", "من أبدأ", "من أولا",
                      "أولويات", "أول", "التواصل", "أتواصل"]

        if any(kw in text_lower for kw in keywords_en):
            return True
        if any(kw in text_lower for kw in keywords_ar):
            return True
        return False

    def _is_comparison_question(self, text: str) -> bool:
        """Detect if asking for a comparison between leads."""
        text_lower = text.lower()
        keywords_en = ["compare", "comparison", "vs", "versus", "difference",
                      "which is better", "rank"]
        keywords_ar = ["قارن", "مقارنة", "بين", "الفرق", "أيهما", "ترتيب"]

        if any(kw in text_lower for kw in keywords_en):
            return True
        if any(kw in text_lower for kw in keywords_ar):
            return True
        return False

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
        # Run news + hiring lookups concurrently to minimise added latency.
        news_results: list[dict[str, Any]] | None = None
        hiring_signals: list[dict[str, Any]] | None = None
        if lead is not None:
            with ThreadPoolExecutor(max_workers=2) as pool:
                news_future = pool.submit(self._fetch_news_for_lead, lead)
                jobs_future = pool.submit(self._fetch_hiring_signals_for_lead, lead)
                news_results = news_future.result()
                hiring_signals = jobs_future.result()
        return AssistantSearchContext(
            used_search=True,
            search_status="used",
            sources=sources,
            query=query,
            news_results=news_results,
            hiring_signals=hiring_signals,
        )

    def _fetch_news_for_lead(self, lead: Lead) -> list[dict[str, Any]] | None:
        """
        Fetch recent Google News mentions for the lead's company.
        Returns a list of news items or None if unavailable / not configured.
        """
        if not lead.company_name:
            return None
        try:
            from app.modules.provider_serpapi.client import SerpApiClient

            client = SerpApiClient()
            news_query = f"{lead.company_name} {lead.city or ''}".strip()
            params = build_google_news_params(query=news_query)
            result = run_google_news(client, params=params)
            items = extract_news_items(result, max_items=5)
            return items if items else None
        except Exception:
            logger.debug(
                "assistant.news_search.unavailable company=%s",
                lead.company_name,
                exc_info=False,
            )
            return None

    def _fetch_hiring_signals_for_lead(self, lead: Lead) -> list[dict[str, Any]] | None:
        """
        Fetch Google Jobs postings for the lead's company.
        Job postings indicate growth/expansion — a high-signal sales timing indicator.
        Returns a list of job items or None if unavailable / not configured.
        """
        if not lead.company_name:
            return None
        try:
            from app.modules.provider_serpapi.client import SerpApiClient

            client = SerpApiClient()
            jobs_query = lead.company_name
            params = build_google_jobs_params(
                query=jobs_query,
                location=lead.city or "",
            )
            result = run_google_jobs(client, params=params)
            items = extract_jobs_items(result, max_items=5)
            return items if items else None
        except Exception:
            logger.debug(
                "assistant.hiring_signals.unavailable company=%s",
                lead.company_name,
                exc_info=False,
            )
            return None

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
            "official website competitors market",
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

    def _workspace_fallback_tokens(
        self,
        db: Session,
        *,
        workspace_id: int,
        messages: list[AssistantMessageInput],
        search_context: AssistantSearchContext,
    ) -> Iterator[str]:
        """Deterministic workspace answers used only when no AI provider is configured."""
        user_message = self._latest_user_message(messages)
        if self._is_qualified_leads_question(user_message):
            yield self._build_qualified_leads_response(
                db, workspace_id=workspace_id, messages=messages
            )
            return
        if self._is_comparison_question(user_message):
            yield self._build_comparison_response(
                db, workspace_id=workspace_id, messages=messages
            )
            return
        yield self._build_workspace_response(
            db,
            workspace_id=workspace_id,
            messages=messages,
            search_context=search_context,
        )

    def _workspace_leads_grounding(
        self, db: Session, *, workspace_id: int, limit: int = 25
    ) -> dict[str, Any]:
        """Collect the top stored leads + their latest scores as LLM grounding facts."""
        leads, total = self.leads_repository.list_paginated(
            db,
            workspace_id=workspace_id,
            page=1,
            page_size=limit,
            status=None,
            search_job_public_id=None,
            has_website=None,
            sort=LeadSortOption.SCORE_DESC,
        )
        scores = self.leads_repository.get_latest_scores(db, [lead.id for lead in leads])
        records: list[dict[str, Any]] = []
        qualified_in_top_n = 0
        for lead in leads:
            score = scores.get(lead.id)
            if score is not None and score.qualified:
                qualified_in_top_n += 1
            records.append(
                {
                    "company_name": lead.company_name,
                    "category": lead.category,
                    "city": lead.city,
                    "rating": lead.rating,
                    "review_count": lead.review_count,
                    "has_website": lead.has_website,
                    "website_domain": lead.website_domain,
                    "data_confidence": round(lead.data_confidence, 2),
                    "score": round(score.total_score) if score is not None else None,
                    "band": score.band if score is not None else None,
                    "qualified": bool(score.qualified) if score is not None else None,
                    "score_state": "scored" if score is not None else "unscored",
                }
            )
        return {
            "total_leads_in_workspace": total,
            "returned_leads": len(records),
            "qualified_in_returned": qualified_in_top_n,
            "leads": records,
        }

    def _build_workspace_llm_messages(
        self,
        db: Session,
        *,
        workspace_id: int,
        messages: list[AssistantMessageInput],
        search_context: AssistantSearchContext,
    ) -> list[dict[str, str]]:
        """Build grounded chat messages for a workspace-level (no specific lead) question."""
        grounding = self._workspace_leads_grounding(db, workspace_id=workspace_id)
        system_prompt = "\n".join(
            [
                "You are an evidence-first B2B sales intelligence assistant for ProspectIQ.",
                "You help a sales team prioritise leads, compare them, and plan outreach.",
                "",
                "RULES:",
                "1. Use ONLY the leads, scores, and evidence in the supplied grounding "
                "context. Never invent companies, numbers, ratings, categories, or URLs.",
                "2. Answer the user's ACTUAL question. 'Compare and explain' means give the "
                "comparison AND explain the trade-offs with a clear recommendation — not just "
                "a table. 'How do I engage / handle them' means give a concrete outreach "
                "approach per lead, not a bare list.",
                "3. Rank and prioritise by the provided deterministic `score`. Do not reorder "
                "leads by your own judgement.",
                "4. A lead with score_state 'unscored' has no stored score; do not state or "
                "infer a score for it.",
                "5. Distinguish stored CRM/score data from any live web or news evidence.",
                "6. Reply in the same language the user writes in (Arabic or English).",
                "7. Format in concise, scannable markdown. Use a table only when it adds "
                "clarity, and always follow a comparison table with a short written analysis.",
                "8. If there are no leads in the context, say so and suggest running a search "
                "job — do not fabricate leads.",
                "9. Never expose internal JSON keys, field names, or implementation details.",
            ]
        )
        context_payload: dict[str, Any] = {
            "workspace_leads": grounding,
            "external_search": search_context.model_dump(),
        }
        chat_messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {
                "role": "system",
                "content": "Grounding context:\n"
                + json.dumps(context_payload, ensure_ascii=True, sort_keys=True),
            },
        ]
        transcript = self._conversation_transcript(messages)
        if transcript:
            chat_messages.append({"role": "user", "content": transcript})
        else:
            chat_messages.append(
                {
                    "role": "user",
                    "content": "Give me a prioritized overview of my best leads and who to "
                    "contact first.",
                }
            )
        return chat_messages

    def _build_qualified_leads_response(
        self,
        db: Session,
        *,
        workspace_id: int,
        messages: list[AssistantMessageInput],
    ) -> str:
        """Build a ranked list of qualified leads ready for outreach."""
        user_need = self._latest_user_message(messages)
        prefers_arabic = self._prefers_arabic(user_need)

        # Get qualified leads sorted by score
        leads, total = self.leads_repository.list_paginated(
            db,
            workspace_id=workspace_id,
            page=1,
            page_size=10,
            status=None,
            search_job_public_id=None,
            has_website=None,
            sort=LeadSortOption.SCORE_DESC,
        )
        latest_scores = self.leads_repository.get_latest_scores(db, [lead.id for lead in leads])
        qualified_leads = [
            (lead, score)
            for lead in leads
            if (score := latest_scores.get(lead.id)) and score.qualified
        ]

        if not qualified_leads:
            if prefers_arabic:
                return "لا توجد عملاء مؤهلين حاليًا."
            return "No qualified leads currently."

        if prefers_arabic:
            lines = [
                "# 🎯 العملاء المؤهلون",
                "",
                f"**{len(qualified_leads)} عملاء مؤهلين** من أصل {total} محفوظ.",
                "",
            ]
            for idx, (lead, score) in enumerate(qualified_leads[:10], 1):
                score_text = f"{score.total_score:.0f}/100" if score else "—"
                rating_text = f"{lead.rating:.1f}⭐" if lead.rating else "—"
                lines.extend([
                    f"{idx}. **{lead.company_name}**",
                    f"   • الدرجة: {score_text}",
                    f"   • التقييم: {rating_text} ({lead.review_count} مراجعة)",
                    f"   • الفئة: {lead.category}",
                    f"   • المدينة: {lead.city or '—'}",
                    "",
                ])
            return "\n".join(lines)
        else:
            lines = [
                "# 🎯 Qualified Leads",
                "",
                f"**{len(qualified_leads)} qualified leads** from {total} stored.",
                "",
            ]
            for idx, (lead, score) in enumerate(qualified_leads[:10], 1):
                score_text = f"{score.total_score:.0f}/100" if score else "—"
                rating_text = f"{lead.rating:.1f}⭐" if lead.rating else "—"
                lines.extend([
                    f"{idx}. **{lead.company_name}**",
                    f"   • Score: {score_text}",
                    f"   • Rating: {rating_text} ({lead.review_count} reviews)",
                    f"   • Category: {lead.category}",
                    f"   • City: {lead.city or '—'}",
                    "",
                ])
            return "\n".join(lines)

    def _build_comparison_response(
        self,
        db: Session,
        *,
        workspace_id: int,
        messages: list[AssistantMessageInput],
    ) -> str:
        """Build a comparison of top 3 leads."""
        user_need = self._latest_user_message(messages)
        prefers_arabic = self._prefers_arabic(user_need)

        leads, _ = self.leads_repository.list_paginated(
            db,
            workspace_id=workspace_id,
            page=1,
            page_size=3,
            status=None,
            search_job_public_id=None,
            has_website=None,
            sort=LeadSortOption.SCORE_DESC,
        )
        latest_scores = self.leads_repository.get_latest_scores(db, [lead.id for lead in leads])

        if len(leads) < 2:
            if prefers_arabic:
                return "عملاء قليلين للمقارنة."
            return "Insufficient leads for comparison."

        if prefers_arabic:
            lines = [
                "# 📊 مقارنة",
                "",
                "| الاسم | الدرجة | التقييم | الفئة | المدينة |",
                "|------|--------|---------|---------|---------|",
            ]
            for lead in leads:
                score = latest_scores.get(lead.id)
                score_text = f"{score.total_score:.0f}/100" if score else "—"
                rating_text = f"{lead.rating:.1f}" if lead.rating else "—"
                lines.append(
                    f"| {lead.company_name} | {score_text} | {rating_text} | {lead.category} | {lead.city or '—'} |"
                )
            return "\n".join(lines)
        else:
            lines = [
                "# 📊 Comparison",
                "",
                "| Name | Score | Rating | Category | City |",
                "|------|--------|---------|---------|---------|",
            ]
            for lead in leads:
                score = latest_scores.get(lead.id)
                score_text = f"{score.total_score:.0f}/100" if score else "—"
                rating_text = f"{lead.rating:.1f}" if lead.rating else "—"
                lines.append(
                    f"| {lead.company_name} | {score_text} | {rating_text} | {lead.category} | {lead.city or '—'} |"
                )
            return "\n".join(lines)

    def _build_workspace_response(
        self,
        db: Session,
        *,
        workspace_id: int,
        messages: list[AssistantMessageInput],
        search_context: AssistantSearchContext,
    ) -> str:
        """Build a workspace-level summary from stored leads and scores."""
        user_need = self._latest_user_message(messages)
        prefers_arabic = self._prefers_arabic(user_need)
        search_line = (
            "_Augmented with live web search results._"
            if search_context.used_search
            else ""
        )
        search_line_ar = (
            "_تم تعزيزه بنتائج البحث الحي._"
            if search_context.used_search
            else ""
        )

        leads, total = self.leads_repository.list_paginated(
            db,
            workspace_id=workspace_id,
            page=1,
            page_size=5,
            status=None,
            search_job_public_id=None,
            has_website=None,
            sort=LeadSortOption.SCORE_DESC,
        )
        latest_scores = self.leads_repository.get_latest_scores(db, [lead.id for lead in leads])

        if not leads:
            if prefers_arabic:
                return "\n".join(
                    [
                        "## مساعد مساحة العمل",
                        "",
                        "أستطيع الإجابة عن أسئلة عامة لمساحة العمل، لكن لا توجد leads محفوظة حاليًا.",
                        search_line_ar,
                        "",
                        f"آخر طلب: **{user_need}**",
                        "",
                        "الخطوة التالية: شغّل مهمة بحث، اترك التقييم يكتمل، ثم اسأل عن العملاء الذين يستحقون التواصل أولاً.",
                    ]
                )
            return "\n".join(
                [
                    "## Workspace assistant",
                    "",
                    "I can answer general workspace questions, but there are no stored leads yet.",
                    search_line,
                    "",
                    f"Your latest request: **{user_need}**",
                    "",
                    "Next step: run a search job, let scoring finish, then ask which leads deserve outreach first.",
                ]
            )

        top_lead = leads[0]
        top_score = latest_scores.get(top_lead.id)
        top_score_text = (
            f"{top_score.total_score:.0f}/100" if top_score is not None else "unscored"
        )
        top_band_text = top_score.band if top_score is not None else "unscored"
        qualified_text = (
            "qualified"
            if top_score is not None and top_score.qualified
            else "not qualified"
            if top_score is not None
            else "not scored"
        )
        qualified_text_ar = (
            "مؤهل"
            if top_score is not None and top_score.qualified
            else "غير مؤهل"
            if top_score is not None
            else "غير مقيّم"
        )
        rating_text = (
            f"{top_lead.rating:.1f} rating / {top_lead.review_count} reviews"
            if top_lead.rating is not None
            else f"{top_lead.review_count} reviews"
        )
        rating_text_ar = (
            f"تقييم {top_lead.rating:.1f} / {top_lead.review_count} مراجعة"
            if top_lead.rating is not None
            else f"{top_lead.review_count} مراجعة"
        )
        confidence_text = f"{round(top_lead.data_confidence * 100)}%"

        candidate_lines: list[str] = []
        candidate_lines_ar: list[str] = []
        for index, candidate in enumerate(leads[:3], start=1):
            candidate_score = latest_scores.get(candidate.id)
            score_text = (
                f"{candidate_score.total_score:.0f}/100"
                if candidate_score is not None
                else "unscored"
            )
            band_text = candidate_score.band if candidate_score is not None else "unscored"
            candidate_lines.append(
                f"{index}. **{candidate.company_name}** - {score_text}, {band_text}, "
                f"{candidate.review_count} reviews, {candidate.website_domain or 'no website'}"
            )
            candidate_lines_ar.append(
                f"{index}. **{candidate.company_name}** - {score_text}، {band_text}، "
                f"{candidate.review_count} مراجعة، {candidate.website_domain or 'لا يوجد موقع'}"
            )

        if prefers_arabic:
            # Build Arabic response with enhanced formatting

            # Calculate additional insights for top lead
            has_website_ar = "✓ نعم" if top_lead.has_website else "✗ لا"
            confidence_icon = "🟢" if top_lead.data_confidence >= 0.85 else "🟡" if top_lead.data_confidence >= 0.70 else "🔴"
            qualification_icon = "✓" if (top_score and top_score.qualified) else "○"
            band_emoji = "⭐⭐⭐" if top_band_text == "high" else "⭐⭐" if top_band_text == "medium" else "⭐"

            # Build action recommendations
            action_items_ar = []
            if top_lead.has_website:
                action_items_ar.append("• تصفح الموقع الرسمي لفهم الخدمات الحالية")
            if top_score and top_score.qualified:
                action_items_ar.append("• ابدأ بمسودة تواصل شخصية")
            else:
                action_items_ar.append("• اجمع مزيد من البيانات قبل التواصل")
            if top_lead.review_count and top_lead.review_count > 50:
                action_items_ar.append("• قارن مع المنافسين الآخرين في السوق")

            return "\n".join(
                [
                    "# 🎯 مساعد مساحة العمل — ملخص العملاء",
                    "",
                    "أستطيع الإجابة عن أسئلة عامة بناءً على العملاء المحفوظين والدرجات والأدلة.",
                    search_line_ar,
                    "",
                    f"**آخر طلبك:** {user_need}",
                    "",
                    "---",
                    "",
                    f"## 🏆 أفضل عميل حاليًا: {top_lead.company_name}",
                    "",
                    "| المقياس | التفاصيل |",
                    "|--------|---------|",
                    f"| **الدرجة** | {top_score_text} {band_emoji} |",
                    f"| **التأهيل** | {qualification_icon} {qualified_text_ar} |",
                    f"| **السمعة** | {rating_text_ar} |",
                    f"| **الموقع الرسمي** | {has_website_ar} |",
                    f"| **ثقة البيانات** | {confidence_icon} {confidence_text} |",
                    "",
                    "### 💡 السبب وراء اختيار هذا العميل:",
                    f"- **{'درجة عالية' if top_band_text == 'high' else 'درجة متوسطة' if top_band_text == 'medium' else 'درجة منخفضة أو غير محددة'}:** {top_score_text} في قاعدة البيانات الحالية",
                    f"- **{'بيانات موثوقة جداً' if top_lead.data_confidence >= 0.85 else 'بيانات كافية' if top_lead.data_confidence >= 0.70 else 'بيانات تحتاج تحسين'}:** ثقة {confidence_text}",
                    f"- **{'جاهز للتواصل' if top_lead.has_website and top_score and top_score.qualified else 'يحتاج مزيداً من البيانات'}:** {'بيانات كافية للبدء برسالة شخصية' if top_lead.has_website and top_score and top_score.qualified else 'اجمع بيانات إضافية قبل التواصل'}",
                    "",
                    "### ⚡ الخطوات التالية المقترحة:",
                    *action_items_ar,
                    "",
                    "---",
                    "",
                    f"## 📈 أفضل المرشحين ({min(3, len(leads))} من {total})",
                    "",
                    *candidate_lines_ar,
                    "",
                    "### 🔍 اسأل المزيد:",
                    "- _أي العملاء المؤهلين يجب أن أبدأ معهم أولاً؟_",
                    "- _قارن بين أفضل 3 عملاء واشرح الفروقات_",
                    f"- _اكتب لي مسودة تواصل متخصصة لـ {top_lead.company_name}_",
                    "- _أين يقع هذا العميل ضمن السوق المحلية؟_",
                    "",
                    "**💡 ملخص:** للمزيد من التفاصيل والأدلة، افتح صفحة تفاصيل العميل.",
                ]
            )

        # English response with enhanced formatting
        has_website_en = "✓ Yes" if top_lead.has_website else "✗ No"
        confidence_icon = "🟢" if top_lead.data_confidence >= 0.85 else "🟡" if top_lead.data_confidence >= 0.70 else "🔴"
        qualification_icon = "✓" if (top_score and top_score.qualified) else "○"
        band_emoji = "⭐⭐⭐" if top_band_text == "high" else "⭐⭐" if top_band_text == "medium" else "⭐"

        # Build action recommendations
        action_items_en = []
        if top_lead.has_website:
            action_items_en.append("• Visit the official website to understand their current services")
        if top_score and top_score.qualified:
            action_items_en.append("• Start with a personalized outreach draft")
        else:
            action_items_en.append("• Gather additional data before reaching out")
        if top_lead.review_count and top_lead.review_count > 50:
            action_items_en.append("• Compare with other competitors in the market")

        return "\n".join(
            [
                "# 🎯 Workspace Assistant — Lead Summary",
                "",
                "I can answer general workspace questions from stored leads, scores, and evidence.",
                search_line,
                "",
                f"**Your latest request:** {user_need}",
                "",
                "---",
                "",
                f"## 🏆 Best Lead Right Now: {top_lead.company_name}",
                "",
                "| Metric | Details |",
                "|--------|---------|",
                f"| **Score** | {top_score_text} {band_emoji} |",
                f"| **Qualification** | {qualification_icon} {qualified_text} |",
                f"| **Reputation** | {rating_text} |",
                f"| **Official Website** | {has_website_en} |",
                f"| **Data Confidence** | {confidence_icon} {confidence_text} |",
                "",
                "### 💡 Why This Lead Ranks First:",
                f"- **{'Top-tier' if top_band_text == 'high' else 'Above-average' if top_band_text == 'medium' else 'Low or unscored'} lead:** {top_score_text} in your current database",
                f"- **{'High-confidence data' if top_lead.data_confidence >= 0.85 else 'Adequate data confidence' if top_lead.data_confidence >= 0.70 else 'Low data confidence — consider enriching'}:** {confidence_text}",
                f"- **{'Ready to engage' if top_lead.has_website and top_score and top_score.qualified else 'Needs more data'}:** {'sufficient information for a personalized message' if top_lead.has_website and top_score and top_score.qualified else 'gather additional evidence before outreach'}",
                "",
                "### ⚡ Suggested Next Steps:",
                *action_items_en,
                "",
                "---",
                "",
                f"## 📈 Top candidates ({min(3, len(leads))} of {total})",
                "",
                *candidate_lines,
                "",
                "### 🔍 Ask Follow-Up Questions:",
                "- _Which qualified leads should I prioritize for outreach?_",
                "- _Compare the top 3 leads and explain the key differences._",
                f"- _Draft a custom outreach message for {top_lead.company_name}_",
                "- _Where does this lead rank in the local market?_",
                "",
                "**💡 Pro Tip:** For deeper evidence and analysis, open the lead detail page.",
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
        rating_text = f"{rating:.1f}" if isinstance(rating, float | int) else "unrated"
        discoverability = web_visibility.get("official_site_discoverability")
        discoverability_text = (
            f"{round(float(discoverability) * 100)}%"
            if isinstance(discoverability, float | int)
            else "unknown"
        )
        official_site_found = bool(
            place_enrichment.get("official_website_found") or lead.has_website
        )
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
                    *[
                        f"- {reason}"
                        for reason in top_reasons[:3]
                        if isinstance(reason, str) and reason.strip()
                    ],
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
            next_actions.append(
                "Verify or create an official website before scaling outbound activity."
            )
        if review_count < 15:
            next_actions.append(
                "Treat reputation-building as an early service angle because review volume is still light."
            )
        if isinstance(discoverability, float | int) and float(discoverability) < 0.5:
            next_actions.append(
                "Position local SEO or profile cleanup as a concrete visibility fix."
            )
        if latest_analysis is not None and latest_analysis.recommended_services:
            next_actions.append(
                "Use the latest analysis service recommendations as the default outreach angle: "
                + ", ".join(latest_analysis.recommended_services[:3])
                + "."
            )
        if not next_actions:
            next_actions.append(
                "Lead with proof of maturity and propose a narrow, evidence-backed growth audit."
            )

        lines.extend(["", "### Suggested next moves", *[f"- {item}" for item in next_actions]])
        return "\n".join(lines)

    def _build_unscored_score_response(
        self,
        *,
        lead: Lead,
        messages: list[AssistantMessageInput],
        facts: dict[str, Any],
        latest_analysis: LeadAnalysisResult | None,
    ) -> str:
        user_need = self._latest_user_message(messages)
        local_business: dict[str, Any] = facts.get("local_business") or {}
        web_visibility: dict[str, Any] = facts.get("web_visibility") or {}
        place_enrichment: dict[str, Any] = facts.get("place_enrichment") or {}

        company_name = str(local_business.get("company_name") or lead.company_name)
        review_count = int(local_business.get("review_count") or lead.review_count or 0)
        rating = local_business.get("rating") or lead.rating
        rating_text = f"{rating:.1f}" if isinstance(rating, float | int) else "غير متوفر"
        website = lead.website_domain or local_business.get("website_domain") or "غير متوفر"
        confidence = local_business.get("data_confidence") or facts.get("data_confidence")
        confidence_text = (
            f"{round(float(confidence) * 100)}%"
            if isinstance(confidence, float | int)
            else "غير متوفر"
        )
        official_site_found = bool(
            place_enrichment.get("official_website_found") or lead.has_website
        )
        discoverability = web_visibility.get("official_site_discoverability")
        discoverability_missing = not isinstance(discoverability, float | int)
        has_hours = bool(local_business.get("hours_present"))

        if self._prefers_arabic(user_need):
            missing: list[str] = []
            if not has_hours:
                missing.append("ساعات العمل")
            if discoverability_missing:
                missing.append("إشارة واضحة لاكتشاف الموقع الرسمي في البحث")
            if latest_analysis is None:
                missing.append("تحليل AI محفوظ لهذا العميل")
            if not missing:
                missing.append("تشغيل خطوة التقييم لحفظ درجة deterministic")

            lines = [
                f"## {company_name}",
                "",
                "**هذا العميل غير مقيّم حاليًا في النظام.**",
                "لا توجد درجة محفوظة أو شريحة تقييم محفوظة لهذا العميل، لذلك لا أستطيع شرح أسباب درجة غير موجودة أو تأكيد تقييمه.",
                "",
                "### الأدلة المتاحة",
                f"- السمعة العامة: **{review_count} مراجعة** بتقييم **{rating_text}**.",
                f"- الموقع الإلكتروني: **{website}**.",
                f"- الموقع الرسمي مؤكد من البيانات المخزنة: **{'نعم' if official_site_found else 'لا'}**.",
                f"- ثقة البيانات المخزنة: **{confidence_text}**. هذه ثقة في البيانات وليست درجة العميل.",
                "",
                "### الناقص قبل التقييم",
                *[f"- {item}." for item in missing],
                "",
                "### الخطوة التالية",
                "- شغّل تقييم/إعادة تقييم العميل من صفحة التفاصيل أو أعد تشغيل discovery/refresh حتى يتم حفظ `latest_score` و `latest_band`، وبعدها يمكنني شرح محركات الدرجة بدقة.",
            ]
            return "\n".join(lines)

        missing_en: list[str] = []
        if not has_hours:
            missing_en.append("business hours")
        if discoverability_missing:
            missing_en.append("clear official-site discoverability evidence")
        if latest_analysis is None:
            missing_en.append("a stored AI analysis snapshot")
        if not missing_en:
            missing_en.append("a scoring run that stores the deterministic score")

        return "\n".join(
            [
                f"## {company_name}",
                "",
                "**This lead is currently unscored in the system.**",
                "There is no stored score or score band, so I cannot explain score drivers for a score that does not exist.",
                "",
                "### Available evidence",
                f"- Public reputation: **{review_count} reviews** at **{rating_text}**.",
                f"- Website: **{website}**.",
                f"- Official website confirmed from stored data: **{'Yes' if official_site_found else 'No'}**.",
                f"- Stored data confidence: **{confidence_text}**. This is data confidence, not the lead score.",
                "",
                "### Missing before scoring",
                *[f"- {item}." for item in missing_en],
                "",
                "### Next action",
                "- Run lead scoring or refresh/discovery so `latest_score` and `latest_band` are stored. Then I can explain the actual score drivers.",
            ]
        )

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
                "You are an evidence-first B2B sales intelligence assistant for ProspectIQ.",
                "Your job is to help sales professionals qualify leads, craft outreach, and prioritize opportunities.",
                "",
                "RULES:",
                "1. Only cite facts present in the supplied grounding context (lead record, score context, analysis, search results, news).",
                "2. Clearly distinguish sources: stored CRM data vs. live SerpAPI search vs. live web_search tool results vs. news mentions.",
                "3. If evidence is missing or unclear, say so explicitly — never invent facts, URLs, names, or outcomes.",
                "4. Reply in concise, scannable markdown: use bullet points and **bold** for key insights.",
                "5. When you cite a search result or news item, include the source URL.",
                "6. When you use the web_search tool, always cite the source URL in your response.",
                "7. Prefer tool-based live search over training knowledge for company-specific facts.",
                "8. Never expose internal JSON keys, field names, or implementation details.",
                "9. Language: reply in the same language the user writes in (Arabic or English).",
                "10. If score_context is null or score_state is unscored, the lead has no stored score. Say it is unscored and do not explain score drivers, score band, or qualification as if a score exists.",
                "11. Never infer a score from rating, review count, confidence, analysis text, or other evidence. Stored score context is the only source for score claims.",
                "",
                "RESPONSE FORMAT (for lead analysis requests):",
                "- **Summary**: 2-3 sentence lead overview",
                "- **Evidence**: key facts with source citations",
                "- **Opportunity**: why this lead is worth pursuing (or not)",
                "- **Next action**: one concrete recommended step",
                "",
                "If news_results are in the context, highlight any relevant recent mentions.",
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
            "score_state": "scored" if score_context is not None else "unscored",
            "score_instruction": (
                "A stored deterministic score exists; score claims must use only score_context."
                if score_context is not None
                else "No stored deterministic score exists for this lead. Treat it as unscored and explain available evidence only."
            ),
            "score_context": score_context,
            "latest_analysis": latest_analysis,
            "external_search": search_context.model_dump(),
        }
        chat_messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        chat_messages.append(
            {
                "role": "system",
                "content": "Grounding context:\n"
                + json.dumps(context_payload, ensure_ascii=True, sort_keys=True),
            }
        )
        transcript = self._conversation_transcript(messages)
        if transcript:
            chat_messages.append({"role": "user", "content": transcript})
        else:
            chat_messages.append(
                {
                    "role": "user",
                    "content": "Summarize this lead and recommend the next best action.",
                }
            )
        return chat_messages

    def _build_web_search_tool_def(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": (
                    "Search the live web for up-to-date information about a company, "
                    "industry, topic, or competitor. Use this when the user asks about "
                    "recent news, current market position, or specific company facts "
                    "that may not be in the stored CRM context."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query to look up on the web",
                        }
                    },
                    "required": ["query"],
                },
            },
        }

    def _execute_web_search_tool(self, query: str, *, settings: Settings) -> str:
        """Execute a SerpAPI web search for an LLM tool call. Returns formatted text."""
        if not query.strip():
            return "No query provided for web search."
        try:
            from app.modules.provider_serpapi.client import SerpApiClient
            from app.modules.provider_serpapi.engines.web_search import (
                build_web_search_params,
                run_web_search,
            )

            client = SerpApiClient()
            params = build_web_search_params(
                query=query,
                hl="en",
                gl="us",
                google_domain="google.com",
                num=settings.llm_web_search_max_results,
            )
            result = run_web_search(client, params=params)
            if not result.ok or not result.payload:
                return f"Web search for '{query}' returned no results."
            organic = result.payload.get("organic_results", [])
            if not organic:
                return f"No web results found for: {query}"
            lines = [f"Web search results for: {query}", ""]
            for i, item in enumerate(organic[: settings.llm_web_search_max_results], 1):
                title = item.get("title", "")
                link = item.get("link", "")
                snippet = item.get("snippet", "")
                lines.append(f"{i}. {title}")
                if link:
                    lines.append(f"   URL: {link}")
                if snippet:
                    lines.append(f"   {snippet}")
                lines.append("")
            return "\n".join(lines)
        except Exception as exc:
            logger.warning(
                "assistant.web_search_tool.failed query=%s error=%s",
                query,
                exc,
                exc_info=False,
            )
            return f"Web search failed: {exc}"

    def _stream_with_openai(
        self,
        *,
        settings: Settings,
        llm_messages: list[dict[str, str]],
    ) -> Iterator[str]:
        offer_tool = settings.enable_llm_web_search and settings.has_serpapi_configured
        request_body: dict[str, Any] = {
            "model": settings.openai_model,
            "messages": llm_messages,
            "stream": True,
        }
        if offer_tool:
            request_body["tools"] = [self._build_web_search_tool_def()]
            request_body["tool_choice"] = "auto"

        with httpx.Client(
            timeout=httpx.Timeout(60.0, connect=10.0),
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
        ) as client:
            accumulated_tool_args = ""
            tool_call_name = ""
            tool_call_id = ""
            finish_reason: str | None = None

            with client.stream(
                "POST",
                f"{settings.openai_base_url.rstrip('/')}/chat/completions",
                json=request_body,
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        break
                    try:
                        payload = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    choices = payload.get("choices")
                    if not choices:
                        err = payload.get("error")
                        if err:
                            raise ServiceUnavailableError(
                                str(err.get("message", "OpenAI streaming failed."))
                            )
                        continue
                    choice = choices[0]
                    finish_reason = choice.get("finish_reason") or finish_reason
                    delta = choice.get("delta", {})
                    content = delta.get("content")
                    if isinstance(content, str) and content:
                        yield content
                    # Accumulate tool_call fragments
                    tool_calls = delta.get("tool_calls")
                    if tool_calls:
                        for tc in tool_calls:
                            if tc.get("id"):
                                tool_call_id = tc["id"]
                            func = tc.get("function", {})
                            if func.get("name"):
                                tool_call_name = func["name"]
                            args_frag = func.get("arguments", "")
                            if isinstance(args_frag, str):
                                accumulated_tool_args += args_frag

            # If the LLM chose to call web_search, execute it and continue
            if finish_reason == "tool_calls" and tool_call_name == "web_search":
                try:
                    args = json.loads(accumulated_tool_args) if accumulated_tool_args else {}
                except json.JSONDecodeError:
                    args = {}
                query = args.get("query", "")
                tool_result = self._execute_web_search_tool(query, settings=settings)

                follow_up_messages = list(llm_messages) + [
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": tool_call_id,
                                "type": "function",
                                "function": {
                                    "name": "web_search",
                                    "arguments": accumulated_tool_args,
                                },
                            }
                        ],
                    },
                    {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": tool_result,
                    },
                ]
                with client.stream(
                    "POST",
                    f"{settings.openai_base_url.rstrip('/')}/chat/completions",
                    json={
                        "model": settings.openai_model,
                        "messages": follow_up_messages,
                        "stream": True,
                    },
                ) as response2:
                    response2.raise_for_status()
                    for line in response2.iter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data = line[6:]
                        if data.strip() == "[DONE]":
                            break
                        try:
                            payload = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        choices = payload.get("choices")
                        if not choices:
                            continue
                        delta = choices[0].get("delta", {})
                        content = delta.get("content")
                        if isinstance(content, str) and content:
                            yield content

    def _stream_with_ollama(
        self,
        *,
        settings: Settings,
        llm_messages: list[dict[str, str]],
    ) -> Iterator[str]:
        with httpx.Client(timeout=httpx.Timeout(45.0, connect=10.0)) as client:
            with client.stream(
                "POST",
                f"{settings.ollama_base_url.rstrip('/')}/api/chat",
                json={
                    "model": settings.ollama_model,
                    "messages": llm_messages,
                    "stream": True,
                },
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    message = chunk.get("message", {})
                    token = message.get("content", "")
                    if token:
                        yield token
                    if chunk.get("done"):
                        break
