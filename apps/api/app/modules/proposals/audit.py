from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median

# Pure rules for the client-facing presence audit: what we can say about a
# business from facts we already hold, and how it compares with similar
# businesses found in the same search. No database and no clock, so every
# rule is tested directly. Findings carry codes and numbers only; the
# document renders them in the reader's language.

STATUS_GOOD = "good"
STATUS_IMPROVE = "improve"
STATUS_MISSING = "missing"

FINDING_WEBSITE = "website"
FINDING_RATING = "rating"
FINDING_REVIEWS = "reviews"
FINDING_PHONE = "phone"
FINDING_EMAIL = "email"
FINDING_SOCIAL = "social"

#: Below this a rating reads as a problem to a local customer.
GOOD_RATING = 4.5
#: Fewer reviews than this look thin, whatever the peers do.
ENOUGH_REVIEWS = 20
#: A benchmark of fewer businesses than this is not shown: it would be noise
#: and could single out one competitor.
MIN_PEERS = 3


@dataclass(frozen=True, slots=True)
class LeadFacts:
    has_website: bool
    rating: float | None
    review_count: int
    has_phone: bool
    has_email: bool
    has_social: bool


@dataclass(frozen=True, slots=True)
class PeerFacts:
    rating: float | None
    review_count: int
    has_website: bool


@dataclass(frozen=True, slots=True)
class Benchmark:
    peer_count: int
    median_rating: float | None
    median_reviews: int
    website_pct: int


@dataclass(frozen=True, slots=True)
class Finding:
    key: str
    status: str
    values: dict[str, float | int] = field(default_factory=dict)


def benchmark(peers: list[PeerFacts]) -> Benchmark | None:
    if len(peers) < MIN_PEERS:
        return None
    ratings = [peer.rating for peer in peers if peer.rating is not None]
    return Benchmark(
        peer_count=len(peers),
        median_rating=round(median(ratings), 1) if ratings else None,
        median_reviews=round(median(peer.review_count for peer in peers)),
        website_pct=round(100 * sum(peer.has_website for peer in peers) / len(peers)),
    )


def _present(key: str, present: bool) -> Finding:
    return Finding(key=key, status=STATUS_GOOD if present else STATUS_MISSING)


def build_findings(facts: LeadFacts, bench: Benchmark | None) -> list[Finding]:
    """One finding per check, opportunities first so the page leads with them."""
    findings = [
        _website(facts, bench),
        _rating(facts, bench),
        _reviews(facts, bench),
        _present(FINDING_PHONE, facts.has_phone),
        _present(FINDING_EMAIL, facts.has_email),
        _present(FINDING_SOCIAL, facts.has_social),
    ]
    order = {STATUS_MISSING: 0, STATUS_IMPROVE: 1, STATUS_GOOD: 2}
    return sorted(findings, key=lambda finding: order[finding.status])


def _website(facts: LeadFacts, bench: Benchmark | None) -> Finding:
    values: dict[str, float | int] = {}
    if bench is not None:
        values["peer_pct"] = bench.website_pct
    return Finding(
        key=FINDING_WEBSITE,
        status=STATUS_GOOD if facts.has_website else STATUS_MISSING,
        values=values,
    )


def _rating(facts: LeadFacts, bench: Benchmark | None) -> Finding:
    if facts.rating is None:
        return Finding(key=FINDING_RATING, status=STATUS_MISSING)
    values: dict[str, float | int] = {"rating": round(facts.rating, 1)}
    below_peers = False
    if bench is not None and bench.median_rating is not None:
        values["peer_median"] = bench.median_rating
        below_peers = facts.rating < bench.median_rating
    good = facts.rating >= GOOD_RATING and not below_peers
    return Finding(key=FINDING_RATING, status=STATUS_GOOD if good else STATUS_IMPROVE, values=values)


def _reviews(facts: LeadFacts, bench: Benchmark | None) -> Finding:
    if facts.review_count <= 0:
        return Finding(key=FINDING_REVIEWS, status=STATUS_MISSING)
    values: dict[str, float | int] = {"count": facts.review_count}
    below_peers = False
    if bench is not None:
        values["peer_median"] = bench.median_reviews
        below_peers = facts.review_count < bench.median_reviews
    good = facts.review_count >= ENOUGH_REVIEWS and not below_peers
    return Finding(key=FINDING_REVIEWS, status=STATUS_GOOD if good else STATUS_IMPROVE, values=values)
