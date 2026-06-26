from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.modules.leads.models import Lead
from app.modules.leads.repository import LeadsRepository
from app.modules.leads.schemas import LeadSortOption
from app.modules.leads.service import LeadsService
from app.modules.scoring.models import LeadScore
from app.modules.search_jobs.models import SearchJob  # noqa: F401
from app.modules.users.models import User, Workspace


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


def test_lead_list_filters_support_score_owner_category_and_sorting() -> None:
    session_factory = _build_session_factory()
    with session_factory() as db:
        workspace = Workspace(name="LeadScope Workspace")
        db.add(workspace)
        db.commit()
        db.refresh(workspace)

        owner = User(
            workspace_id=workspace.id,
            email="owner@example.com",
            full_name="Owner User",
            hashed_password="hashed",
            role="agency_manager",
        )
        other = User(
            workspace_id=workspace.id,
            email="other@example.com",
            full_name="Other User",
            hashed_password="hashed",
            role="sales_user",
        )
        db.add_all([owner, other])
        db.commit()
        db.refresh(owner)
        db.refresh(other)

        first = Lead(
            workspace_id=workspace.id,
            company_name="Acme Dental",
            category="Dentist",
            city="Istanbul",
            review_count=30,
            rating=4.7,
            has_website=True,
            assigned_to_user_id=owner.id,
            status="qualified",
            data_completeness=0.85,
            data_confidence=0.8,
        )
        second = Lead(
            workspace_id=workspace.id,
            company_name="Beta Dental",
            category="Dentist",
            city="Ankara",
            review_count=9,
            rating=4.1,
            has_website=False,
            assigned_to_user_id=other.id,
            status="reviewed",
            data_completeness=0.55,
            data_confidence=0.7,
        )
        third = Lead(
            workspace_id=workspace.id,
            company_name="Gamma Salon",
            category="Salon",
            city="Istanbul",
            phone="+90 555 123 4567",
            email="owner@gammasalon.test",
            industry="Beauty services",
            ai_opener="Your booking flow could capture more high-intent clients.",
            review_count=55,
            rating=4.8,
            has_website=True,
            status="new",
            data_completeness=0.9,
            data_confidence=0.88,
        )
        db.add_all([first, second, third])
        db.commit()
        db.refresh(first)
        db.refresh(second)
        db.refresh(third)

        db.add_all(
            [
                LeadScore(
                    lead_id=first.id,
                    scoring_config_version_id=1,
                    total_score=81,
                    band="high",
                    qualified=True,
                ),
                LeadScore(
                    lead_id=second.id,
                    scoring_config_version_id=1,
                    total_score=58,
                    band="medium",
                    qualified=True,
                ),
                LeadScore(
                    lead_id=third.id,
                    scoring_config_version_id=1,
                    total_score=33,
                    band="not_qualified",
                    qualified=False,
                ),
            ]
        )
        db.commit()

        response = LeadsService().list_leads(
            db,
            workspace_id=workspace.id,
            page=1,
            page_size=20,
            status=None,
            search_job_id=None,
            has_website=True,
            q=None,
            city="Istanbul",
            band=None,
            category="Dentist",
            min_score=70,
            max_score=None,
            qualified=True,
            owner_user_id=owner.public_id,
            sort=LeadSortOption.SCORE_DESC,
        )

        assert response.pagination.total == 1
        assert response.items[0].company_name == "Acme Dental"
        assert response.items[0].latest_band == "high"
        assert response.items[0].assigned_to_user_public_id == owner.public_id

        sorted_response = LeadsService().list_leads(
            db,
            workspace_id=workspace.id,
            page=1,
            page_size=20,
            status=None,
            search_job_id=None,
            has_website=None,
            sort=LeadSortOption.REVIEWS_DESC,
        )

        assert [item.company_name for item in sorted_response.items][:2] == [
            "Gamma Salon",
            "Acme Dental",
        ]

        by_ids = LeadsService().list_leads(
            db,
            workspace_id=workspace.id,
            page=1,
            page_size=20,
            status=None,
            search_job_id=None,
            has_website=None,
            lead_public_ids=[first.public_id, third.public_id],
            sort=LeadSortOption.NEWEST,
        )

        assert by_ids.pagination.total == 2
        names = {item.company_name for item in by_ids.items}
        assert names == {"Acme Dental", "Gamma Salon"}

        category_search = LeadsService().list_leads(
            db,
            workspace_id=workspace.id,
            page=1,
            page_size=20,
            status=None,
            search_job_id=None,
            has_website=None,
            q="beauty",
            sort=LeadSortOption.NEWEST,
        )

        assert category_search.pagination.total == 1
        assert category_search.items[0].company_name == "Gamma Salon"

        ai_opener_search = LeadsService().list_leads(
            db,
            workspace_id=workspace.id,
            page=1,
            page_size=20,
            status=None,
            search_job_id=None,
            has_website=None,
            q="booking flow",
            sort=LeadSortOption.NEWEST,
        )

        assert ai_opener_search.pagination.total == 1
        assert ai_opener_search.items[0].company_name == "Gamma Salon"


def test_lead_sort_sql_is_mariadb_safe() -> None:
    repository = LeadsRepository()
    latest_scores = repository._latest_scores_subquery()

    score_statement = (
        select(Lead)
        .select_from(Lead)
        .outerjoin(latest_scores, latest_scores.c.lead_id == Lead.id)
        .order_by(*repository._order_by(LeadSortOption.SCORE_DESC, latest_scores))
    )
    rating_statement = (
        select(Lead)
        .select_from(Lead)
        .outerjoin(latest_scores, latest_scores.c.lead_id == Lead.id)
        .order_by(*repository._order_by(LeadSortOption.RATING_DESC, latest_scores))
    )

    score_sql = str(score_statement.compile(dialect=mysql.dialect()))
    rating_sql = str(rating_statement.compile(dialect=mysql.dialect()))

    assert "NULLS LAST" not in score_sql.upper()
    assert "NULLS LAST" not in rating_sql.upper()


def test_lead_list_uses_single_latest_score_when_timestamps_tie() -> None:
    session_factory = _build_session_factory()
    with session_factory() as db:
        workspace = Workspace(name="Tie Score Workspace")
        db.add(workspace)
        db.commit()
        db.refresh(workspace)

        lead = Lead(
            workspace_id=workspace.id,
            company_name="Si3 Digital Marketing Agency Dubai",
            category="Internet marketing service",
            city="Dubai",
            website_domain="si3.ae",
            has_website=True,
            data_completeness=0.9,
            data_confidence=0.9,
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)

        scored_at = datetime(2026, 5, 29, 22, 47, 5, tzinfo=UTC)
        db.add_all(
            [
                LeadScore(
                    lead_id=lead.id,
                    scoring_config_version_id=1,
                    total_score=68,
                    band="medium",
                    qualified=True,
                    scored_at=scored_at,
                ),
                LeadScore(
                    lead_id=lead.id,
                    scoring_config_version_id=1,
                    total_score=69,
                    band="medium",
                    qualified=True,
                    scored_at=scored_at,
                ),
                LeadScore(
                    lead_id=lead.id,
                    scoring_config_version_id=1,
                    total_score=70,
                    band="high",
                    qualified=True,
                    scored_at=scored_at,
                ),
            ]
        )
        db.commit()

        response = LeadsService().list_leads(
            db,
            workspace_id=workspace.id,
            page=1,
            page_size=20,
            status=None,
            search_job_id=None,
            has_website=None,
            sort=LeadSortOption.SCORE_DESC,
        )

        assert response.pagination.total == 1
        assert len(response.items) == 1
        assert response.items[0].company_name == "Si3 Digital Marketing Agency Dubai"
        assert response.items[0].latest_score == 70
        assert response.items[0].latest_band == "high"
