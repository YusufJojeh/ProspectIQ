from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import Any, Literal, cast

from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.modules.crm.repository import CrmRepository
from app.modules.crm.schemas import ActivityCreateRequest, ActivityType
from app.modules.crm.service import CrmService
from app.modules.knowledge.constants import (
    CASE_STUDIES,
    COLLECTION_TYPES,
    INDUSTRY_PLAYBOOKS,
    OBJECTIONS,
    PORTFOLIO,
    SALES_PLAYBOOKS,
)
from app.modules.knowledge.matching import CapabilityMatcher
from app.modules.knowledge.service import KnowledgeService
from app.modules.leads.models import Lead
from app.modules.leads.repository import LeadsRepository
from app.modules.leads.schemas import LeadNoteCreateRequest, LeadStatusUpdateRequest
from app.modules.leads.service import LeadsService
from app.modules.outreach.models import OutreachMessage
from app.modules.outreach.quality_guard import GuardReport, OutreachQualityGuard
from app.modules.outreach.schemas import OutreachGenerateRequest, OutreachMessageUpdateRequest
from app.modules.outreach.send_gateway import (
    CHANNEL_EMAIL,
    CHANNEL_LINKEDIN,
    CHANNEL_WHATSAPP,
    STATUS_SENT,
    ExternalSendGateway,
    SendRequest,
)
from app.modules.outreach.service import OutreachGenerationService
from app.modules.proposals.brands import get_brand
from app.modules.proposals.pricing import ground_milestone_amounts
from app.modules.proposals.service import ProposalService
from app.modules.research.agent_loop import ResearchAgentLoop
from app.modules.research.repository import ResearchRepository
from app.modules.research.tools import ResearchToolExecutor
from app.modules.users.models import User
from app.shared.enums.jobs import LeadStatus, OutreachTone

_ResearchDepth = Literal["quick", "standard", "deep"]


def _coerce_depth(value: Any, default: _ResearchDepth) -> _ResearchDepth:
    if value in {"quick", "standard", "deep"}:
        return cast(_ResearchDepth, value)
    return default

logger = logging.getLogger(__name__)

# Straight pass-through to the existing research tool executor -- these names
# are identical between the two registries, so there is no wrapping logic to
# duplicate, only delegation.
_DELEGATED_TO_RESEARCH_EXECUTOR = frozenset(
    {
        "search_web_tavily",
        "search_google_serpapi",
        "crawl_company_site",
        "crawl_reviews",
        "get_existing_evidence",
        "get_previous_research",
        "get_icp_profile",
        "compare_evidence",
    }
)


class AgentToolExecutor:
    """Executes READ/RESEARCH tool calls immediately, and (separately) builds
    non-mutating previews for WRITE_PROPOSAL/ACTION tools plus performs the
    actual domain mutation once an AgentActionGate has approved one.

    READ/RESEARCH tools reuse ResearchToolExecutor verbatim wherever the tool
    name is identical; nothing about search/crawl/evidence logic is
    reimplemented here. WRITE tools call the existing domain services
    (LeadsService, OutreachGenerationService, CrmService) -- this class never
    contains business logic of its own, only translation between a tool call
    and the existing service method for it.
    """

    def __init__(
        self,
        db: Session,
        *,
        workspace_id: int,
        lead: Lead | None,
        current_user: User,
    ) -> None:
        self.db = db
        self.workspace_id = workspace_id
        self.lead = lead
        self.current_user = current_user
        self.research_executor = (
            ResearchToolExecutor(db, workspace_id=workspace_id, lead=lead)
            if lead is not None
            else None
        )
        self.leads_repository = LeadsRepository()
        self.leads_service = LeadsService()
        self.outreach_service = OutreachGenerationService()
        self.crm_repository = CrmRepository()
        self.crm_service = CrmService()
        self.research_repository = ResearchRepository()
        self.knowledge_service = KnowledgeService()
        self.capability_matcher = CapabilityMatcher()
        self.quality_guard = OutreachQualityGuard()
        self.send_gateway = ExternalSendGateway()
        # What this run actually retrieved. The outreach guard checks the
        # draft against THIS, not against the whole knowledge base: a claim
        # the run never read is a claim the model supplied from memory.
        self.retrieved_grounding: list[str] = []
        self.rag_queries_performed = 0
        #: Set by the runtime so drafted documents can name the run that
        #: produced them.
        self.run_public_id: str | None = None
        self.proposal_service = ProposalService()

    @property
    def searches_performed(self) -> int:
        return self.research_executor.searches_performed if self.research_executor else 0

    @property
    def crawls_performed(self) -> int:
        return self.research_executor.crawls_performed if self.research_executor else 0

    @property
    def sources_gathered(self) -> int:
        return self.research_executor.sources_gathered if self.research_executor else 0

    def execute_rag(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Search the workspace's own sales knowledge.

        Note what is absent from the arguments: there is no workspace, no user
        and no visibility parameter for the model to supply. Tenancy and
        visibility come from the run and the acting user, so a prompt-injected
        model asking for another workspace's case studies has no field in
        which to ask.

        A RAG search does not require a lead: the sales copilot may answer
        "what have we done in dental?" with no lead bound to the run.
        """
        if name == "match_capabilities_to_lead":
            return self._match_capabilities()

        # Each of these is the same governed retrieval with a different
        # collection filter applied by the BACKEND, so the model cannot ask
        # for case studies and be served pricing guidance, or vice versa.
        query_field, forced_types = {
            "search_sales_knowledge": ("query", None),
            "get_relevant_case_studies": ("situation", (CASE_STUDIES, PORTFOLIO)),
            "get_sales_playbook": (
                "topic",
                (SALES_PLAYBOOKS, INDUSTRY_PLAYBOOKS, OBJECTIONS),
            ),
        }.get(name, ("", ()))
        if not query_field:
            return {"error": f"Unknown knowledge tool '{name}'."}
        query = str(arguments.get(query_field) or "").strip()
        if not query:
            return {"error": "A non-empty 'query' is required."}

        if forced_types is None:
            raw_types = arguments.get("collection_types")
            collection_types = (
                [
                    value
                    for value in raw_types
                    if isinstance(value, str) and value in COLLECTION_TYPES
                ]
                if isinstance(raw_types, list)
                else None
            )
        else:
            collection_types = list(forced_types)
        limit = arguments.get("limit")
        try:
            response = self.knowledge_service.search(
                self.db,
                workspace_id=self.workspace_id,
                query=query,
                user_id=self.current_user.id,
                user_role=self.current_user.role,
                collection_types=collection_types or None,
                limit=int(limit) if isinstance(limit, int) else None,
            )
        except ApiError as exc:
            return {"error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.warning("agents.rag.failed error=%s", exc)
            return {"error": str(exc)}

        self.rag_queries_performed += 1
        self.retrieved_grounding.extend(item.excerpt for item in response.results)
        return response.model_dump(mode="json")

    def _match_capabilities(self) -> dict[str, Any]:
        """Opportunities come from the Evidence Graph, capabilities from RAG.

        The model receives a finished match: which problems this lead
        demonstrably has, with the graph's own confidence, and which of our
        documents support addressing them. It chooses none of that.
        """
        if self.lead is None:
            return {"error": "This run has no lead bound to it."}
        graph = self.leads_service.evidence_graph(
            self.db, self.workspace_id, self.lead.public_id
        )
        matches = self.capability_matcher.match(
            self.db,
            workspace_id=self.workspace_id,
            graph=graph,
            user_id=self.current_user.id,
            user_role=self.current_user.role,
        )
        self.rag_queries_performed += 1
        for match in matches:
            for citation in (*match.capabilities, *match.proof):
                excerpt_text = citation.get("excerpt")
                if isinstance(excerpt_text, str):
                    self.retrieved_grounding.append(excerpt_text)
        return {
            "lead_id": self.lead.public_id,
            "evidence_confidence": graph.evidence_confidence,
            "research_coverage": graph.research_coverage,
            "matches": [
                {
                    "opportunity": match.opportunity_key,
                    "label": match.opportunity_label,
                    "basis_claim_type": match.basis_claim_type,
                    "basis_value": match.basis_value,
                    "confidence": match.confidence,
                    "rationale": match.rationale,
                    "capabilities": match.capabilities,
                    "proof": match.proof,
                }
                for match in matches
            ],
            "match_count": len(matches),
        }

    def execute_read_or_research(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if self.lead is None or self.research_executor is None:
            return {"error": "This run has no lead bound to it."}
        try:
            handler = self._read_handlers().get(name)
            if handler is not None:
                return handler(arguments)
            if name in _DELEGATED_TO_RESEARCH_EXECUTOR:
                return self.research_executor.execute(name, arguments)
            return {"error": f"Unknown read/research tool '{name}'."}
        except Exception as exc:  # noqa: BLE001
            logger.warning("agents.tool.failed name=%s error=%s", name, exc)
            return {"error": str(exc)}

    def _read_handlers(self) -> dict[str, Callable[[dict[str, Any]], dict[str, Any]]]:
        return {
            "get_lead_context": self._get_lead_context,
            "get_evidence_graph": self._get_evidence_graph,
            "get_score_breakdown": self._get_score_breakdown,
            "get_research_history": self._get_research_history,
            "get_delta_changes": self._get_delta_changes,
            "get_outreach_history": self._get_outreach_history,
            "get_lead_notes": self._get_lead_notes,
            "get_lead_activity": self._get_lead_activity,
            "get_contact_channels": self._get_contact_channels,
            "get_service_catalog": self._get_service_catalog,
            "refresh_lead_research": self._refresh_lead_research,
        }

    def _get_lead_context(self, _arguments: dict[str, Any]) -> dict[str, Any]:
        lead = self.lead
        assert lead is not None
        return {
            "lead_id": lead.public_id,
            "company_name": lead.company_name,
            "city": lead.city,
            "category": lead.category,
            "website_url": lead.website_url,
            "status": lead.status,
            "data_completeness": lead.data_completeness,
            "tags": (lead.enrichments or {}).get("tags", []),
        }

    def _get_evidence_graph(self, arguments: dict[str, Any]) -> dict[str, Any]:
        assert self.research_executor is not None
        return self.research_executor.execute("compare_evidence", arguments)

    def _get_score_breakdown(self, arguments: dict[str, Any]) -> dict[str, Any]:
        assert self.research_executor is not None
        return self.research_executor.execute("get_lead_score_breakdown", arguments)

    def _get_research_history(self, _arguments: dict[str, Any]) -> dict[str, Any]:
        assert self.lead is not None
        response = self.leads_service.research_history(
            self.db, self.workspace_id, self.lead.public_id, page=1, per_page=10
        )
        return response.model_dump(mode="json")

    def _get_delta_changes(self, _arguments: dict[str, Any]) -> dict[str, Any]:
        assert self.lead is not None
        response = self.leads_service.research_history(
            self.db, self.workspace_id, self.lead.public_id, page=1, per_page=10
        )
        changes = [
            change.model_dump(mode="json") for item in response.items for change in item.changes
        ]
        return {"changes": changes, "count": len(changes)}

    def _get_outreach_history(self, _arguments: dict[str, Any]) -> dict[str, Any]:
        assert self.lead is not None
        message = self.outreach_service.repository.get_latest_by_lead(self.db, self.lead.id)
        if message is None:
            return {"message": None}
        return {
            "message": {
                "public_id": message.public_id,
                "subject": message.edited_subject or message.subject,
                "tone": message.tone,
                "outreach_status": message.outreach_status,
                "version_number": message.version_number,
                "created_at": message.created_at.isoformat(),
            }
        }

    def _refresh_lead_research(self, arguments: dict[str, Any]) -> dict[str, Any]:
        assert self.lead is not None
        depth = _coerce_depth(arguments.get("depth"), "quick")
        result = ResearchAgentLoop().run(
            self.db, workspace_id=self.workspace_id, lead=self.lead, depth=depth
        )
        return result.model_dump(mode="json")

    # -- WRITE_PROPOSAL / ACTION: preview builders (no mutation) -----------

    def build_preview(
        self, name: str, arguments: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any], str, str]:
        """Returns (preview, payload, resource_type, resource_id). Must never
        touch the database beyond read-only lookups used to make the preview
        accurate (e.g. showing the lead's current status before a change).
        """
        assert self.lead is not None
        builders: dict[str, Callable[[dict[str, Any]], tuple[dict[str, Any], dict[str, Any], str, str]]] = {
            "save_outreach_draft": self._preview_save_outreach_draft,
            "add_lead_note": self._preview_add_lead_note,
            "create_follow_up": self._preview_create_follow_up,
            "create_lead_task": self._preview_create_lead_task,
            "update_lead_stage": self._preview_update_lead_stage,
            "update_lead_tags": self._preview_update_lead_tags,
            "request_deep_research": self._preview_request_deep_research,
            "draft_proposal": self._preview_draft_proposal,
            "send_email": partial(self._preview_send, "send_email"),
            "send_whatsapp": partial(self._preview_send, "send_whatsapp"),
            "send_linkedin_message": partial(self._preview_send, "send_linkedin_message"),
        }
        builder = builders.get(name)
        if builder is None:
            raise ApiError(f"Tool '{name}' has no write-proposal preview builder.")
        return builder(arguments)

    def _preview_save_outreach_draft(
        self, arguments: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any], str, str]:
        assert self.lead is not None
        message = self.outreach_service.repository.get_latest_by_lead(self.db, self.lead.id)
        current = (
            {
                "subject": message.edited_subject or message.subject,
                "message": message.edited_message or message.message,
            }
            if message is not None
            else None
        )
        payload = {"subject": arguments["subject"], "message": arguments["message"]}
        preview = {"lead_id": self.lead.public_id, "current": current, "proposed": payload}
        resource_id = message.public_id if message is not None else self.lead.public_id
        return preview, payload, "outreach_message", resource_id

    def _preview_add_lead_note(
        self, arguments: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any], str, str]:
        assert self.lead is not None
        payload = {"note": arguments["note"]}
        preview = {"lead_id": self.lead.public_id, "note": arguments["note"]}
        return preview, payload, "lead_note", self.lead.public_id

    def _preview_create_follow_up(
        self, arguments: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any], str, str]:
        return self._preview_activity(arguments, activity_type=ActivityType.FOLLOW_UP.value)

    def _preview_create_lead_task(
        self, arguments: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any], str, str]:
        return self._preview_activity(arguments, activity_type=ActivityType.FOLLOW_UP.value)

    def _preview_activity(
        self, arguments: dict[str, Any], *, activity_type: str
    ) -> tuple[dict[str, Any], dict[str, Any], str, str]:
        assert self.lead is not None
        due_in_days = int(arguments.get("due_in_days") or 0)
        due_at = (datetime.now(tz=UTC) + timedelta(days=due_in_days)).isoformat()
        payload = {
            "activity_type": activity_type,
            "title": arguments["title"],
            "note": arguments.get("note"),
            "due_at": due_at,
        }
        preview = {"lead_id": self.lead.public_id, **payload}
        return preview, payload, "crm_activity", self.lead.public_id

    def _preview_update_lead_stage(
        self, arguments: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any], str, str]:
        assert self.lead is not None
        payload = {"status": arguments["status"], "note": arguments.get("note")}
        preview = {"lead_id": self.lead.public_id, "from_status": self.lead.status, **payload}
        return preview, payload, "lead", self.lead.public_id

    def _preview_update_lead_tags(
        self, arguments: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any], str, str]:
        assert self.lead is not None
        existing = list((self.lead.enrichments or {}).get("tags", []))
        payload = {"tags": arguments["tags"]}
        preview = {"lead_id": self.lead.public_id, "current_tags": existing, "add_tags": arguments["tags"]}
        return preview, payload, "lead", self.lead.public_id

    def _preview_request_deep_research(
        self, arguments: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any], str, str]:
        assert self.lead is not None
        depth = arguments.get("depth") or "standard"
        payload = {"depth": depth}
        preview = {"lead_id": self.lead.public_id, "depth": depth}
        return preview, payload, "research_run", self.lead.public_id

    def _preview_draft_proposal(
        self, arguments: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any], str, str]:
        """Prices are the one thing in a proposal a model must not invent.

        Each amount is kept only if it is backed by pricing this run actually
        retrieved; anything else reaches the draft unpriced, and the document
        cannot be marked ready until a person prices it.
        """
        assert self.lead is not None
        brand = get_brand(str(arguments.get("brand") or ""))
        if brand is None:
            raise ApiError("Unknown proposal brand.")
        currency = str(arguments.get("currency") or brand.default_currency).strip().upper()
        if len(currency) != 3 or not currency.isalpha():
            raise ApiError("currency must be a 3-letter ISO code such as USD.")
        raw_lines = [item for item in arguments.get("milestones") or [] if isinstance(item, dict)]
        grounding = ground_milestone_amounts(
            [item.get("amount") for item in raw_lines], self.retrieved_grounding
        )
        milestones: list[dict[str, Any]] = [
            {
                "title": str(item.get("title") or "").strip(),
                "description": str(item.get("description") or "").strip(),
                "amount_minor": amount,
            }
            for item, amount in zip(raw_lines, grounding.amounts_minor, strict=True)
        ]
        payload = {
            "brand": brand.key,
            "language": arguments.get("language") or "en",
            "title": str(arguments["title"]).strip(),
            "outcome": str(arguments.get("outcome") or "").strip() or None,
            "currency": currency,
            "validity_days": arguments.get("validity_days") or brand.validity_days,
            "milestones": milestones,
            "commercial_notes": str(arguments.get("commercial_notes") or "").strip() or None,
            "pricing_basis": str(arguments.get("pricing_basis") or "").strip() or None,
            "source_agent_run_id": self.run_public_id,
        }
        total_minor = sum(amount or 0 for amount in grounding.amounts_minor)
        preview = {
            "lead_id": self.lead.public_id,
            "brand": brand.name,
            "title": payload["title"],
            "client_company": self.lead.company_name,
            "currency": currency,
            "milestones": [
                f"{line['title']} — "
                + (f"{currency} {amount / 100:,.2f}" if amount is not None else "unpriced")
                for line, amount in zip(milestones, grounding.amounts_minor, strict=True)
            ],
            "total": f"{currency} {total_minor / 100:,.2f}",
            "pricing_status": grounding.status,
            "pricing_basis": payload["pricing_basis"],
        }
        return preview, payload, "proposal", self.lead.public_id

    def _get_lead_notes(self, _arguments: dict[str, Any]) -> dict[str, Any]:
        assert self.lead is not None
        rows = self.leads_repository.list_notes(self.db, self.lead.id)
        return {
            "notes": [
                {
                    "note_id": note.public_id,
                    "note": note.note,
                    "author": author_name,
                    "created_at": note.created_at.isoformat(),
                }
                for note, _author_public_id, author_name in rows[:20]
            ],
            "count": len(rows),
        }

    def _get_lead_activity(self, _arguments: dict[str, Any]) -> dict[str, Any]:
        assert self.lead is not None
        deal = self.crm_repository.get_open_deal_for_lead(
            self.db, workspace_id=self.workspace_id, lead_id=self.lead.id
        )
        if deal is None:
            return {"deal": None, "activities": [], "count": 0}
        activities = self.crm_repository.list_activities(self.db, deal.id)
        return {
            "deal": {"deal_id": deal.public_id, "status": deal.status},
            "activities": [
                {
                    "activity_id": activity.public_id,
                    "activity_type": activity.activity_type,
                    "title": activity.title,
                    "note": activity.note,
                    "due_at": activity.due_at.isoformat() if activity.due_at else None,
                    "completed_at": (
                        activity.completed_at.isoformat() if activity.completed_at else None
                    ),
                }
                for activity in activities[:20]
            ],
            "count": len(activities),
        }

    def _get_contact_channels(self, _arguments: dict[str, Any]) -> dict[str, Any]:
        """Read the evidenced contact channels, not a guess.

        The values come from the Evidence Graph's canonical facts, so a
        channel the agent suggests using is one the research actually found.
        """
        assert self.lead is not None
        graph = self.leads_service.evidence_graph(
            self.db, self.workspace_id, self.lead.public_id
        )
        wanted = {"contact_channels", "has_whatsapp", "website_url"}
        channels = [
            {
                "claim_type": fact.claim_type,
                "value": fact.value,
                "status": fact.status,
                "confidence": fact.confidence,
            }
            for group in graph.groups
            for fact in group.facts
            if fact.claim_type in wanted
        ]
        return {
            "lead_id": self.lead.public_id,
            "phone": self.lead.phone,
            "website_url": self.lead.website_url,
            "evidenced_channels": channels,
        }

    def _get_service_catalog(self, _arguments: dict[str, Any]) -> dict[str, Any]:
        """List what this workspace sells, from the knowledge store's own
        documents rather than from the model's assumptions."""
        documents = self.knowledge_service.list_documents(
            self.db,
            workspace_id=self.workspace_id,
            user_id=self.current_user.id,
            user_role=self.current_user.role,
        )
        catalog = [
            {
                "document_id": document.document_id,
                "title": document.title,
                "document_type": document.document_type,
                "industry": document.industry,
            }
            for document in documents
            if document.document_type in {"services", "capabilities"}
            and document.status == "ready"
        ]
        return {"services": catalog, "count": len(catalog)}

    # -- Auto-executing write tools (requires_approval=False) --------------

    def execute_auto_write(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        assert self.lead is not None
        if name != "draft_outreach":
            return {"error": f"'{name}' is not an auto-executing write tool."}
        try:
            tone = OutreachTone(arguments.get("tone") or "consultative")
            payload = OutreachGenerateRequest(
                tone=tone,
                regenerate=bool(arguments.get("regenerate", False)),
                language=arguments.get("language", "en"),
            )
            response = self.outreach_service.generate_for_lead(
                self.db,
                workspace_id=self.workspace_id,
                lead_public_id=self.lead.public_id,
                current_user=self.current_user,
                payload=payload,
            )
            result = response.model_dump(mode="json")
            result["quality"] = self._guard_draft(result).as_dict()
            return result
        except ApiError as exc:
            return {"error": exc.detail}

    def _guard_draft(self, draft: dict[str, Any]) -> GuardReport:
        """Check a generated draft before a human ever sees it.

        The report travels back to the model as part of the tool result, so a
        blocked draft is something the agent can fix in the next step rather
        than something a salesperson discovers after sending.
        """
        assert self.lead is not None
        body = ""
        subject: str | None = None
        for key in ("edited_body", "body"):
            value = draft.get(key)
            if isinstance(value, str) and value.strip():
                body = value
                break
        for key in ("edited_subject", "subject"):
            value = draft.get(key)
            if isinstance(value, str) and value.strip():
                subject = value
                break

        lead_terms = [
            term
            for term in (
                self.lead.company_name,
                self.lead.city,
                self.lead.category,
                self.lead.website_url,
                self.lead.phone,
            )
            if term
        ]
        return self.quality_guard.check(
            subject=subject,
            body=body,
            grounding=self.retrieved_grounding,
            lead_terms=lead_terms,
        )

    # -- Post-approval execution (never called before an AgentAction is
    # explicitly approved by AgentActionGate) ------------------------------

    def execute_action(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        assert self.lead is not None
        handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "save_outreach_draft": self._execute_save_outreach_draft,
            "add_lead_note": self._execute_add_lead_note,
            "create_follow_up": self._execute_create_activity,
            "create_lead_task": self._execute_create_activity,
            "update_lead_stage": self._execute_update_lead_stage,
            "update_lead_tags": self._execute_update_lead_tags,
            "request_deep_research": self._execute_request_deep_research,
            "draft_proposal": self._execute_draft_proposal,
            "send_email": self._execute_send,
            "send_whatsapp": self._execute_send,
            "send_linkedin_message": self._execute_send,
        }
        handler = handlers.get(tool_name)
        if handler is None:
            raise ApiError(f"Tool '{tool_name}' has no execution handler.")
        return handler(payload)


    # -- External send ----------------------------------------------------
    #
    # Both halves of the send path -- proposing and executing -- call
    # `ensure_enabled` independently. That is deliberate duplication: a
    # config change between proposal and approval must not let a pending
    # action execute against a rule that no longer permits it.

    _SEND_CHANNELS: dict[str, tuple[str, str]] = {
        "send_email": (CHANNEL_EMAIL, "to_email"),
        "send_whatsapp": (CHANNEL_WHATSAPP, "to_number"),
        "send_linkedin_message": (CHANNEL_LINKEDIN, "profile_url"),
    }

    def _resolve_send(
        self, name: str, arguments: dict[str, Any]
    ) -> tuple[str, str, OutreachMessage]:
        """(channel, destination, message) for a send tool call.

        The message is loaded from the database by its public id and checked
        to belong to THIS run's lead. The model supplies an id, never text:
        a human approves a stored draft they can read, not a body the model
        re-typed at send time.
        """
        assert self.lead is not None
        self.send_gateway.ensure_enabled()
        channel, destination_field = self._SEND_CHANNELS[name]
        destination = str(arguments.get(destination_field, "")).strip()
        if not destination:
            raise ApiError(f"'{destination_field}' is required to send.")
        message_id = str(arguments.get("outreach_message_id", "")).strip()
        message = self.outreach_service.repository.get_by_public_id(self.db, message_id)
        if message is None or message.lead_id != self.lead.id:
            raise ApiError("No outreach message with that id belongs to this lead.")
        return channel, destination, message

    def _preview_send(
        self, name: str, arguments: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any], str, str]:
        assert self.lead is not None
        channel, destination, message = self._resolve_send(name, arguments)
        subject = message.edited_subject or message.subject
        body = message.edited_message or message.message
        # The payload carries the exact text. It is hashed, shown to the
        # approver, and re-verified before execution, so the bytes a human
        # read are the bytes that would go out.
        payload = {
            "channel": channel,
            "destination": destination,
            "outreach_message_id": message.public_id,
            "subject": subject,
            "body": body,
        }
        preview = {
            "lead_id": self.lead.public_id,
            "irreversible": True,
            "channel": channel,
            "destination": destination,
            "subject": subject,
            "body": body,
            "delivery": (
                "No delivery transport is configured; approving this records the attempt "
                "without transmitting anything."
            ),
        }
        return preview, payload, "outreach_message", message.public_id

    def _execute_send(self, payload: dict[str, Any]) -> dict[str, Any]:
        assert self.lead is not None
        self.send_gateway.ensure_enabled()
        message = self.outreach_service.repository.get_by_public_id(
            self.db, str(payload.get("outreach_message_id", ""))
        )
        if message is None or message.lead_id != self.lead.id:
            raise ApiError("No outreach message with that id belongs to this lead.")
        result = self.send_gateway.send(
            SendRequest(
                channel=str(payload["channel"]),
                destination=str(payload["destination"]),
                subject=payload.get("subject"),
                body=str(payload["body"]),
                outreach_message_id=message.public_id,
            )
        )
        # Status only advances on a real delivery. Marking a draft "sent"
        # when nothing was transmitted would corrupt every downstream
        # reply-rate and follow-up decision that reads this column.
        if result.delivered:
            message.outreach_status = STATUS_SENT
            self.outreach_service.repository.save(self.db, message)
        return {
            "outreach_message_id": message.public_id,
            "outreach_status": message.outreach_status,
            **result.as_dict(),
        }

    def _execute_save_outreach_draft(self, payload: dict[str, Any]) -> dict[str, Any]:
        assert self.lead is not None
        message = self.outreach_service.repository.get_latest_by_lead(self.db, self.lead.id)
        if message is None:
            raise ApiError("Lead has no outreach draft to update yet.")
        response = self.outreach_service.update_draft(
            self.db,
            workspace_id=self.workspace_id,
            message_public_id=message.public_id,
            payload=OutreachMessageUpdateRequest(
                subject=payload["subject"], message=payload["message"]
            ),
            current_user=self.current_user,
        )
        return response.model_dump(mode="json")

    def _execute_add_lead_note(self, payload: dict[str, Any]) -> dict[str, Any]:
        assert self.lead is not None
        response = self.leads_service.create_note(
            self.db,
            self.workspace_id,
            self.lead.public_id,
            LeadNoteCreateRequest(note=payload["note"]),
            current_user=self.current_user,
        )
        return response.model_dump(mode="json")

    def _get_or_create_open_deal_public_id(self) -> str:
        assert self.lead is not None
        deal = self.crm_repository.get_open_deal_for_lead(
            self.db, workspace_id=self.workspace_id, lead_id=self.lead.id
        )
        if deal is not None:
            return deal.public_id
        created = self.crm_service.create_deal_from_lead(
            self.db,
            workspace_id=self.workspace_id,
            lead_id=self.lead.public_id,
            current_user=self.current_user,
            allow_duplicate_open=True,
        )
        return created.public_id

    def _execute_create_activity(self, payload: dict[str, Any]) -> dict[str, Any]:
        deal_public_id = self._get_or_create_open_deal_public_id()
        due_at = datetime.fromisoformat(payload["due_at"]) if payload.get("due_at") else None
        response = self.crm_service.create_activity(
            self.db,
            workspace_id=self.workspace_id,
            deal_id=deal_public_id,
            payload=ActivityCreateRequest(
                activity_type=ActivityType(payload["activity_type"]),
                title=payload["title"],
                note=payload.get("note"),
                due_at=due_at,
            ),
            current_user=self.current_user,
        )
        return response.model_dump(mode="json")

    def _execute_update_lead_stage(self, payload: dict[str, Any]) -> dict[str, Any]:
        assert self.lead is not None
        response = self.leads_service.update_status(
            self.db,
            self.workspace_id,
            self.lead.public_id,
            LeadStatusUpdateRequest(
                status=LeadStatus(payload["status"]), note=payload.get("note")
            ),
            current_user=self.current_user,
        )
        return response.model_dump(mode="json")

    def _execute_update_lead_tags(self, payload: dict[str, Any]) -> dict[str, Any]:
        assert self.lead is not None
        lead = self.leads_repository.get_by_id_for_workspace(
            self.db, workspace_id=self.workspace_id, lead_id=self.lead.id
        )
        if lead is None:
            raise ApiError("Lead was not found.")
        enrichments = dict(lead.enrichments or {})
        existing_tags = set(enrichments.get("tags", []))
        new_tags = sorted(existing_tags | set(payload["tags"]))
        enrichments["tags"] = new_tags
        lead.enrichments = enrichments
        self.leads_repository.save(self.db, lead)
        return {"lead_id": lead.public_id, "tags": new_tags}

    def _execute_draft_proposal(self, payload: dict[str, Any]) -> dict[str, Any]:
        assert self.lead is not None
        brand = get_brand(str(payload.get("brand") or ""))
        if brand is None:
            raise ApiError("Unknown proposal brand.")
        proposal = self.proposal_service.create(
            self.db,
            workspace_id=self.workspace_id,
            lead=self.lead,
            brand=brand,
            current_user=self.current_user,
            language=str(payload.get("language") or "en"),
            title=payload.get("title"),
            outcome=payload.get("outcome"),
            currency=payload.get("currency"),
            validity_days=payload.get("validity_days"),
            milestones=list(payload.get("milestones") or []),
            commercial_notes=payload.get("commercial_notes"),
            pricing_basis=payload.get("pricing_basis"),
            source_agent_run_id=payload.get("source_agent_run_id"),
        )
        response = self.proposal_service.to_response(self.db, proposal)
        return {
            "proposal_id": response.public_id,
            "number": response.number,
            "status": response.status,
            "total_minor": response.totals.total_minor,
            "currency": response.currency,
            "readiness_issues": response.readiness.issues,
        }

    def _execute_request_deep_research(self, payload: dict[str, Any]) -> dict[str, Any]:
        assert self.lead is not None
        depth = _coerce_depth(payload.get("depth"), "standard")
        result = ResearchAgentLoop().run(
            self.db, workspace_id=self.workspace_id, lead=self.lead, depth=depth
        )
        return result.model_dump(mode="json")


__all__ = ["AgentToolExecutor"]
