from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.modules.audit_logs.models import AuditLog
from app.modules.billing.models import (
    Invoice,
    InvoiceItem,
    PaymentAttempt,
    Subscription,
    UsageCounter,
)
from app.modules.leads.models import Lead
from app.modules.provider_serpapi.models import (
    LeadIdentity,
    LeadSourceRecord,
    ProviderFetch,
    ProviderNormalizedFact,
)
from app.modules.provider_serpapi.repository import ProviderEvidenceRepository
from app.modules.scoring.models import LeadScore, ScoreBreakdown
from app.modules.search_jobs.models import SearchJob  # noqa: F401
from app.modules.users.models import Workspace
from scripts.db_maintenance import main as maintenance_main


def _build_session_factory(database_url: str = "sqlite+pysqlite:///:memory:") -> sessionmaker[Session]:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine_kwargs: dict[str, object] = {
        "future": True,
        "connect_args": connect_args,
    }
    if database_url.endswith(":memory:"):
        engine_kwargs["poolclass"] = StaticPool
    engine = create_engine(database_url, **engine_kwargs)
    Base.metadata.create_all(engine)
    return sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )


def _seed_workspace(db: Session) -> Workspace:
    workspace = Workspace(name="DB Hardening Workspace")
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return workspace


def _seed_lead_with_facts(db: Session) -> tuple[Lead, ProviderNormalizedFact, ProviderNormalizedFact]:
    workspace = _seed_workspace(db)
    lead = Lead(
        workspace_id=workspace.id,
        company_name="Acme Dental",
        review_count=12,
        data_completeness=0.5,
        data_confidence=0.6,
        has_website=True,
        status="new",
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)

    fetch = ProviderFetch(
        workspace_id=workspace.id,
        engine="google_maps",
        mode="maps_search",
        request_fingerprint="fetch-fingerprint",
        request_params_json={"query": "acme dental"},
        status="ok",
    )
    db.add(fetch)
    db.commit()
    db.refresh(fetch)

    fact_one = ProviderNormalizedFact(
        workspace_id=workspace.id,
        lead_id=lead.id,
        provider_fetch_id=fetch.id,
        source_type="maps_search",
        company_name=lead.company_name,
        review_count=lead.review_count,
        confidence=0.6,
        completeness=0.5,
        facts_json={"source": "maps_search"},
    )
    fact_two = ProviderNormalizedFact(
        workspace_id=workspace.id,
        lead_id=lead.id,
        provider_fetch_id=fetch.id,
        source_type="maps_place",
        company_name=lead.company_name,
        review_count=lead.review_count,
        confidence=0.8,
        completeness=0.9,
        facts_json={"source": "maps_place"},
    )
    db.add_all([fact_one, fact_two])
    db.commit()
    db.refresh(fact_one)
    db.refresh(fact_two)
    return lead, fact_one, fact_two


def test_usage_counter_unique_constraint_prevents_duplicate_period_rows() -> None:
    session_factory = _build_session_factory()
    period_start = datetime(2026, 5, 1, tzinfo=UTC)
    period_end = datetime(2026, 5, 31, 23, 59, 59, tzinfo=UTC)

    with session_factory() as db:
        workspace = _seed_workspace(db)
        db.add(
            UsageCounter(
                workspace_id=workspace.id,
                metric_key="exports_per_month",
                current_value=1,
                period_start=period_start,
                period_end=period_end,
            )
        )
        db.commit()

        db.add(
            UsageCounter(
                workspace_id=workspace.id,
                metric_key="exports_per_month",
                current_value=2,
                period_start=period_start,
                period_end=period_end,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()


def test_lead_source_repository_promotes_only_one_current_record() -> None:
    session_factory = _build_session_factory()
    repository = ProviderEvidenceRepository()

    with session_factory() as db:
        lead, fact_one, fact_two = _seed_lead_with_facts(db)

        repository.set_source_record(
            db,
            lead_id=lead.id,
            provider_normalized_fact_id=fact_one.id,
            priority=20,
            is_current=True,
        )
        repository.set_source_record(
            db,
            lead_id=lead.id,
            provider_normalized_fact_id=fact_two.id,
            priority=10,
            is_current=True,
        )

        records = list(
            db.scalars(select(LeadSourceRecord).order_by(LeadSourceRecord.id.asc()))
        )

        assert len(records) == 2
        assert records[0].is_current is False
        assert records[0].current_for_lead_id is None
        assert records[1].is_current is True
        assert records[1].current_for_lead_id == lead.id

        db.add(
            LeadSourceRecord(
                lead_id=lead.id,
                provider_normalized_fact_id=fact_one.id,
                current_for_lead_id=lead.id,
                priority=5,
                is_current=True,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()


def test_model_alignment_exposes_expected_indexes_and_constraints() -> None:
    assert "ix_provider_fetches_workspace_engine_mode" in {
        index.name for index in ProviderFetch.__table__.indexes
    }
    assert "uq_lead_identities_workspace_key" in {
        constraint.name
        for constraint in LeadIdentity.__table__.constraints
        if constraint.name is not None
    }
    assert "ix_lead_identities_lookup" in {
        index.name for index in LeadIdentity.__table__.indexes
    }
    assert "ix_lead_scores_lead_scored_at" in {
        index.name for index in LeadScore.__table__.indexes
    }
    assert "ix_score_breakdowns_lead_score_key" in {
        index.name for index in ScoreBreakdown.__table__.indexes
    }
    assert "ix_audit_logs_workspace_created_at" in {
        index.name for index in AuditLog.__table__.indexes
    }
    assert "ix_subscriptions_workspace_id_id" in {
        index.name for index in Subscription.__table__.indexes
    }
    assert "ix_invoices_workspace_issued_at_id" in {
        index.name for index in Invoice.__table__.indexes
    }
    assert "ix_invoice_items_invoice_id_id" in {
        index.name for index in InvoiceItem.__table__.indexes
    }
    assert "ix_payment_attempts_invoice_attempted_at_id" in {
        index.name for index in PaymentAttempt.__table__.indexes
    }
    assert "uq_usage_counters_workspace_metric_period" in {
        constraint.name
        for constraint in UsageCounter.__table__.constraints
        if constraint.name is not None
    }


def test_db_maintenance_dry_run_and_repair(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    database_path = tmp_path / "maintenance.db"
    database_url = f"sqlite+pysqlite:///{database_path}"
    session_factory = _build_session_factory(database_url)

    with session_factory() as db:
        lead, fact_one, _ = _seed_lead_with_facts(db)
        db.add(
            LeadSourceRecord(
                lead_id=lead.id,
                provider_normalized_fact_id=fact_one.id,
                current_for_lead_id=None,
                priority=20,
                is_current=True,
            )
        )
        db.commit()

    result = maintenance_main(
        ["--database-url", database_url, "--large-table-threshold", "1"]
    )
    output = capsys.readouterr().out

    assert result == 0
    assert "Mode: dry-run" in output
    assert "Lead source marker mismatches: 1" in output
    assert "provider_normalized_facts: 2" in output

    repair_result = maintenance_main(
        [
            "--database-url",
            database_url,
            "--large-table-threshold",
            "1",
            "--apply-current-marker-repair",
        ]
    )
    repair_output = capsys.readouterr().out

    assert repair_result == 0
    assert "Mode: repair + audit" in repair_output
    assert "Current-marker rows repaired: 1" in repair_output
    assert "Lead source marker mismatches: 0" in repair_output

    with session_factory() as db:
        repaired = db.scalar(select(LeadSourceRecord).where(LeadSourceRecord.is_current == True))  # noqa: E712
        assert repaired is not None
        assert repaired.current_for_lead_id == repaired.lead_id
