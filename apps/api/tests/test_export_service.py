from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.modules.exports.service import ExportService
from app.modules.leads.models import Lead
from app.modules.scoring.models import LeadScore
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


def test_export_service_applies_band_and_query_filters() -> None:
    session_factory = _build_session_factory()
    with session_factory() as db:
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

        high_lead = Lead(
            workspace_id=workspace.id,
            company_name="North Dental",
            city="Istanbul",
            review_count=24,
            rating=4.7,
            website_domain="north.example",
            website_url="https://north.example",
            data_completeness=0.9,
            data_confidence=0.88,
            has_website=True,
        )
        low_lead = Lead(
            workspace_id=workspace.id,
            company_name="South Salon",
            city="Ankara",
            review_count=4,
            rating=3.8,
            data_completeness=0.5,
            data_confidence=0.52,
            has_website=False,
        )
        db.add_all([high_lead, low_lead])
        db.commit()
        db.refresh(high_lead)
        db.refresh(low_lead)

        db.add_all(
            [
                LeadScore(
                    lead_id=high_lead.id,
                    scoring_config_version_id=1,
                    total_score=82,
                    band="high",
                    qualified=True,
                ),
                LeadScore(
                    lead_id=low_lead.id,
                    scoring_config_version_id=1,
                    total_score=38,
                    band="low",
                    qualified=True,
                ),
            ]
        )
        db.commit()

        payload = ExportService().export_leads_csv(
            db,
            workspace_id=workspace.id,
            band="high",
            q="north",
            status=None,
            search_job_public_id=None,
            has_website=None,
            city=None,
        )

        assert "North Dental" in payload
        assert "South Salon" not in payload
