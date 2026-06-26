from __future__ import annotations

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import clear_settings_cache
from app.core.database import Base
from app.modules.ai_analysis.models import AIAnalysisEvidence
from app.modules.auth.permissions import get_role_permissions
from app.modules.auth.schemas import LoginRequest
from app.modules.auth.service import AuthService
from app.modules.leads.models import Lead
from app.modules.scoring.models import ScoringConfigVersion
from app.modules.scoring.schemas import ScoringWeights
from app.modules.search_jobs.models import SearchJob
from app.modules.signals.models import LeadSignal
from app.modules.users.models import User
from scripts.seed import _seed_demo_workspace


def _build_session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )


@pytest.fixture(autouse=True)
def _non_production_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-with-at-least-32-bytes")
    monkeypatch.setenv("DEFAULT_ADMIN_PASSWORD", "local-dev-admin-password-rotate-before-sharing")
    clear_settings_cache()
    yield
    clear_settings_cache()


def test_demo_seed_creates_deterministic_accounts_with_expected_roles_and_auth() -> None:
    session_factory = _build_session_factory()

    with session_factory() as db:
        _seed_demo_workspace(db)

        admin = db.scalar(select(User).where(User.email == "admin@example.test"))
        manager = db.scalar(select(User).where(User.email == "manager@example.test"))
        user1 = db.scalar(select(User).where(User.email == "user1@example.test"))

        assert admin is not None
        assert manager is not None
        assert user1 is not None
        assert admin.role == "account_owner"
        assert manager.role == "manager"
        assert user1.role == "member"
        assert admin.workspace_id == manager.workspace_id == user1.workspace_id

        admin_token = AuthService().authenticate(
            db,
            payload=LoginRequest(email="admin@example.test", password="AdminPass123!"),
        )
        manager_token = AuthService().authenticate(
            db,
            payload=LoginRequest(email="manager@example.test", password="ManagerPass123!"),
        )
        user1_token = AuthService().authenticate(
            db,
            payload=LoginRequest(email="user1@example.test", password="UserPass123!"),
        )

        assert admin_token.user.role == "account_owner"
        assert manager_token.user.role == "manager"
        assert user1_token.user.role == "member"
        assert "billing:manage" in admin_token.user.permissions
        assert "leads:manage" in manager_token.user.permissions
        assert get_role_permissions("member") == list(user1_token.user.permissions)

        scoring_versions = db.scalars(select(ScoringConfigVersion)).all()
        assert scoring_versions
        for version in scoring_versions:
            ScoringWeights.model_validate(version.weights_json)
        assert int(db.scalar(select(func.count(LeadSignal.id))) or 0) > 0
        assert int(db.scalar(select(func.count(AIAnalysisEvidence.id))) or 0) > 0


def test_demo_seed_is_idempotent_for_accounts_and_dataset() -> None:
    session_factory = _build_session_factory()

    with session_factory() as db:
        _seed_demo_workspace(db)
        first_user_count = int(
            db.scalar(
                select(func.count(User.id)).where(
                    User.email.in_(
                        [
                            "admin@example.test",
                            "manager@example.test",
                            "user1@example.test",
                        ]
                    )
                )
            )
            or 0
        )
        first_job_count = int(db.scalar(select(func.count(SearchJob.id))) or 0)
        first_lead_count = int(db.scalar(select(func.count(Lead.id))) or 0)
        first_signal_count = int(db.scalar(select(func.count(LeadSignal.id))) or 0)
        first_evidence_count = int(
            db.scalar(select(func.count(AIAnalysisEvidence.id))) or 0
        )

        _seed_demo_workspace(db)

        second_user_count = int(
            db.scalar(
                select(func.count(User.id)).where(
                    User.email.in_(
                        [
                            "admin@example.test",
                            "manager@example.test",
                            "user1@example.test",
                        ]
                    )
                )
            )
            or 0
        )
        second_job_count = int(db.scalar(select(func.count(SearchJob.id))) or 0)
        second_lead_count = int(db.scalar(select(func.count(Lead.id))) or 0)
        second_signal_count = int(db.scalar(select(func.count(LeadSignal.id))) or 0)
        second_evidence_count = int(
            db.scalar(select(func.count(AIAnalysisEvidence.id))) or 0
        )

        assert first_user_count == second_user_count == 3
        assert first_job_count == second_job_count
        assert first_lead_count == second_lead_count
        assert first_signal_count == second_signal_count > 0
        assert first_evidence_count == second_evidence_count > 0


def test_demo_seed_is_blocked_in_production() -> None:
    clear_settings_cache()
    session_factory = _build_session_factory()

    with session_factory() as db:
        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setenv("APP_ENV", "production")
            monkeypatch.setenv("JWT_SECRET", "production-test-secret-with-at-least-32-characters")
            monkeypatch.setenv("DEFAULT_ADMIN_PASSWORD", "VeryStrongProdPassword123!")
            monkeypatch.setenv("WEB_ORIGINS", "https://example.test")
            monkeypatch.setenv("SERPAPI_API_KEY", "configured-for-validation")
            monkeypatch.setenv("AI_PROVIDER", "openai")
            monkeypatch.setenv("OPENAI_API_KEY", "configured-openai-key")
            clear_settings_cache()

            with pytest.raises(RuntimeError, match="Demo account seeding is blocked"):
                _seed_demo_workspace(db)

        assert db.scalar(select(User).where(User.email == "admin@example.test")) is None
