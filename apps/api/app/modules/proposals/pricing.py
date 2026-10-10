from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from app.modules.proposals.documents import MAX_AMOUNT_MINOR

# "7,500", "7500.00", "7.5k", "12K" -- the ways a price shows up in prose.
_NUMBER = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?\s*([kK])?(?![\w])")

PRICING_GROUNDED = "grounded"
PRICING_PARTIAL = "partial"
PRICING_NEEDS_PRICING = "needs_pricing"


@dataclass(frozen=True, slots=True)
class PricingGrounding:
    #: Per input line: the accepted amount in minor units, or None.
    amounts_minor: list[int | None]
    status: str


def _to_minor(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    try:
        minor = int((Decimal(str(value)) * 100).quantize(Decimal(1)))
    except InvalidOperation:
        return None
    if minor <= 0 or minor > MAX_AMOUNT_MINOR:
        return None
    return minor


def prices_in(texts: list[str]) -> set[int]:
    """Every amount (in minor units) mentioned anywhere in `texts`."""
    found: set[int] = set()
    for text in texts:
        for whole, fraction, thousands in _NUMBER.findall(text):
            try:
                value = Decimal(whole.replace(",", "") + (fraction or ""))
            except InvalidOperation:
                continue
            if thousands:
                value *= 1000
            found.add(int((value * 100).quantize(Decimal(1))))
    return found


def ground_milestone_amounts(amounts: list[object], grounding: list[str]) -> PricingGrounding:
    """Keep only amounts backed by retrieved pricing.

    A line is backed when its own amount appears in the grounding, or when
    the sum of all proposed lines does (a package price split across
    milestones). Anything else is dropped to None -- unpriced, never guessed.
    """
    proposed = [_to_minor(value) for value in amounts]
    known = prices_in(grounding)
    priced = [value for value in proposed if value is not None]
    total_backed = bool(priced) and len(priced) == len(proposed) and sum(priced) in known
    accepted = [
        value if value is not None and (total_backed or value in known) else None
        for value in proposed
    ]
    kept = sum(1 for value in accepted if value is not None)
    if accepted and kept == len(accepted):
        status = PRICING_GROUNDED
    elif kept:
        status = PRICING_PARTIAL
    else:
        status = PRICING_NEEDS_PRICING
    return PricingGrounding(amounts_minor=accepted, status=status)
