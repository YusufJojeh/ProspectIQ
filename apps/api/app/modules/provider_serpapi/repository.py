from __future__ import annotations

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.modules.leads.models import Lead
from app.modules.provider_serpapi.models import (
    LeadIdentity,
    LeadSourceRecord,
    ProviderNormalizedFact,
)
from app.modules.provider_serpapi.schemas import LeadIdentityCandidate, PlaceLookupKey


class ProviderEvidenceRepository:
    _IDENTITY_WEIGHTS = {
        "data_cid": 120,
        "data_id": 110,
        "place_id": 100,
        "phone": 70,
        "website_domain": 50,
        "fingerprint": 30,
    }

    def find_lead_by_identities(
        self,
        db: Session,
        *,
        workspace_id: int,
        identities: list[LeadIdentityCandidate],
    ) -> Lead | None:
        if not identities:
            return None

        conditions = [
            and_(
                LeadIdentity.identity_type == identity.identity_type,
                LeadIdentity.identity_value == identity.identity_value,
            )
            for identity in identities
        ]
        statement = (
            select(LeadIdentity.lead_id, LeadIdentity.identity_type)
            .join(Lead, LeadIdentity.lead_id == Lead.id)
            .where(
                Lead.workspace_id == workspace_id,
                LeadIdentity.workspace_id == workspace_id,
                or_(*conditions),
            )
        )
        matches = db.execute(statement).all()
        if not matches:
            return None

        lead_scores: dict[int, tuple[int, int]] = {}
        for lead_id, identity_type in matches:
            identity_weight = self._IDENTITY_WEIGHTS.get(str(identity_type), 10)
            score, count = lead_scores.get(int(lead_id), (0, 0))
            lead_scores[int(lead_id)] = (score + identity_weight, count + 1)

        best_lead_id = min(
            lead_scores.items(),
            key=lambda item: (-item[1][0], -item[1][1], item[0]),
        )[0]
        return db.get(Lead, best_lead_id)

    def save_lead(self, db: Session, lead: Lead) -> Lead:
        db.add(lead)
        db.commit()
        db.refresh(lead)
        return lead

    def ensure_identities(
        self,
        db: Session,
        *,
        workspace_id: int,
        lead_id: int,
        identities: list[LeadIdentityCandidate],
    ) -> None:
        if not identities:
            return

        existing_statement = select(LeadIdentity).where(
            LeadIdentity.workspace_id == workspace_id,
            LeadIdentity.lead_id == lead_id,
        )
        existing = {
            (item.identity_type, item.identity_value) for item in db.scalars(existing_statement)
        }
        to_add = [
            LeadIdentity(
                workspace_id=workspace_id,
                lead_id=lead_id,
                identity_type=identity.identity_type,
                identity_value=identity.identity_value,
            )
            for identity in identities
            if (identity.identity_type, identity.identity_value) not in existing
        ]
        if to_add:
            db.add_all(to_add)
            db.commit()

    def add_normalized_fact(
        self, db: Session, fact: ProviderNormalizedFact
    ) -> ProviderNormalizedFact:
        db.add(fact)
        db.commit()
        db.refresh(fact)
        return fact

    def set_source_record(
        self,
        db: Session,
        *,
        lead_id: int,
        provider_normalized_fact_id: int,
        priority: int,
        is_current: bool,
    ) -> None:
        if is_current:
            current_statement = select(LeadSourceRecord).where(
                LeadSourceRecord.lead_id == lead_id,
                LeadSourceRecord.is_current == True,  # noqa: E712
            )
            for record in db.scalars(current_statement):
                record.is_current = False
                db.add(record)
            db.commit()

        db.add(
            LeadSourceRecord(
                lead_id=lead_id,
                provider_normalized_fact_id=provider_normalized_fact_id,
                priority=priority,
                is_current=is_current,
            )
        )
        db.commit()

    def get_best_source_priority(self, db: Session, lead_id: int) -> int | None:
        statement = (
            select(LeadSourceRecord.priority)
            .where(LeadSourceRecord.lead_id == lead_id, LeadSourceRecord.is_current == True)  # noqa: E712
            .order_by(LeadSourceRecord.priority.asc())
            .limit(1)
        )
        return db.scalar(statement)

    def list_normalized_facts_for_lead(
        self, db: Session, lead_id: int
    ) -> list[ProviderNormalizedFact]:
        statement = (
            select(ProviderNormalizedFact)
            .where(ProviderNormalizedFact.lead_id == lead_id)
            .order_by(ProviderNormalizedFact.created_at.desc(), ProviderNormalizedFact.id.desc())
        )
        return list(db.scalars(statement))

    def get_latest_visibility(self, db: Session, lead_id: int) -> tuple[float | None, str | None]:
        statement = (
            select(ProviderNormalizedFact)
            .where(
                ProviderNormalizedFact.lead_id == lead_id,
                ProviderNormalizedFact.source_type == "web_search",
            )
            .order_by(ProviderNormalizedFact.created_at.desc())
            .limit(1)
        )
        item = db.scalar(statement)
        if item is None:
            return None, None
        visibility_confidence = item.facts_json.get("visibility_confidence")
        source = item.facts_json.get("source")
        confidence = (
            float(visibility_confidence)
            if isinstance(visibility_confidence, (int, float))
            else None
        )
        return confidence, source if isinstance(source, str) else None

    def get_best_place_lookup(self, db: Session, lead_id: int) -> PlaceLookupKey | None:
        statement = (
            select(ProviderNormalizedFact)
            .where(
                ProviderNormalizedFact.lead_id == lead_id,
                ProviderNormalizedFact.source_type.in_(("maps_place", "maps_search")),
            )
            .order_by(ProviderNormalizedFact.created_at.desc())
        )
        for item in db.scalars(statement):
            if item.place_id:
                return PlaceLookupKey(key_type="place_id", value=item.place_id)
            if item.data_cid:
                return PlaceLookupKey(key_type="data_cid", value=item.data_cid)
            if item.data_id:
                return PlaceLookupKey(key_type="data", value=item.data_id)
        return None
