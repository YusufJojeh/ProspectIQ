from __future__ import annotations

import pytest
from sqlalchemy.orm import Session, sessionmaker
from test_agent_runtime import _build_session_factory
from test_knowledge_rag import _seed_workspace

from app.core.config import clear_settings_cache
from app.core.errors import ApiError
from app.modules.agents.action_gate import hash_payload
from app.modules.agents.profiles import get_profile, tools_for
from app.modules.agents.tool_executor import AgentToolExecutor
from app.modules.agents.tool_registry import (
    ACTION,
    EXTERNAL_SEND_TOOL_NAMES,
    HIGH,
    TOOL_REGISTRY,
)
from app.modules.leads.models import Lead
from app.modules.outreach.models import OutreachMessage
from app.modules.outreach.send_gateway import (
    ExternalSendDisabledError,
    ExternalSendGateway,
    SendRequest,
)
from app.modules.users.models import User, Workspace


def _enable_sending(monkeypatch: pytest.MonkeyPatch, *, enabled: bool) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("EXTERNAL_SEND_ENABLED", "true" if enabled else "false")
    clear_settings_cache()


@pytest.fixture(autouse=True)
def _disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    clear_settings_cache()


def _seed_lead_with_draft(
    session_factory: sessionmaker[Session],
) -> tuple[int, str, str, str]:
    """Returns (workspace_id, lead_public_id, message_public_id, body)."""
    with session_factory() as db:
        workspace, user = _seed_workspace(db, name="Send WS", email="owner@send.test")
        lead = Lead(
            workspace_id=workspace.id,
            company_name="Acme Dental",
            email="owner@acmedental.test",
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
        message = OutreachMessage(
            lead_id=lead.id,
            ai_analysis_snapshot_id=1,
            subject="A quicker way to fill Tuesday mornings",
            message="Hello -- noticed you take bookings by phone only.",
            created_by_user_id=user.id,
        )
        db.add(message)
        db.commit()
        db.refresh(message)
        return workspace.id, lead.public_id, message.public_id, message.message


def _executor(session_factory: sessionmaker[Session], db: Session) -> AgentToolExecutor:
    workspace = db.query(Workspace).first()
    assert workspace is not None
    user = db.query(User).first()
    assert user is not None
    lead = db.query(Lead).first()
    assert lead is not None
    return AgentToolExecutor(
        db, workspace_id=workspace.id, lead=lead, current_user=user
    )


# --- Registration policy -------------------------------------------------


def test_send_tools_are_registered_as_high_risk_approval_required_actions() -> None:
    assert EXTERNAL_SEND_TOOL_NAMES == {"send_email", "send_whatsapp", "send_linkedin_message"}
    for name in EXTERNAL_SEND_TOOL_NAMES:
        spec = TOOL_REGISTRY[name]
        assert spec.tool_type == ACTION
        assert spec.risk_level == HIGH
        assert spec.requires_approval is True
        assert spec.external_io is True
        assert spec.feature_flag == "external_send_enabled"


def test_send_tools_carry_no_tenancy_parameter() -> None:
    # The same structural rule as every other tool: there is no field an
    # injected instruction could fill to redirect a send to another tenant.
    for name in EXTERNAL_SEND_TOOL_NAMES:
        properties = TOOL_REGISTRY[name].parameters["properties"]
        assert not {"workspace_id", "workspace", "tenant_id", "user_id"} & set(properties)
        assert TOOL_REGISTRY[name].parameters["additionalProperties"] is False


# --- Disabled by default -------------------------------------------------


def test_send_tools_are_not_described_to_the_model_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_sending(monkeypatch, enabled=False)
    for profile_key in ("research", "sales_copilot", "read_only", "admin_assistant"):
        names = {tool.name for tool in tools_for(get_profile(profile_key), role="admin")}
        assert not names & EXTERNAL_SEND_TOOL_NAMES


def test_send_tools_become_visible_only_to_admin_assistant_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_sending(monkeypatch, enabled=True)
    admin_names = {tool.name for tool in tools_for(get_profile("admin_assistant"), role="admin")}
    assert EXTERNAL_SEND_TOOL_NAMES <= admin_names
    # The sales copilot's MEDIUM risk ceiling excludes them even though the
    # tools name that profile: both sides must agree, and one says no.
    copilot_names = {tool.name for tool in tools_for(get_profile("sales_copilot"), role="admin")}
    assert not copilot_names & EXTERNAL_SEND_TOOL_NAMES
    read_only_names = {tool.name for tool in tools_for(get_profile("read_only"), role="admin")}
    assert not read_only_names & EXTERNAL_SEND_TOOL_NAMES


def test_gateway_refuses_and_transmits_nothing_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_sending(monkeypatch, enabled=False)
    gateway = ExternalSendGateway()
    assert gateway.enabled is False
    with pytest.raises(ExternalSendDisabledError):
        gateway.send(
            SendRequest(
                channel="email",
                destination="owner@acmedental.test",
                subject="Hi",
                body="Body",
                outreach_message_id="om_1",
            )
        )


def test_disabled_send_cannot_even_be_proposed_for_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_sending(monkeypatch, enabled=False)
    session_factory = _build_session_factory()
    _, _, message_id, _ = _seed_lead_with_draft(session_factory)
    with session_factory() as db:
        executor = _executor(session_factory, db)
        with pytest.raises(ExternalSendDisabledError):
            executor.build_preview(
                "send_email",
                {"outreach_message_id": message_id, "to_email": "owner@acmedental.test"},
            )


def test_disabled_send_refuses_at_execution_even_with_an_approved_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Simulates sending being switched off between approval and execution.
    _enable_sending(monkeypatch, enabled=True)
    session_factory = _build_session_factory()
    _, _, message_id, body = _seed_lead_with_draft(session_factory)
    with session_factory() as db:
        executor = _executor(session_factory, db)
        _preview, payload, _rtype, _rid = executor.build_preview(
            "send_email",
            {"outreach_message_id": message_id, "to_email": "owner@acmedental.test"},
        )

    _enable_sending(monkeypatch, enabled=False)
    with session_factory() as db:
        executor = _executor(session_factory, db)
        with pytest.raises(ExternalSendDisabledError):
            executor.execute_action("send_email", payload)
    assert body in payload["body"]


# --- Approved payload integrity -----------------------------------------


def test_preview_payload_carries_the_exact_stored_draft_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_sending(monkeypatch, enabled=True)
    session_factory = _build_session_factory()
    _, _, message_id, body = _seed_lead_with_draft(session_factory)
    with session_factory() as db:
        executor = _executor(session_factory, db)
        preview, payload, resource_type, resource_id = executor.build_preview(
            "send_email",
            {"outreach_message_id": message_id, "to_email": "owner@acmedental.test"},
        )
    assert payload["body"] == body
    assert preview["body"] == body
    assert preview["irreversible"] is True
    assert resource_type == "outreach_message"
    assert resource_id == message_id


def test_tampering_with_an_approved_send_payload_changes_its_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The gate re-hashes the stored payload before execution and refuses on a
    # mismatch, so this is the property that makes "approved == executed" true.
    _enable_sending(monkeypatch, enabled=True)
    session_factory = _build_session_factory()
    _, _, message_id, _ = _seed_lead_with_draft(session_factory)
    with session_factory() as db:
        executor = _executor(session_factory, db)
        _preview, payload, _rtype, _rid = executor.build_preview(
            "send_email",
            {"outreach_message_id": message_id, "to_email": "owner@acmedental.test"},
        )
    approved_hash = hash_payload(payload)
    tampered = {**payload, "destination": "attacker@evil.test"}
    assert hash_payload(tampered) != approved_hash
    assert hash_payload(dict(reversed(list(payload.items())))) == approved_hash


def test_send_cannot_target_an_outreach_message_belonging_to_another_lead(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_sending(monkeypatch, enabled=True)
    session_factory = _build_session_factory()
    _seed_lead_with_draft(session_factory)
    with session_factory() as db:
        other_lead = Lead(workspace_id=1, company_name="Other Co")
        db.add(other_lead)
        db.commit()
        db.refresh(other_lead)
        foreign = OutreachMessage(
            lead_id=other_lead.id,
            ai_analysis_snapshot_id=1,
            subject="Not yours",
            message="Not yours either.",
            created_by_user_id=1,
        )
        db.add(foreign)
        db.commit()
        db.refresh(foreign)
        foreign_id = foreign.public_id

    with session_factory() as db:
        executor = _executor(session_factory, db)
        with pytest.raises(ApiError):
            executor.build_preview(
                "send_email",
                {"outreach_message_id": foreign_id, "to_email": "owner@acmedental.test"},
            )


# --- Honest execution result --------------------------------------------


def test_enabled_send_without_a_transport_reports_not_delivered_and_keeps_draft_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_sending(monkeypatch, enabled=True)
    session_factory = _build_session_factory()
    _, _, message_id, _ = _seed_lead_with_draft(session_factory)
    with session_factory() as db:
        executor = _executor(session_factory, db)
        _preview, payload, _rtype, _rid = executor.build_preview(
            "send_email",
            {"outreach_message_id": message_id, "to_email": "owner@acmedental.test"},
        )
        result = executor.execute_action("send_email", payload)

    assert result["delivered"] is False
    assert result["provider"] == "none"
    # A message nothing transmitted must not be recorded as sent: every
    # downstream reply-rate and follow-up decision reads this column.
    assert result["outreach_status"] == "draft"
    with session_factory() as db:
        stored = db.query(OutreachMessage).filter_by(public_id=message_id).one()
        assert stored.outreach_status == "draft"
