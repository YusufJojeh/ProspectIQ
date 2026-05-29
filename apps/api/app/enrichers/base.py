from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.modules.leads.models import Lead

logger = logging.getLogger(__name__)


@dataclass
class EnrichmentPayload:
    """Result of a single enricher run. `data` is empty when nothing was found."""

    source: str
    data: dict[str, Any] = field(default_factory=dict)
    ok: bool = True

    @classmethod
    def empty(cls, source: str) -> EnrichmentPayload:
        return cls(source=source, data={}, ok=False)


class BaseLeadEnricher(ABC):
    """Base class for lead enrichers.

    Enrichers must never raise: callers should invoke `safe_enrich`, which
    catches every exception, logs a WARNING, and returns an empty payload.
    """

    name: str = "base"

    @abstractmethod
    def enrich(self, lead: Lead, *, db: Session) -> EnrichmentPayload: ...

    def safe_enrich(self, lead: Lead, *, db: Session) -> EnrichmentPayload:
        try:
            return self.enrich(lead, db=db)
        except Exception as exc:
            logger.warning(
                "enricher.failed name=%s lead=%s error=%s",
                self.name,
                lead.public_id,
                exc,
            )
            return EnrichmentPayload.empty(self.name)
