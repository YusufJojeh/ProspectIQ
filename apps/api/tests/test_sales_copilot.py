from __future__ import annotations

import json

import pytest
from sqlalchemy.orm import Session, sessionmaker
from test_agent_runtime import _build_session_factory
from test_knowledge_rag import _collection, _document, _seed_workspace

from app.core.config import clear_settings_cache
from app.modules.agents.profiles import (
    PROFILES,
    agent_permissions_for_role,
    get_profile,
    tools_for,
)
from app.modules.agents.tool_registry import (
    ACTION,
    BLOCKED,
    PROFILE_READ_ONLY,
    PROFILE_SALES_COPILOT,
    TOOL_REGISTRY,
    WRITE_PROPOSAL,
    risk_rank,
)
from app.modules.knowledge.constants import CASE_STUDIES, SERVICES
from app.modules.knowledge.matching import CapabilityMatcher
from app.modules.outreach.quality_guard import OutreachQualityGuard
from app.modules.research.evidence_graph import (
    CanonicalFact,
    EvidenceGraph,
    EvidenceGroup,
)


@pytest.fixture(autouse=True)
def _local_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
    clear_settings_cache()


def _fact(claim_type: str, value: str, *, confidence: float = 0.8) -> CanonicalFact:
    return CanonicalFact(
        claim_type=claim_type,
        value=value,
        status="supported",
        confidence=confidence,
        freshness_score=1.0,
        source_quality=0.9,
    )


def _graph(*facts: CanonicalFact) -> EvidenceGraph:
    return EvidenceGraph(
        lead_id="lead_test",
        groups=[EvidenceGroup(group="digital_presence", facts=list(facts))],
        evidence_confidence=0.8,
        research_coverage=0.7,
    )


# --- profiles as policy, not as separate engines --------------------------


def test_every_profile_resolves_and_an_unknown_key_narrows_rather_than_widens() -> None:
    for key in PROFILES:
        assert get_profile(key).key == key
    # A typo must not produce an unrestricted run.
    fallback = get_profile("superuser_mode")
    assert fallback.key == "research"
    assert get_profile(None).key == "research"


def test_read_only_profile_cannot_reach_any_mutating_tool() -> None:
    tools = tools_for(get_profile(PROFILE_READ_ONLY), role="admin")
    assert tools, "read_only must still have read tools"
    assert all(tool.tool_type not in {WRITE_PROPOSAL, ACTION} for tool in tools)
    assert all(not tool.mutating for tool in tools)


def test_sales_copilot_has_knowledge_tools_but_a_medium_risk_ceiling() -> None:
    profile = get_profile(PROFILE_SALES_COPILOT)
    names = {tool.name for tool in tools_for(profile, role="admin")}
    assert "search_sales_knowledge" in names
    assert "match_capabilities_to_lead" in names
    assert "get_relevant_case_studies" in names
    # request_deep_research is HIGH risk: above this profile's ceiling even
    # for an admin, because the profile is the narrower of the two limits.
    assert "request_deep_research" not in names
    ceiling = risk_rank(profile.max_risk)
    assert all(risk_rank(TOOL_REGISTRY[name].risk_level) <= ceiling for name in names)


def test_a_role_without_a_permission_never_sees_the_tools_needing_it() -> None:
    """A tool the caller cannot use is not described to the model at all."""
    member_permissions = agent_permissions_for_role("member")
    assert "research:run" not in member_permissions
    names = {tool.name for tool in tools_for(get_profile("research"), role="member")}
    assert "search_web_tavily" not in names
    assert "crawl_company_site" not in names
    assert "get_lead_context" in names

    admin_names = {tool.name for tool in tools_for(get_profile("research"), role="admin")}
    assert "search_web_tavily" in admin_names


def test_an_unknown_role_gets_no_agent_permissions_at_all() -> None:
    assert agent_permissions_for_role("contractor_from_a_deleted_tenant") == frozenset()
    assert tools_for(get_profile("research"), role="contractor_from_a_deleted_tenant") == []


def test_no_tool_is_exposed_at_blocked_risk() -> None:
    for profile in PROFILES.values():
        for tool in tools_for(profile, role="admin"):
            assert tool.risk_level != BLOCKED


def test_no_tool_schema_accepts_a_tenancy_parameter() -> None:
    """The structural half of the injection defence, across the whole registry."""
    forbidden = {"workspace_id", "workspace", "tenant_id", "user_id", "actor_id", "sql", "query_sql"}
    for tool in TOOL_REGISTRY.values():
        properties = tool.parameters.get("properties", {})
        assert not (set(properties) & forbidden), f"{tool.name} exposes tenancy input"


# --- capability matching: the backend decides, the model writes ------------


def test_opportunities_come_from_facts_and_carry_the_graph_confidence() -> None:
    matcher = CapabilityMatcher()
    session_factory: sessionmaker[Session] = _build_session_factory()
    with session_factory() as db:
        from app.modules.knowledge.service import KnowledgeService

        service = KnowledgeService()
        workspace, user = _seed_workspace(db, name="W1", email="w1@example.com")
        services_collection = _collection(
            service, db, workspace_id=workspace.id, slug="services", kind=SERVICES
        )
        _document(
            service,
            db,
            workspace_id=workspace.id,
            user_id=user.id,
            collection_id=services_collection,
            title="Online Booking Setup",
            content=(
                "# Online Booking Setup\n\n"
                "We install an online booking and appointment scheduling system with "
                "calendar sync and automated reminders."
            ),
        )
        cases_collection = _collection(
            service, db, workspace_id=workspace.id, slug="cases", kind=CASE_STUDIES
        )
        _document(
            service,
            db,
            workspace_id=workspace.id,
            user_id=user.id,
            collection_id=cases_collection,
            title="Clinic Booking Rollout",
            content=(
                "# Clinic Booking Rollout\n\n"
                "An online booking and appointment scheduling system took the clinic from "
                "phone-only to 40 percent self-serve bookings."
            ),
        )

        matches = matcher.match(
            db,
            workspace_id=workspace.id,
            graph=_graph(_fact("online_booking", "false", confidence=0.91)),
            user_id=user.id,
            user_role=user.role,
        )

        assert len(matches) == 1
        match = matches[0]
        assert match.opportunity_key == "no_online_booking"
        assert match.basis_claim_type == "online_booking"
        # The confidence is the Evidence Graph's, carried through unchanged.
        assert match.confidence == 0.91
        assert any(
            citation["document_title"] == "Online Booking Setup"
            for citation in match.capabilities
        )
        assert any(
            citation["document_title"] == "Clinic Booking Rollout" for citation in match.proof
        )


def test_a_lead_with_no_evidenced_problems_yields_no_opportunities() -> None:
    """Absence of evidence is never reported as a finding."""
    matcher = CapabilityMatcher()
    session_factory: sessionmaker[Session] = _build_session_factory()
    with session_factory() as db:
        workspace, user = _seed_workspace(db, name="W1", email="w1@example.com")
        graph = _graph(
            _fact("online_booking", "true"),
            _fact("has_whatsapp", "true"),
            _fact("has_ecommerce", "true"),
            _fact("website_url", "https://example.com"),
            _fact("social_presence", json.dumps(["instagram.com/acme"])),
            _fact("review_sentiment", "positive"),
        )
        assert (
            matcher.match(
                db,
                workspace_id=workspace.id,
                graph=graph,
                user_id=user.id,
                user_role=user.role,
            )
            == []
        )


def test_matches_are_ordered_by_evidence_confidence() -> None:
    matcher = CapabilityMatcher()
    session_factory: sessionmaker[Session] = _build_session_factory()
    with session_factory() as db:
        workspace, user = _seed_workspace(db, name="W1", email="w1@example.com")
        matches = matcher.match(
            db,
            workspace_id=workspace.id,
            graph=_graph(
                _fact("online_booking", "false", confidence=0.4),
                _fact("has_whatsapp", "false", confidence=0.95),
            ),
            user_id=user.id,
            user_role=user.role,
        )
        assert [match.opportunity_key for match in matches] == [
            "no_whatsapp_channel",
            "no_online_booking",
        ]


def test_low_digital_maturity_is_read_from_the_backend_band_not_inferred() -> None:
    matcher = CapabilityMatcher()
    session_factory: sessionmaker[Session] = _build_session_factory()
    with session_factory() as db:
        workspace, user = _seed_workspace(db, name="W1", email="w1@example.com")
        low = json.dumps({"band": "low", "score": 22, "components": {}})
        high = json.dumps({"band": "high", "score": 88, "components": {}})

        low_matches = matcher.match(
            db,
            workspace_id=workspace.id,
            graph=_graph(_fact("digital_maturity", low)),
            user_id=user.id,
            user_role=user.role,
        )
        assert [match.opportunity_key for match in low_matches] == ["low_digital_maturity"]

        high_matches = matcher.match(
            db,
            workspace_id=workspace.id,
            graph=_graph(_fact("digital_maturity", high)),
            user_id=user.id,
            user_role=user.role,
        )
        assert high_matches == []


# --- outreach factuality guard --------------------------------------------


def test_guard_blocks_a_number_the_run_never_retrieved() -> None:
    guard = OutreachQualityGuard()
    report = guard.check(
        subject="Quick idea for Acme Dental",
        body=(
            "Hi there, I noticed Acme Dental has no online booking. We typically cut no-show "
            "rates by 47 percent within a month, and I would love to show you how that would "
            "look for your clinic. Would a short call next week suit you?"
        ),
        grounding=["We install online booking systems with automated reminders."],
        lead_terms=["Acme Dental", "Riyadh"],
    )
    assert report.blocked
    codes = {finding.code for finding in report.findings}
    assert "unsupported_number" in codes
    assert any(finding.evidence.startswith("47") for finding in report.findings)


def test_guard_accepts_a_number_that_appears_in_retrieved_knowledge() -> None:
    guard = OutreachQualityGuard()
    report = guard.check(
        subject="Quick idea for Acme Dental",
        body=(
            "Hi there, I noticed Acme Dental has no online booking. For a clinic much like "
            "yours we cut the no-show rate by 31 percent in two months, and the same approach "
            "would fit your four branches. Would a short call next week suit you?"
        ),
        grounding=[
            "Riyadh Dental Group cut its no-show rate by 31 percent in two months after "
            "deploying reminder automation across four branches."
        ],
        lead_terms=["Acme Dental", "Riyadh"],
    )
    assert not report.blocked


def test_guard_blocks_guarantees_and_leftover_placeholders() -> None:
    guard = OutreachQualityGuard()
    report = guard.check(
        subject="Hello {{company}}",
        body=(
            "Hi [FIRST NAME], we guarantee you will double your revenue. "
            "Reply and we will get started right away with the rollout plan for your team."
        ),
        grounding=[],
        lead_terms=["Acme Dental"],
    )
    codes = {finding.code for finding in report.findings}
    assert "placeholder_left_in_draft" in codes
    assert "unbacked_guarantee" in codes
    assert report.blocked


def test_guard_warns_about_a_client_name_that_was_never_retrieved() -> None:
    guard = OutreachQualityGuard()
    report = guard.check(
        subject="Idea for Acme Dental",
        body=(
            "Hi there, we recently did exactly this for Northern Star Clinics and it worked "
            "well. I would love to walk you through how the same rollout would look for your "
            "practice, if you have fifteen minutes next week for a short call."
        ),
        grounding=["We install online booking systems with automated reminders."],
        lead_terms=["Acme Dental"],
    )
    codes = {finding.code for finding in report.findings}
    assert "unsupported_named_entity" in codes
    assert any("Northern Star Clinics" in finding.evidence for finding in report.findings)


def test_guard_passes_a_grounded_well_shaped_draft() -> None:
    guard = OutreachQualityGuard()
    report = guard.check(
        subject="Booking gap at Acme Dental",
        body=(
            "Hi there, I had a look at Acme Dental and noticed there is no way to book online, "
            "so every appointment still has to come through the phone. We install online "
            "booking with automated reminders, and for a clinic of a similar size that shifted "
            "a large share of bookings to self-serve without adding front-desk work. If it is "
            "useful, I can send over how that would look for your practice before we talk."
        ),
        grounding=[
            "We install online booking with automated reminders and calendar sync for clinics.",
        ],
        lead_terms=["Acme Dental", "Riyadh", "dental clinic"],
    )
    assert report.passed, [finding.code for finding in report.findings]
