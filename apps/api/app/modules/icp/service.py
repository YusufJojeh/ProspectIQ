from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.modules.icp.models import IcpProfile, LeadIcpMatch
from app.modules.icp.repository import IcpProfileRepository
from app.modules.icp.schemas import (
    IcpProfileCreateRequest,
    IcpProfileListResponse,
    IcpProfileResponse,
    IcpProfileUpdateRequest,
    LeadIcpMatchListResponse,
    LeadIcpMatchResponse,
)
from app.modules.leads.models import Lead
from app.modules.leads.repository import LeadsRepository
from app.modules.signals.models import LeadSignal
from app.shared.enums.jobs import WebsitePreference


class IcpProfileService:
    def __init__(self) -> None:
        self.repository = IcpProfileRepository()
        self.leads_repository = LeadsRepository()

    def list_profiles(self, db: Session, *, workspace_id: int) -> IcpProfileListResponse:
        return IcpProfileListResponse(
            items=[
                self._to_profile_response(profile)
                for profile in self.repository.list_for_workspace(db, workspace_id=workspace_id)
            ]
        )

    def create_profile(
        self,
        db: Session,
        *,
        workspace_id: int,
        created_by_user_id: int,
        payload: IcpProfileCreateRequest,
    ) -> IcpProfileResponse:
        profile = IcpProfile(
            workspace_id=workspace_id,
            created_by_user_id=created_by_user_id,
            **payload.model_dump(mode="json"),
        )
        return self._to_profile_response(self.repository.save(db, profile))

    def update_profile(
        self,
        db: Session,
        *,
        workspace_id: int,
        profile_public_id: str,
        payload: IcpProfileUpdateRequest,
    ) -> IcpProfileResponse:
        profile = self._get_profile_or_raise(db, workspace_id, profile_public_id)
        for key, value in payload.model_dump(exclude_unset=True, mode="json").items():
            setattr(profile, key, value)
        profile.updated_at = datetime.now(tz=UTC)
        return self._to_profile_response(self.repository.save(db, profile))

    def delete_profile(self, db: Session, *, workspace_id: int, profile_public_id: str) -> None:
        profile = self._get_profile_or_raise(db, workspace_id, profile_public_id)
        self.repository.delete(db, profile)

    def recompute_lead_matches(
        self,
        db: Session,
        *,
        workspace_id: int,
        lead_public_id: str,
        signals: list[LeadSignal] | None = None,
    ) -> LeadIcpMatchListResponse:
        lead = self.leads_repository.get_by_public_id_for_workspace(
            db, workspace_id=workspace_id, public_id=lead_public_id
        )
        if lead is None:
            raise NotFoundError("Lead was not found.")
        matches = LeadIcpMatcherService(self.repository).recompute_for_lead(
            db, workspace_id=workspace_id, lead=lead, signals=signals
        )
        return LeadIcpMatchListResponse(
            items=[self._to_match_response(db, lead, match) for match in matches]
        )

    def recompute_profile_match(
        self,
        db: Session,
        *,
        workspace_id: int,
        profile_public_id: str,
        lead_public_id: str,
        signals: list[LeadSignal] | None = None,
    ) -> LeadIcpMatchResponse:
        profile = self._get_profile_or_raise(db, workspace_id, profile_public_id)
        lead = self.leads_repository.get_by_public_id_for_workspace(
            db, workspace_id=workspace_id, public_id=lead_public_id
        )
        if lead is None:
            raise NotFoundError("Lead was not found.")
        match = LeadIcpMatcherService(self.repository).upsert_match(
            db, workspace_id=workspace_id, lead=lead, profile=profile, signals=signals
        )
        return self._to_match_response(db, lead, match)

    def _get_profile_or_raise(
        self, db: Session, workspace_id: int, profile_public_id: str
    ) -> IcpProfile:
        profile = self.repository.get_by_public_id(
            db, workspace_id=workspace_id, public_id=profile_public_id
        )
        if profile is None:
            raise NotFoundError("ICP profile was not found.")
        return profile

    def _to_profile_response(self, profile: IcpProfile) -> IcpProfileResponse:
        return IcpProfileResponse(
            public_id=profile.public_id,
            name=profile.name,
            description=profile.description,
            target_industries=list(profile.target_industries or []),
            target_cities=list(profile.target_cities or []),
            min_rating=profile.min_rating,
            max_rating=profile.max_rating,
            min_reviews=profile.min_reviews,
            max_reviews=profile.max_reviews,
            website_preference=WebsitePreference(profile.website_preference),
            required_signals=list(profile.required_signals or []),
            excluded_keywords=list(profile.excluded_keywords or []),
            is_active=profile.is_active,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )

    def _to_match_response(
        self, db: Session, lead: Lead, match: LeadIcpMatch
    ) -> LeadIcpMatchResponse:
        profile = db.get(IcpProfile, match.icp_profile_id)
        profile_public_id = profile.public_id if profile else "unknown"
        return LeadIcpMatchResponse(
            public_id=match.public_id,
            lead_id=lead.public_id,
            icp_profile_id=profile_public_id,
            fit_score=match.fit_score,
            matched=match.matched,
            match_reasons=dict(match.match_reasons_json or {}),
            calculated_at=match.calculated_at,
        )


class LeadIcpMatcherService:
    def __init__(self, repository: IcpProfileRepository | None = None) -> None:
        self.repository = repository or IcpProfileRepository()

    def recompute_for_lead(
        self,
        db: Session,
        *,
        workspace_id: int,
        lead: Lead,
        signals: list[LeadSignal] | None = None,
    ) -> list[LeadIcpMatch]:
        profiles = self.repository.list_for_workspace(
            db, workspace_id=workspace_id, active_only=True
        )
        return [
            self.upsert_match(
                db,
                workspace_id=workspace_id,
                lead=lead,
                profile=profile,
                signals=signals,
            )
            for profile in profiles
        ]

    def best_match_for_lead(
        self, db: Session, *, workspace_id: int, lead_id: int
    ) -> LeadIcpMatch | None:
        matches = self.repository.list_matches_for_lead(
            db, workspace_id=workspace_id, lead_id=lead_id
        )
        return matches[0] if matches else None

    def upsert_match(
        self,
        db: Session,
        *,
        workspace_id: int,
        lead: Lead,
        profile: IcpProfile,
        signals: list[LeadSignal] | None = None,
    ) -> LeadIcpMatch:
        score, matched, reasons = self.calculate_fit(lead, profile, signals=signals)
        match = self.repository.get_match(
            db, workspace_id=workspace_id, lead_id=lead.id, icp_profile_id=profile.id
        )
        now = datetime.now(tz=UTC)
        if match is None:
            match = LeadIcpMatch(
                workspace_id=workspace_id,
                lead_id=lead.id,
                icp_profile_id=profile.id,
                fit_score=score,
                matched=matched,
                match_reasons_json=reasons,
                calculated_at=now,
            )
        else:
            match.fit_score = score
            match.matched = matched
            match.match_reasons_json = reasons
            match.calculated_at = now
        return self.repository.save_match(db, match)

    def calculate_fit(
        self,
        lead: Lead,
        profile: IcpProfile,
        *,
        signals: list[LeadSignal] | None = None,
    ) -> tuple[float, bool, dict[str, Any]]:
        signal_types = {signal.signal_type for signal in signals or []}
        reasons: dict[str, Any] = {"positive": [], "negative": [], "constraints": {}}
        components = [
            self._industry_score(lead, profile, reasons),
            self._city_score(lead, profile, reasons),
            self._rating_score(lead, profile, reasons),
            self._review_score(lead, profile, reasons),
            self._website_score(lead, profile, reasons),
            self._required_signal_score(profile, signal_types, reasons),
        ]
        score = round(sum(components) / len(components), 2)
        excluded = self._matches_excluded_keyword(lead, profile, reasons)
        if excluded:
            score = min(score, 20.0)
        return score, bool(score >= 60.0 and not excluded), reasons

    def _industry_score(self, lead: Lead, profile: IcpProfile, reasons: dict[str, Any]) -> float:
        targets = self._normalized_set(profile.target_industries)
        if not targets:
            return 80.0
        haystack = " ".join(part for part in (lead.category, lead.industry) if part).casefold()
        matched = any(target in haystack for target in targets)
        reasons["constraints"]["industry"] = matched
        (reasons["positive"] if matched else reasons["negative"]).append("industry_match")
        return 100.0 if matched else 25.0

    def _city_score(self, lead: Lead, profile: IcpProfile, reasons: dict[str, Any]) -> float:
        targets = self._normalized_set(profile.target_cities)
        if not targets:
            return 80.0
        city = (lead.city or "").casefold()
        matched = any(target in city for target in targets)
        reasons["constraints"]["city"] = matched
        (reasons["positive"] if matched else reasons["negative"]).append("city_match")
        return 100.0 if matched else 35.0

    def _rating_score(self, lead: Lead, profile: IcpProfile, reasons: dict[str, Any]) -> float:
        if profile.min_rating is None and profile.max_rating is None:
            return 75.0 if lead.rating is not None else 55.0
        rating = lead.rating
        matched = rating is not None
        if rating is not None and profile.min_rating is not None:
            matched = matched and rating >= profile.min_rating
        if rating is not None and profile.max_rating is not None:
            matched = matched and rating <= profile.max_rating
        reasons["constraints"]["rating"] = matched
        return 100.0 if matched else 30.0

    def _review_score(self, lead: Lead, profile: IcpProfile, reasons: dict[str, Any]) -> float:
        if profile.min_reviews is None and profile.max_reviews is None:
            return min(100.0, 50.0 + lead.review_count)
        matched = True
        if profile.min_reviews is not None:
            matched = matched and lead.review_count >= profile.min_reviews
        if profile.max_reviews is not None:
            matched = matched and lead.review_count <= profile.max_reviews
        reasons["constraints"]["reviews"] = matched
        return 100.0 if matched else 35.0

    def _website_score(self, lead: Lead, profile: IcpProfile, reasons: dict[str, Any]) -> float:
        preference = WebsitePreference(profile.website_preference)
        if preference == WebsitePreference.ANY:
            return 75.0
        has_website = bool(lead.has_website or lead.website_url or lead.website_domain)
        matched = (
            has_website
            if preference == WebsitePreference.MUST_HAVE
            else not has_website
        )
        reasons["constraints"]["website_preference"] = matched
        return 100.0 if matched else 25.0

    def _required_signal_score(
        self, profile: IcpProfile, signal_types: set[str], reasons: dict[str, Any]
    ) -> float:
        required = self._normalized_set(profile.required_signals)
        if not required:
            return 75.0
        missing = sorted(required - signal_types)
        reasons["constraints"]["required_signals"] = {"missing": missing}
        if not missing:
            reasons["positive"].append("required_signals_present")
            return 100.0
        reasons["negative"].append("required_signals_missing")
        return max(20.0, 100.0 - (len(missing) / len(required) * 80.0))

    def _matches_excluded_keyword(
        self, lead: Lead, profile: IcpProfile, reasons: dict[str, Any]
    ) -> bool:
        excluded = self._normalized_set(profile.excluded_keywords)
        if not excluded:
            return False
        haystack = " ".join(
            part
            for part in (
                lead.company_name,
                lead.category or "",
                lead.industry or "",
                lead.address or "",
                lead.website_domain or "",
            )
            if part
        ).casefold()
        matched = sorted(keyword for keyword in excluded if keyword in haystack)
        if matched:
            reasons["negative"].append("excluded_keyword")
            reasons["constraints"]["excluded_keywords"] = matched
        return bool(matched)

    def _normalized_set(self, values: list[str] | None) -> set[str]:
        return {value.strip().casefold() for value in values or [] if value.strip()}
