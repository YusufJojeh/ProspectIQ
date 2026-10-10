from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime
from functools import lru_cache

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# --- Provider pricing -----------------------------------------------------
#
# Prices belong in configuration, not in business logic. Providers change
# their rates without asking us, and a rate compiled into a scoring or
# budgeting function is a number nobody can correct without a deploy.
#
# The other half of that principle matters just as much: an UNKNOWN price is
# represented as None and stays None. It is never silently replaced by zero,
# because a ledger that reports $0.00 for an unpriced model reads exactly
# like a ledger that reports a free call, and a budget built on that would
# never trip. Callers must handle None explicitly.
#
# Rates are expressed in micro-USD per 1,000 tokens (integers), so the whole
# cost path stays in integer arithmetic -- float drift over thousands of
# small calls is a real source of disagreement between a bill and a ledger.

MICRO = 1_000_000


@dataclass(frozen=True, slots=True)
class ProviderPricing:
    provider: str
    model: str
    #: micro-USD per 1,000 input tokens.
    input_rate_micro_per_1k: int | None = None
    #: micro-USD per 1,000 output tokens.
    output_rate_micro_per_1k: int | None = None
    #: micro-USD per 1,000 embedded tokens.
    embedding_rate_micro_per_1k: int | None = None
    #: micro-USD for one unit of a non-token-priced operation: a Tavily or
    #: SerpAPI search, an Apify actor run. Providers bill these per call.
    unit_rate_micro: int | None = None
    #: The date this rate took effect. The most recent rate not in the
    #: future wins, so a scheduled price change can be configured ahead of
    #: time without rewriting history: a run costed last month keeps the
    #: figure it was costed with, because the ledger stores the result.
    effective_from: date | None = None

    @property
    def key(self) -> tuple[str, str]:
        return (self.provider.lower(), self.model.lower())


def _parse_date(value: object) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def _parse_int(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(round(value))
    if isinstance(value, str) and value.strip():
        try:
            return int(round(float(value)))
        except ValueError:
            return None
    return None


def _parse_entry(raw: object) -> ProviderPricing | None:
    if not isinstance(raw, dict):
        return None
    provider = str(raw.get("provider") or "").strip()
    model = str(raw.get("model") or "").strip()
    if not provider or not model:
        return None
    return ProviderPricing(
        provider=provider,
        model=model,
        input_rate_micro_per_1k=_parse_int(raw.get("input_rate_micro_per_1k")),
        output_rate_micro_per_1k=_parse_int(raw.get("output_rate_micro_per_1k")),
        embedding_rate_micro_per_1k=_parse_int(raw.get("embedding_rate_micro_per_1k")),
        unit_rate_micro=_parse_int(raw.get("unit_rate_micro")),
        effective_from=_parse_date(raw.get("effective_from")),
    )


def parse_pricing(raw_json: str) -> tuple[ProviderPricing, ...]:
    """Parse a pricing table from JSON, ignoring entries we cannot read.

    A malformed pricing table must not take the application down, and must
    not be guessed at either: unreadable entries are dropped and logged, and
    the models they covered simply become unpriced.
    """
    if not raw_json.strip():
        return ()
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError:
        logger.warning("provider_pricing_json_invalid")
        return ()
    if not isinstance(payload, list):
        logger.warning("provider_pricing_json_not_a_list")
        return ()
    entries = [_parse_entry(item) for item in payload]
    return tuple(entry for entry in entries if entry is not None)


class PricingTable:
    """Resolves (provider, model) to the rate in force on a given date."""

    def __init__(self, entries: tuple[ProviderPricing, ...]) -> None:
        self._entries = entries

    def resolve(
        self, *, provider: str, model: str, on: date | None = None
    ) -> ProviderPricing | None:
        as_of = on or datetime.now(tz=UTC).date()
        key = (provider.lower(), model.lower())
        candidates = [
            entry
            for entry in self._entries
            if entry.key == key
            and (entry.effective_from is None or entry.effective_from <= as_of)
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda entry: entry.effective_from or date.min)

    def token_cost_micro_usd(
        self,
        *,
        provider: str,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        embedding_tokens: int = 0,
        on: date | None = None,
    ) -> int | None:
        """Cost in micro-USD, or None when this model has no configured rate.

        None means "we do not know", never "free". A partially-configured
        entry still prices the components it covers: an input rate with no
        output rate yields the input cost, because a known lower bound is
        more useful than discarding the whole measurement.
        """
        pricing = self.resolve(provider=provider, model=model, on=on)
        if pricing is None:
            return None
        components = (
            (input_tokens, pricing.input_rate_micro_per_1k),
            (output_tokens, pricing.output_rate_micro_per_1k),
            (embedding_tokens, pricing.embedding_rate_micro_per_1k),
        )
        priced = [
            (tokens * rate) // 1000
            for tokens, rate in components
            if rate is not None and tokens > 0
        ]
        if not priced:
            # The entry exists but prices nothing we consumed. That is still
            # "unknown", not zero.
            return None if any(tokens > 0 for tokens, _rate in components) else 0
        return sum(priced)

    def unit_cost_micro_usd(
        self, *, provider: str, model: str, units: int = 1, on: date | None = None
    ) -> int | None:
        pricing = self.resolve(provider=provider, model=model, on=on)
        if pricing is None or pricing.unit_rate_micro is None:
            return None
        return pricing.unit_rate_micro * units


@lru_cache(maxsize=1)
def _cached_table(raw_json: str) -> PricingTable:
    return PricingTable(parse_pricing(raw_json))


def get_pricing_table() -> PricingTable:
    """The configured pricing table.

    Deliberately empty by default: this repository ships no provider rates,
    because a stale hardcoded rate is worse than an honest "unknown". Deploy
    with PROVIDER_PRICING_JSON set from whatever the account is actually
    billed.
    """
    return _cached_table(get_settings().provider_pricing_json)


__all__ = [
    "MICRO",
    "PricingTable",
    "ProviderPricing",
    "get_pricing_table",
    "parse_pricing",
]
