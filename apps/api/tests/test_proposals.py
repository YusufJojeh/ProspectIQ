from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_workspace_e2e import _build_session_factory, _login, _override_client, _seed_workspace

from app.core.config import clear_settings_cache
from app.modules.agents.tool_executor import AgentToolExecutor
from app.modules.agents.tool_registry import get_tool, validate_arguments
from app.modules.leads.models import Lead
from app.modules.proposals.documents import (
    compute_totals,
    next_number,
    readiness_issues,
    share_pct,
)
from app.modules.proposals.models import Proposal
from app.modules.proposals.pricing import (
    PRICING_GROUNDED,
    PRICING_NEEDS_PRICING,
    PRICING_PARTIAL,
    ground_milestone_amounts,
    prices_in,
)
from app.modules.users.models import User, Workspace

# --- Pure document rules ------------------------------------------------------


def test_totals_take_the_first_milestone_as_the_deposit() -> None:
    lines = [{"amount_minor": 150_000}, {"amount_minor": 337_500}, {"amount_minor": 262_500}]
    totals = compute_totals(lines)
    assert (totals.total_minor, totals.deposit_minor, totals.remaining_minor) == (
        750_000,
        150_000,
        600_000,
    )
    assert share_pct(150_000, totals.total_minor) == 20.0
    assert share_pct(None, totals.total_minor) is None
    assert compute_totals([]).total_minor == 0


def _issues(**overrides: Any) -> list[str]:
    today = date(2026, 10, 10)
    fields: dict[str, Any] = {
        "title": "Booking platform",
        "client_company": "Acme Dental",
        "client_email": "owner@acme.example",
        "client_contact_name": "Dr. Lina",
        "client_location": "Dubai",
        "outcome": "A booking system.",
        "milestones": [{"title": "Discovery", "description": "", "amount_minor": 100_00}],
        "commercial_notes": "Deposit first.",
        "validity_notes": "30 days.",
        "issue_date": today,
        "valid_until": today + timedelta(days=30),
        "today": today,
    }
    fields.update(overrides)
    return readiness_issues(**fields)


def test_a_complete_document_has_no_issues() -> None:
    assert _issues() == []


@pytest.mark.parametrize(
    ("overrides", "issue"),
    [
        ({"title": " "}, "missing_title"),
        ({"client_company": ""}, "missing_client_company"),
        ({"client_email": None}, "missing_client_email"),
        ({"client_email": "not-an-email"}, "invalid_client_email"),
        ({"outcome": ""}, "missing_outcome"),
        ({"milestones": []}, "no_milestones"),
        ({"milestones": [{"title": "", "amount_minor": 1}]}, "milestone_missing_title"),
        ({"milestones": [{"title": "x", "amount_minor": None}]}, "milestone_missing_amount"),
        ({"milestones": [{"title": "x", "amount_minor": 0}]}, "milestone_missing_amount"),
        ({"valid_until": date(2026, 10, 10)}, "invalid_validity"),
        (
            {"issue_date": date(2026, 8, 1), "valid_until": date(2026, 9, 1)},
            "expired",
        ),
        ({"client_company": "[Client Company]"}, "placeholder_text"),
        (
            {"milestones": [{"title": "x", "description": "[scope]", "amount_minor": 1}]},
            "placeholder_text",
        ),
    ],
)
def test_each_gap_is_reported(overrides: dict[str, Any], issue: str) -> None:
    assert issue in _issues(**overrides)


def test_numbers_continue_past_the_highest_issued() -> None:
    assert next_number("YJ-Q", 2026, []) == "YJ-Q-2026-001"
    assert next_number("YJ-Q", 2026, ["YJ-Q-2026-001", "YJ-Q-2026-007", "YJ-Q-2025-050"]) == (
        "YJ-Q-2026-008"
    )
    assert next_number("HXT-Q", 2026, ["YJ-Q-2026-009"]) == "HXT-Q-2026-001"


# --- Pricing grounding --------------------------------------------------------


def test_prices_are_read_in_the_forms_people_write_them() -> None:
    found = prices_in(["Starter package USD 7,500.00; retainer 1.5k/month; 12K for enterprise"])
    assert {750_000, 150_000, 1_200_000} <= found


def test_amounts_backed_line_by_line_are_kept() -> None:
    result = ground_milestone_amounts([1500, 3375], ["Discovery 1,500; build 3,375"])
    assert result.amounts_minor == [150_000, 337_500]
    assert result.status == PRICING_GROUNDED


def test_a_package_total_split_across_milestones_is_backed() -> None:
    result = ground_milestone_amounts([1500, 3375, 2625], ["Standard package: USD 7,500"])
    assert result.amounts_minor == [150_000, 337_500, 262_500]
    assert result.status == PRICING_GROUNDED


def test_invented_prices_are_dropped_not_guessed() -> None:
    assert ground_milestone_amounts([999, 4000], []).amounts_minor == [None, None]
    assert ground_milestone_amounts([999], []).status == PRICING_NEEDS_PRICING
    partial = ground_milestone_amounts([1500, 4321], ["Discovery from 1,500"])
    assert partial.amounts_minor == [150_000, None]
    assert partial.status == PRICING_PARTIAL
    # Lines with no amount at all stay unpriced.
    assert ground_milestone_amounts([None], ["7,500"]).amounts_minor == [None]


# --- API ------------------------------------------------------------------------


def _client_setup(monkeypatch: pytest.MonkeyPatch) -> tuple[Any, Any]:
    monkeypatch.setenv("APP_ENV", "test")
    clear_settings_cache()
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    return session_factory, seed


def test_a_proposal_goes_from_draft_to_sent(monkeypatch: pytest.MonkeyPatch) -> None:
    session_factory, seed = _client_setup(monkeypatch)
    with _override_client(session_factory) as client:
        headers = {"Authorization": f"Bearer {_login(client, seed)}"}

        brands = client.get("/api/v1/proposals/brands", headers=headers).json()["items"]
        assert {brand["key"] for brand in brands} == {"yusuf_jojeh", "hexaterminal"}

        created = client.post(
            "/api/v1/proposals",
            json={"lead_id": seed.lead_public_id, "brand_key": "yusuf_jojeh"},
            headers=headers,
        )
        assert created.status_code == 201, created.text
        body = created.json()
        proposal_id = body["public_id"]
        assert body["number"].startswith("YJ-Q-")
        assert body["status"] == "draft"
        # Template lines arrive unpriced: nobody chose a price for this client yet.
        assert [m["amount_minor"] for m in body["milestones"]] == [None, None, None]
        assert "milestone_missing_amount" in body["readiness"]["issues"]

        refused = client.post(f"/api/v1/proposals/{proposal_id}/ready", headers=headers)
        assert refused.status_code == 422
        assert refused.json()["error"]["code"] == "proposals.not_ready"

        updated = client.patch(
            f"/api/v1/proposals/{proposal_id}",
            json={
                "title": "Online booking system",
                "client_email": "owner@client.example",
                "milestones": [
                    {"title": "Discovery", "description": "Mapping", "amount_minor": 150_000},
                    {"title": "Build", "description": "APIs", "amount_minor": 337_500},
                    {"title": "Launch", "description": "Handover", "amount_minor": 262_500},
                ],
            },
            headers=headers,
        ).json()
        assert updated["totals"] == {
            "total_minor": 750_000,
            "deposit_minor": 150_000,
            "remaining_minor": 600_000,
        }
        assert [m["share_pct"] for m in updated["milestones"]] == [20.0, 45.0, 35.0]
        assert updated["readiness"] == {"ready": True, "issues": []}

        # Not ready yet, so it cannot be marked sent.
        early = client.post(f"/api/v1/proposals/{proposal_id}/sent", headers=headers)
        assert early.status_code == 409

        ready = client.post(f"/api/v1/proposals/{proposal_id}/ready", headers=headers).json()
        assert ready["status"] == "ready"

        # Editing a ready proposal sends it back to draft for another review.
        edited = client.patch(
            f"/api/v1/proposals/{proposal_id}", json={"outcome": "Revised."}, headers=headers
        ).json()
        assert edited["status"] == "draft"
        client.post(f"/api/v1/proposals/{proposal_id}/ready", headers=headers)

        sent = client.post(f"/api/v1/proposals/{proposal_id}/sent", headers=headers).json()
        assert sent["status"] == "sent"
        assert sent["sent_at"] is not None

        locked = client.patch(
            f"/api/v1/proposals/{proposal_id}", json={"title": "Changed"}, headers=headers
        )
        assert locked.status_code == 409

        decided = client.post(
            f"/api/v1/proposals/{proposal_id}/decision",
            json={"decision": "accepted"},
            headers=headers,
        ).json()
        assert decided["status"] == "accepted"

        listing = client.get(
            "/api/v1/proposals", params={"lead_id": seed.lead_public_id}, headers=headers
        ).json()["items"]
        assert [item["public_id"] for item in listing] == [proposal_id]
        assert listing[0]["total_minor"] == 750_000


def test_proposals_are_invisible_to_other_workspaces(monkeypatch: pytest.MonkeyPatch) -> None:
    session_factory, seed = _client_setup(monkeypatch)
    with session_factory() as db:
        other = Workspace(name="Other")
        db.add(other)
        db.commit()
        admin = db.scalar(select(User).where(User.email == seed.admin_email))
        assert admin is not None
        foreign_lead = Lead(workspace_id=other.id, company_name="Elsewhere")
        db.add(foreign_lead)
        db.commit()
        foreign = Proposal(
            workspace_id=other.id,
            lead_id=foreign_lead.id,
            number="HXT-Q-2026-001",
            brand_key="hexaterminal",
            issue_date=date(2026, 10, 1),
            valid_until=date(2026, 10, 31),
            outcome="",
            milestones=[],
            commercial_notes="",
            validity_notes="",
            created_by_user_id=admin.id,
        )
        db.add(foreign)
        db.commit()
        foreign_id, foreign_lead_id = foreign.public_id, foreign_lead.public_id

    with _override_client(session_factory) as client:
        headers = {"Authorization": f"Bearer {_login(client, seed)}"}
        assert client.get(f"/api/v1/proposals/{foreign_id}", headers=headers).status_code == 404
        assert (
            client.patch(
                f"/api/v1/proposals/{foreign_id}", json={"title": "x"}, headers=headers
            ).status_code
            == 404
        )
        assert client.get("/api/v1/proposals", headers=headers).json()["items"] == []
        assert (
            client.post(
                "/api/v1/proposals",
                json={"lead_id": foreign_lead_id, "brand_key": "hexaterminal"},
                headers=headers,
            ).status_code
            == 404
        )


def test_unknown_brand_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    session_factory, seed = _client_setup(monkeypatch)
    with _override_client(session_factory) as client:
        headers = {"Authorization": f"Bearer {_login(client, seed)}"}
        response = client.post(
            "/api/v1/proposals",
            json={"lead_id": seed.lead_public_id, "brand_key": "acme"},
            headers=headers,
        )
        assert response.status_code == 422


# --- Copilot tool ----------------------------------------------------------------


def _executor(db: Session, seed: Any) -> AgentToolExecutor:
    admin = db.scalar(select(User).where(User.email == seed.admin_email))
    lead = db.scalar(select(Lead).where(Lead.public_id == seed.lead_public_id))
    assert admin is not None and lead is not None
    executor = AgentToolExecutor(db, workspace_id=admin.workspace_id, lead=lead, current_user=admin)
    executor.run_public_id = "ar_test"
    return executor


def test_draft_proposal_schema_rejects_malformed_milestones() -> None:
    tool = get_tool("draft_proposal")
    assert tool is not None and tool.requires_approval
    assert validate_arguments(tool, {"brand": "acme", "title": "x", "milestones": [{"title": "a"}]})
    assert validate_arguments(tool, {"brand": "hexaterminal", "title": "x", "milestones": []})
    assert validate_arguments(
        tool, {"brand": "hexaterminal", "title": "x", "milestones": [{"title": "a", "amount": "5"}]}
    )
    assert (
        validate_arguments(
            tool,
            {"brand": "hexaterminal", "title": "x", "milestones": [{"title": "a", "amount": 5}]},
        )
        is None
    )


def test_copilot_drafts_a_proposal_with_only_retrieved_prices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory, seed = _client_setup(monkeypatch)
    arguments = {
        "brand": "hexaterminal",
        "title": "Patient booking platform",
        "currency": "usd",
        "milestones": [
            {"title": "Discovery", "description": "Mapping", "amount": 2400},
            {"title": "Build", "description": "APIs", "amount": 5400},
            {"title": "Launch", "description": "Handover", "amount": 4200},
        ],
        "pricing_basis": "Standard build package: USD 12,000.",
    }
    with session_factory() as db:
        executor = _executor(db, seed)
        executor.retrieved_grounding.append("Standard build package: USD 12,000 (3 milestones).")
        preview, payload, resource_type, _ = executor.build_preview("draft_proposal", arguments)
        assert resource_type == "proposal"
        assert preview["pricing_status"] == "grounded"
        assert preview["total"] == "USD 12,000.00"
        assert payload["source_agent_run_id"] == "ar_test"

        # Building the preview changes nothing; only the approved action does.
        assert db.scalar(select(Proposal)) is None
        result = executor.execute_action("draft_proposal", payload)

    assert result["number"].startswith("HXT-Q-")
    assert result["total_minor"] == 1_200_000
    assert result["status"] == "draft"
    with session_factory() as db:
        stored = db.scalar(select(Proposal).where(Proposal.public_id == result["proposal_id"]))
        assert stored is not None
        assert stored.source_agent_run_id == "ar_test"
        assert stored.pricing_basis == "Standard build package: USD 12,000."
        assert stored.currency == "USD"


def test_copilot_cannot_invent_prices(monkeypatch: pytest.MonkeyPatch) -> None:
    session_factory, seed = _client_setup(monkeypatch)
    with session_factory() as db:
        executor = _executor(db, seed)
        preview, payload, _, _ = executor.build_preview(
            "draft_proposal",
            {
                "brand": "yusuf_jojeh",
                "title": "Booking system",
                "milestones": [{"title": "Discovery", "amount": 9999}],
            },
        )
    assert preview["pricing_status"] == "needs_pricing"
    assert preview["milestones"] == ["Discovery — unpriced"]
    assert payload["milestones"][0]["amount_minor"] is None
