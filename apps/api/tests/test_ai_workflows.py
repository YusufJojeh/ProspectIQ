from __future__ import annotations

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.core.errors import ServiceUnavailableError
from app.modules.ai_analysis.adapters import FallbackAnalysisBuilder
from app.modules.ai_analysis.models import AIAnalysisSnapshot, PromptTemplate, ServiceRecommendation
from app.modules.ai_analysis.schemas import LeadAnalysisInput, LeadScoreContext
from app.modules.ai_analysis.service import AIAnalysisService
from app.modules.leads.models import Lead
from app.modules.outreach.models import OutreachMessage
from app.modules.outreach.schemas import OutreachGenerateRequest, OutreachMessageUpdateRequest
from app.modules.outreach.service import OutreachGenerationService
from app.modules.search_jobs import models as _search_job_models  # noqa: F401
from app.modules.users.models import User, Workspace
from app.shared.dto.lead_facts import NormalizedLeadFacts
from app.shared.enums.jobs import OutreachTone


def _build_session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session
    )


def _seed(db: Session) -> tuple[Workspace, User, Lead]:
    workspace = Workspace(name="LeadScope Workspace")
    db.add(workspace)
    db.commit()
    db.refresh(workspace)

    user = User(
        workspace_id=workspace.id,
        email="admin@example.com",
        full_name="Admin User",
        hashed_password="hashed",
        role="admin",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    template = PromptTemplate(
        workspace_id=workspace.id,
        name="Default lead analysis",
        template_text="Use stored facts only.",
        is_active=True,
        created_by_user_id=user.id,
    )
    db.add(template)

    lead = Lead(
        workspace_id=workspace.id,
        company_name="Acme Dental",
        category="Dentist",
        city="Istanbul",
        review_count=12,
        rating=4.4,
        website_domain="acmedental.example",
        website_url="https://acmedental.example",
        data_completeness=0.78,
        data_confidence=0.82,
        has_website=True,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return workspace, user, lead


class InvalidAdapter:
    def analyze(self, payload: object) -> dict[str, object]:
        return {"summary": "invalid"}


class ValidAdapter:
    def analyze(self, payload: LeadAnalysisInput) -> dict[str, object]:
        company_name = payload.local_business.company_name
        return {
            "summary": f"{company_name} has enough evidence for an assistive review.",
            "weaknesses": ["Website conversion details are still limited."],
            "opportunities": ["Run a focused visibility audit."],
            "recommended_services": ["Local SEO Sprint", "GBP Optimization"],
            "outreach_subject": f"Quick ideas for {company_name}",
            "outreach_message": f"Hi {company_name}, we found a few evidence-backed opportunities.",
            "confidence": 0.78,
        }


class ServiceCatalogAwareAdapter:
    def analyze(self, payload: LeadAnalysisInput) -> dict[str, object]:
        company_name = payload.local_business.company_name
        services = list(payload.allowed_service_catalog[:2]) or ["Local SEO Sprint"]
        return {
            "summary": f"{company_name} has a scoped service opportunity.",
            "weaknesses": ["The visible demand signals need follow-up."],
            "opportunities": ["Match outreach to the highest-ranked workspace service."],
            "recommended_services": services,
            "outreach_subject": f"Service ideas for {company_name}",
            "outreach_message": f"Hi {company_name}, these services align with your current signals.",
            "confidence": 0.74,
            "recommended_tone": "consultative",
        }


def test_ai_analysis_persists_and_reuses_snapshot() -> None:
    session_factory = _build_session_factory()
    with session_factory() as db:
        workspace, user, lead = _seed(db)
        service = AIAnalysisService(llm_client=ValidAdapter())
        facts = NormalizedLeadFacts(
            company_name=lead.company_name,
            category=lead.category,
            city=lead.city,
            website_url=lead.website_url,
            website_domain=lead.website_domain,
            review_count=lead.review_count,
            rating=lead.rating,
            data_completeness=lead.data_completeness,
            data_confidence=lead.data_confidence,
            has_website=lead.has_website,
            visibility_confidence=0.4,
            visibility_source="web_search",
        )
        score_context = LeadScoreContext(total_score=68, band="medium", qualified=True)

        first_snapshot, first_result = service.analyze(
            db,
            workspace_id=workspace.id,
            lead=lead,
            facts=facts,
            created_by_user_id=user.id,
            score_context=score_context,
        )
        second_snapshot, second_result = service.analyze(
            db,
            workspace_id=workspace.id,
            lead=lead,
            facts=facts,
            created_by_user_id=user.id,
            score_context=score_context,
        )

        assert "Acme Dental" in first_result.summary
        assert first_result.recommended_services
        assert first_snapshot.id == second_snapshot.id
        assert first_result == second_result
        assert db.scalar(select(func.count(AIAnalysisSnapshot.id))) == 1
        assert db.scalar(select(func.count(ServiceRecommendation.id))) == len(
            first_result.recommended_services
        )

        latest = service.get_latest_for_lead(
            db,
            workspace_id=workspace.id,
            lead_public_id=lead.public_id,
        )

        assert latest.snapshot is not None
        assert latest.snapshot.public_id == first_snapshot.public_id
        assert latest.snapshot.analysis.summary == first_result.summary
        assert len(latest.snapshot.service_recommendations) == len(
            first_result.recommended_services
        )


def test_ai_analysis_creates_default_prompt_template_when_missing() -> None:
    session_factory = _build_session_factory()
    with session_factory() as db:
        workspace, user, lead = _seed(db)
        db.query(PromptTemplate).delete()
        db.commit()

        service = AIAnalysisService(llm_client=ValidAdapter())
        facts = NormalizedLeadFacts(
            company_name=lead.company_name,
            category=lead.category,
            city=lead.city,
            website_url=lead.website_url,
            website_domain=lead.website_domain,
            review_count=lead.review_count,
            rating=lead.rating,
            data_completeness=lead.data_completeness,
            data_confidence=lead.data_confidence,
            has_website=lead.has_website,
            visibility_confidence=0.4,
            visibility_source="web_search",
        )

        snapshot, result = service.analyze(
            db,
            workspace_id=workspace.id,
            lead=lead,
            facts=facts,
            created_by_user_id=user.id,
        )

        assert snapshot.prompt_template_id is not None
        assert result.summary
        assert db.scalar(select(func.count(PromptTemplate.id))) == 1


def test_ai_analysis_uses_explicit_fallback_client_when_primary_output_is_invalid() -> None:
    session_factory = _build_session_factory()
    with session_factory() as db:
        workspace, user, lead = _seed(db)
        service = AIAnalysisService(
            llm_client=InvalidAdapter(),
            fallback_client=FallbackAnalysisBuilder(),
        )
        facts = NormalizedLeadFacts(
            company_name=lead.company_name,
            category=lead.category,
            city=lead.city,
            website_url=lead.website_url,
            website_domain=lead.website_domain,
            review_count=lead.review_count,
            rating=lead.rating,
            data_completeness=lead.data_completeness,
            data_confidence=lead.data_confidence,
            has_website=lead.has_website,
            official_website_found=True,
            official_website_source="maps_place",
            website_domain_matches_brand=True,
        )

        _, result = service.analyze(
            db,
            workspace_id=workspace.id,
            lead=lead,
            facts=facts,
            created_by_user_id=user.id,
        )

        assert "fallback path" in result.summary.casefold()
        assert result.recommended_services


def test_ai_analysis_fails_when_all_configured_providers_fail() -> None:
    session_factory = _build_session_factory()
    with session_factory() as db:
        workspace, user, lead = _seed(db)
        service = AIAnalysisService(llm_client=InvalidAdapter())

        facts = NormalizedLeadFacts(
            company_name=lead.company_name,
            category=lead.category,
            city=lead.city,
            website_url=lead.website_url,
            website_domain=lead.website_domain,
            review_count=lead.review_count,
            rating=lead.rating,
            data_completeness=lead.data_completeness,
            data_confidence=lead.data_confidence,
            has_website=lead.has_website,
        )

        try:
            service.analyze(
                db,
                workspace_id=workspace.id,
                lead=lead,
                facts=facts,
                created_by_user_id=user.id,
            )
        except ServiceUnavailableError as exc:
            assert "all configured providers" in exc.detail
        else:
            raise AssertionError("Expected ServiceUnavailableError when all providers fail.")


def test_sha256_deduplication_returns_existing_snapshot_not_new_one() -> None:
    session_factory = _build_session_factory()
    with session_factory() as db:
        workspace, user, lead = _seed(db)
        service = AIAnalysisService(llm_client=ValidAdapter())
        facts = NormalizedLeadFacts(
            company_name=lead.company_name,
            category=lead.category,
            city=lead.city,
            website_url=lead.website_url,
            website_domain=lead.website_domain,
            review_count=lead.review_count,
            rating=lead.rating,
            data_completeness=lead.data_completeness,
            data_confidence=lead.data_confidence,
            has_website=lead.has_website,
            visibility_confidence=0.5,
            visibility_source="web_search",
        )
        snap1, _ = service.analyze(db, workspace_id=workspace.id, lead=lead, facts=facts, created_by_user_id=user.id)
        snap2, _ = service.analyze(db, workspace_id=workspace.id, lead=lead, facts=facts, created_by_user_id=user.id)
        snap3, _ = service.analyze(db, workspace_id=workspace.id, lead=lead, facts=facts, created_by_user_id=user.id)

        assert snap1.id == snap2.id == snap3.id
        assert db.scalar(select(func.count(AIAnalysisSnapshot.id))) == 1


def test_fallback_analysis_builder_output_schema_is_valid() -> None:
    from app.modules.ai_analysis.adapters import FallbackAnalysisBuilder
    from app.modules.ai_analysis.prompt_builder import PromptBuilder
    from app.modules.ai_analysis.schemas import LeadScoreContext
    from app.modules.ai_analysis.validator import LLMOutputValidator

    session_factory = _build_session_factory()
    with session_factory() as db:
        workspace, user, lead = _seed(db)
        facts = NormalizedLeadFacts(
            company_name=lead.company_name,
            category=lead.category,
            city=lead.city,
            website_url=lead.website_url,
            website_domain=lead.website_domain,
            review_count=lead.review_count,
            rating=lead.rating,
            data_completeness=lead.data_completeness,
            data_confidence=lead.data_confidence,
            has_website=lead.has_website,
            visibility_confidence=0.5,
            visibility_source="web_search",
        )
        input_payload = PromptBuilder().build_input_payload(
            facts,
            score_context=LeadScoreContext(total_score=72, band="medium", qualified=True),
            allowed_service_catalog=["SEO", "PPC"],
        )
        raw = FallbackAnalysisBuilder().analyze(input_payload)
        result = LLMOutputValidator().validate(raw)

        assert result.summary
        assert result.recommended_services
        assert result.recommended_tone in (None, "formal", "friendly", "consultative", "short_pitch")
        assert 0.0 <= result.confidence <= 1.0


def test_service_recommendation_rank_ordering() -> None:
    from app.modules.ai_analysis.models import WorkspaceServiceCatalogItem

    session_factory = _build_session_factory()
    with session_factory() as db:
        workspace, user, lead = _seed(db)

        for rank, name in enumerate(["Reputation Management", "Local SEO", "PPC Ads"], start=1):
            db.add(
                WorkspaceServiceCatalogItem(
                    workspace_id=workspace.id,
                    service_name=name,
                    is_active=True,
                    rank_order=rank,
                )
            )
        db.commit()

        service = AIAnalysisService(llm_client=ServiceCatalogAwareAdapter())
        facts = NormalizedLeadFacts(
            company_name=lead.company_name,
            category=lead.category,
            city=lead.city,
            website_url=lead.website_url,
            website_domain=lead.website_domain,
            review_count=lead.review_count,
            rating=lead.rating,
            data_completeness=lead.data_completeness,
            data_confidence=lead.data_confidence,
            has_website=lead.has_website,
            visibility_confidence=0.5,
            visibility_source="web_search",
        )
        _, result = service.analyze(
            db,
            workspace_id=workspace.id,
            lead=lead,
            facts=facts,
            created_by_user_id=user.id,
        )

        assert result.recommended_services
        for service_name in result.recommended_services:
            assert service_name in {"Reputation Management", "Local SEO", "PPC Ads"}


def test_outreach_generation_versions_messages_by_tone_and_regeneration() -> None:
    session_factory = _build_session_factory()
    with session_factory() as db:
        workspace, user, lead = _seed(db)
        analysis_service = AIAnalysisService(llm_client=ValidAdapter())
        outreach_service = OutreachGenerationService()
        outreach_service.analysis_service = AIAnalysisService(llm_client=ValidAdapter())
        facts = NormalizedLeadFacts(
            company_name=lead.company_name,
            category=lead.category,
            city=lead.city,
            website_url=lead.website_url,
            website_domain=lead.website_domain,
            review_count=lead.review_count,
            rating=lead.rating,
            data_completeness=lead.data_completeness,
            data_confidence=lead.data_confidence,
            has_website=lead.has_website,
            visibility_confidence=0.3,
            visibility_source="web_search",
        )

        snapshot, analysis = analysis_service.analyze(
            db,
            workspace_id=workspace.id,
            lead=lead,
            facts=facts,
            created_by_user_id=user.id,
        )
        first_message = outreach_service.generate(
            db,
            lead=lead,
            snapshot=snapshot,
            analysis=analysis,
            created_by_user_id=user.id,
            tone=OutreachTone.CONSULTATIVE,
        )
        second_message = outreach_service.generate(
            db,
            lead=lead,
            snapshot=snapshot,
            analysis=analysis,
            created_by_user_id=user.id,
            tone=OutreachTone.CONSULTATIVE,
        )
        regenerated = outreach_service.generate_for_lead(
            db,
            workspace_id=workspace.id,
            lead_public_id=lead.public_id,
            current_user=user,
            payload=OutreachGenerateRequest(tone=OutreachTone.FORMAL, regenerate=True),
        )

        assert first_message.subject == second_message.subject
        assert "Acme Dental" in first_message.message
        assert db.scalar(select(func.count(OutreachMessage.id))) == 2

        latest = outreach_service.get_latest_for_lead(
            db,
            workspace_id=workspace.id,
            lead_public_id=lead.public_id,
        )

        assert latest.message is not None
        assert latest.message.public_id == regenerated.public_id
        assert latest.message.tone == OutreachTone.FORMAL
        assert latest.message.version_number == 2
        assert latest.message.has_manual_edits is False

        updated = outreach_service.update_draft(
            db,
            workspace_id=workspace.id,
            message_public_id=latest.message.public_id,
            payload=OutreachMessageUpdateRequest(
                subject="Quick idea for Acme Dental",
                message="We found two visibility opportunities worth fixing first.",
            ),
            current_user=user,
        )

        assert updated.subject == "Quick idea for Acme Dental"
        assert updated.message == "We found two visibility opportunities worth fixing first."
        assert updated.generated_subject == regenerated.generated_subject
        assert updated.has_manual_edits is True
