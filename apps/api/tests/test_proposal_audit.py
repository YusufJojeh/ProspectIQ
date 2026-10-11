from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select
from test_workspace_e2e import _build_session_factory, _login, _override_client, _seed_workspace

from app.core.config import clear_settings_cache
from app.modules.leads.models import Lead
from app.modules.proposals.audit import (
    MIN_PEERS,
    LeadFacts,
    PeerFacts,
    benchmark,
    build_findings,
)
from app.modules.signals.models import LeadSignal
from app.modules.users.models import Workspace


def _facts(**overrides: Any) -> LeadFacts:
    values: dict[str, Any] = {
        "has_website": True,
        "rating": 4.8,
        "review_count": 120,
        "has_phone": True,
        "has_email": True,
        "has_social": True,
    }
    values.update(overrides)
    return LeadFacts(**values)


def _statuses(facts: LeadFacts, peers: list[PeerFacts] | None = None) -> dict[str, str]:
    return {item.key: item.status for item in build_findings(facts, benchmark(peers or []))}


def test_a_strong_presence_has_no_opportunities() -> None:
    assert set(_statuses(_facts()).values()) == {"good"}


def test_gaps_are_missing_and_listed_first() -> None:
    findings = build_findings(_facts(has_website=False, rating=None, review_count=0), None)
    assert [item.status for item in findings[:3]] == ["missing", "missing", "missing"]
    assert {item.key for item in findings[:3]} == {"website", "rating", "reviews"}


def test_ratings_and_reviews_are_judged_against_similar_businesses() -> None:
    peers = [PeerFacts(rating=4.9, review_count=300, has_website=True) for _ in range(4)]
    statuses = _statuses(_facts(rating=4.6, review_count=80), peers)
    assert statuses["rating"] == "improve"
    assert statuses["reviews"] == "improve"
    # Without peers the same numbers are fine on their own.
    assert _statuses(_facts(rating=4.6, review_count=80))["rating"] == "good"


def test_a_benchmark_needs_enough_businesses() -> None:
    peer = PeerFacts(rating=4.0, review_count=10, has_website=False)
    assert benchmark([peer] * (MIN_PEERS - 1)) is None
    bench = benchmark(
        [peer, PeerFacts(rating=None, review_count=30, has_website=True), peer, peer]
    )
    assert bench is not None
    assert bench.median_rating == 4.0
    assert bench.median_reviews == 10
    assert bench.website_pct == 25


def _client_setup(monkeypatch: pytest.MonkeyPatch) -> tuple[Any, Any]:
    monkeypatch.setenv("APP_ENV", "test")
    clear_settings_cache()
    session_factory = _build_session_factory()
    return session_factory, _seed_workspace(session_factory)


def test_the_audit_compares_a_lead_with_its_search(monkeypatch: pytest.MonkeyPatch) -> None:
    session_factory, seed = _client_setup(monkeypatch)
    with session_factory() as db:
        lead = db.scalar(select(Lead).where(Lead.public_id == seed.lead_public_id))
        assert lead is not None
        for index, (rating, reviews) in enumerate([(4.9, 200), (4.8, 150), (4.9, 90)]):
            db.add(
                Lead(
                    workspace_id=lead.workspace_id,
                    search_job_id=lead.search_job_id,
                    company_name=f"Peer {index}",
                    rating=rating,
                    review_count=reviews,
                    has_website=True,
                )
            )
        db.add(
            LeadSignal(
                workspace_id=lead.workspace_id,
                lead_id=lead.id,
                signal_type="hiring",
                signal_strength=0.8,
                evidence_text="Hiring a receptionist.",
                source_url="javascript:alert(1)",
            )
        )
        db.commit()

    with _override_client(session_factory) as client:
        headers = {"Authorization": f"Bearer {_login(client, seed)}"}
        response = client.get(f"/api/v1/proposals/lead-audit/{seed.lead_public_id}", headers=headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["company_name"] == "Acme Dental"
        assert body["benchmark"] == {
            "peer_count": 3,
            "median_rating": 4.9,
            "median_reviews": 150,
            "website_pct": 100,
        }
        findings = {item["key"]: item for item in body["findings"]}
        # 4.7 stars and 24 reviews trail the businesses found alongside it.
        assert findings["rating"]["status"] == "improve"
        assert findings["rating"]["values"] == {"rating": 4.7, "peer_median": 4.9}
        assert findings["reviews"]["status"] == "improve"
        assert findings["website"]["status"] == "good"
        # Evidence is kept, but a non-web link is never printed as a source.
        assert body["evidence"] == [
            {"signal_type": "hiring", "text": "Hiring a receptionist.", "source_url": None}
        ]


def test_the_audit_is_scoped_to_the_workspace(monkeypatch: pytest.MonkeyPatch) -> None:
    session_factory, seed = _client_setup(monkeypatch)
    with session_factory() as db:
        other = Workspace(public_id="ws_other", name="Other")
        db.add(other)
        db.commit()
        foreign = Lead(workspace_id=other.id, company_name="Elsewhere Dental")
        db.add(foreign)
        db.commit()
        foreign_id = foreign.public_id

    with _override_client(session_factory) as client:
        headers = {"Authorization": f"Bearer {_login(client, seed)}"}
        response = client.get(f"/api/v1/proposals/lead-audit/{foreign_id}", headers=headers)
        assert response.status_code == 404
