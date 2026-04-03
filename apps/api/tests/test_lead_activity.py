from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.modules.leads.models import Lead
from app.modules.leads.schemas import LeadNoteCreateRequest, LeadStatusUpdateRequest
from app.modules.leads.service import LeadsService
from app.modules.users.models import User, Workspace
from app.shared.enums.jobs import LeadStatus


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


def test_lead_activity_lists_status_history_and_notes() -> None:
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
        db.refresh(user)

        lead = Lead(
            workspace_id=workspace.id,
            company_name="Acme Dental",
            category="Dentist",
            city="Istanbul",
            review_count=9,
            rating=4.4,
            data_completeness=0.71,
            data_confidence=0.76,
            has_website=False,
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)

        service = LeadsService()
        service.update_status(
            db,
            workspace.id,
            lead.public_id,
            LeadStatusUpdateRequest(status=LeadStatus.QUALIFIED, note="Strong review signal."),
            current_user=user,
        )
        note = service.create_note(
            db,
            workspace.id,
            lead.public_id,
            LeadNoteCreateRequest(note="Follow up with a GBP optimization audit."),
            current_user=user,
        )
        activity = service.list_activity(db, workspace.id, lead.public_id)

        assert note.actor_user_public_id == user.public_id
        assert len(activity.items) == 3
        assert [item.created_at for item in activity.items] == sorted(
            [item.created_at for item in activity.items],
            reverse=True,
        )

        status_entries = [item for item in activity.items if item.entry_type == "status_change"]
        note_entries = [item for item in activity.items if item.entry_type == "note"]

        assert len(status_entries) == 1
        assert status_entries[0].from_status == LeadStatus.NEW
        assert status_entries[0].to_status == LeadStatus.QUALIFIED
        assert status_entries[0].actor_full_name == "Admin User"

        assert len(note_entries) == 2
        assert {entry.note for entry in note_entries} == {
            "Strong review signal.",
            "Follow up with a GBP optimization audit.",
        }
