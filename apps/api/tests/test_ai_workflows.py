from __future__ import annotations

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.modules.ai_analysis.models import AIAnalysisSnapshot, PromptTemplate, ServiceRecommendation
from app.modules.ai_analysis.schemas import LeadScoreContext
from app.modules.ai_analysis.service import AIAnalysisService
from app.modules.leads.models import Lead
from app.modules.outreach.models import OutreachMessage
from app.modules.outreach.schemas import OutreachGenerateRequest, OutreachMessageUpdateRequest
from app.modules.outreach.service import OutreachGenerationService
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


def test_ai_analysis_persists_and_reuses_snapshot() -> None:
    session_factory = _build_session_factory()
    with session_factory() as db:
        workspace, user, lead = _seed(db)
        service = AIAnalysisService()
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

        service = AIAnalysisService()
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


def test_ai_analysis_falls_back_to_valid_payload_when_adapter_output_is_invalid() -> None:
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


def test_outreach_generation_versions_messages_by_tone_and_regeneration() -> None:
    session_factory = _build_session_factory()
    with session_factory() as db:
        workspace, user, lead = _seed(db)
        analysis_service = AIAnalysisService()
        outreach_service = OutreachGenerationService()
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
