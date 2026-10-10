from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

# Pure document rules: arithmetic and readiness. No database, no clock --
# `today` is passed in -- so the same rules can be tested exhaustively and
# applied identically by the API and the copilot tool.

#: The kits ship with bracketed placeholders ("[Client Company]"). A
#: document still containing one is a template, not a proposal.
_PLACEHOLDER = re.compile(r"\[[^\]\n]{1,80}\]")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

MAX_AMOUNT_MINOR = 10**12

STATUS_DRAFT = "draft"
STATUS_READY = "ready"
STATUS_SENT = "sent"
STATUS_ACCEPTED = "accepted"
STATUS_DECLINED = "declined"
STATUSES: tuple[str, ...] = (
    STATUS_DRAFT,
    STATUS_READY,
    STATUS_SENT,
    STATUS_ACCEPTED,
    STATUS_DECLINED,
)
EDITABLE_STATUSES = frozenset({STATUS_DRAFT, STATUS_READY})

ISSUE_MISSING_TITLE = "missing_title"
ISSUE_MISSING_CLIENT_COMPANY = "missing_client_company"
ISSUE_MISSING_CLIENT_EMAIL = "missing_client_email"
ISSUE_INVALID_CLIENT_EMAIL = "invalid_client_email"
ISSUE_MISSING_OUTCOME = "missing_outcome"
ISSUE_NO_MILESTONES = "no_milestones"
ISSUE_MILESTONE_MISSING_TITLE = "milestone_missing_title"
ISSUE_MILESTONE_MISSING_AMOUNT = "milestone_missing_amount"
ISSUE_INVALID_VALIDITY = "invalid_validity"
ISSUE_EXPIRED = "expired"
ISSUE_PLACEHOLDER_TEXT = "placeholder_text"


@dataclass(frozen=True, slots=True)
class Totals:
    total_minor: int
    deposit_minor: int
    remaining_minor: int


def amount_of(milestone: dict[str, Any]) -> int | None:
    value = milestone.get("amount_minor")
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def compute_totals(milestones: list[dict[str, Any]]) -> Totals:
    """Total of every priced line; the deposit is the first milestone.

    That is the kits' commercial structure: "the first payment reserves the
    engagement", and the remaining invoices follow the later milestones.
    """
    amounts = [amount_of(item) or 0 for item in milestones]
    total = sum(amounts)
    deposit = amounts[0] if amounts else 0
    return Totals(total_minor=total, deposit_minor=deposit, remaining_minor=total - deposit)


def share_pct(amount_minor: int | None, total_minor: int) -> float | None:
    if amount_minor is None or total_minor <= 0:
        return None
    return round(amount_minor * 100 / total_minor, 1)


def has_placeholder(*texts: str | None) -> bool:
    return any(text and _PLACEHOLDER.search(text) for text in texts)


def readiness_issues(
    *,
    title: str,
    client_company: str,
    client_email: str | None,
    client_contact_name: str | None,
    client_location: str | None,
    outcome: str,
    milestones: list[dict[str, Any]],
    commercial_notes: str,
    validity_notes: str,
    issue_date: date,
    valid_until: date,
    today: date,
) -> list[str]:
    """Everything that stops this document from being sent as-is.

    Ordered as a person would fix it, top of the page to the bottom.
    """
    issues: list[str] = []
    if not title.strip():
        issues.append(ISSUE_MISSING_TITLE)
    if not client_company.strip():
        issues.append(ISSUE_MISSING_CLIENT_COMPANY)
    email = (client_email or "").strip()
    if not email:
        issues.append(ISSUE_MISSING_CLIENT_EMAIL)
    elif not _EMAIL.match(email):
        issues.append(ISSUE_INVALID_CLIENT_EMAIL)
    if valid_until <= issue_date:
        issues.append(ISSUE_INVALID_VALIDITY)
    elif valid_until < today:
        issues.append(ISSUE_EXPIRED)
    if not outcome.strip():
        issues.append(ISSUE_MISSING_OUTCOME)
    if not milestones:
        issues.append(ISSUE_NO_MILESTONES)
    if any(not str(item.get("title") or "").strip() for item in milestones):
        issues.append(ISSUE_MILESTONE_MISSING_TITLE)
    if any((amount_of(item) or 0) <= 0 for item in milestones):
        issues.append(ISSUE_MILESTONE_MISSING_AMOUNT)
    milestone_texts = [
        text
        for item in milestones
        for text in (str(item.get("title") or ""), str(item.get("description") or ""))
    ]
    if has_placeholder(
        title,
        client_company,
        client_email,
        client_contact_name,
        client_location,
        outcome,
        commercial_notes,
        validity_notes,
        *milestone_texts,
    ):
        issues.append(ISSUE_PLACEHOLDER_TEXT)
    return issues


def next_number(prefix: str, year: int, existing: list[str]) -> str:
    """`{prefix}-{year}-{seq:03d}`, one past the highest already issued.

    Taken from the highest existing sequence rather than a count, so a
    deleted or skipped number can never be issued twice.
    """
    stem = f"{prefix}-{year}-"
    highest = 0
    for number in existing:
        if not number.startswith(stem):
            continue
        tail = number[len(stem) :]
        if tail.isdigit():
            highest = max(highest, int(tail))
    return f"{stem}{highest + 1:03d}"
