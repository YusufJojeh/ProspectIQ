from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.enrichers.base import BaseLeadEnricher, EnrichmentPayload
from app.modules.provider_serpapi.client import SerpApiClient
from app.modules.provider_serpapi.engines.linkedin import (
    build_linkedin_company_params,
    extract_company_url,
    run_linkedin_company,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.modules.leads.models import Lead


class LinkedInEnricher(BaseLeadEnricher):
    """Best-effort LinkedIn company-page discovery via a scoped web search.

    Emits ``linkedin_url`` when a ``linkedin.com/company`` result is found. The
    discovery pipeline promotes this value onto the typed ``Lead.linkedin_url``
    column. No contact/employee data is fetched (no provider available).
    """

    name = "linkedin"

    def __init__(self, client: SerpApiClient) -> None:
        self._client = client

    def enrich(self, lead: Lead, *, db: Session) -> EnrichmentPayload:
        params = build_linkedin_company_params(
            company_name=lead.company_name,
            city=lead.city,
        )
        result = run_linkedin_company(self._client, params=params)
        company_url = extract_company_url(result)
        if not company_url:
            return EnrichmentPayload.empty(self.name)
        data: dict[str, Any] = {"linkedin_url": company_url}
        return EnrichmentPayload(source=self.name, data=data)
