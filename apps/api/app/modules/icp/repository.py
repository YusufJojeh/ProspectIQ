from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.icp.models import IcpProfile, LeadIcpMatch


class IcpProfileRepository:
    def list_for_workspace(
        self, db: Session, *, workspace_id: int, active_only: bool = False
    ) -> list[IcpProfile]:
        statement = (
            select(IcpProfile)
            .where(IcpProfile.workspace_id == workspace_id)
            .order_by(IcpProfile.created_at.desc(), IcpProfile.id.desc())
        )
        if active_only:
            statement = statement.where(IcpProfile.is_active.is_(True))
        return list(db.scalars(statement))

    def get_by_public_id(
        self, db: Session, *, workspace_id: int, public_id: str
    ) -> IcpProfile | None:
        return db.scalar(
            select(IcpProfile).where(
                IcpProfile.workspace_id == workspace_id,
                IcpProfile.public_id == public_id,
            )
        )

    def save(self, db: Session, profile: IcpProfile) -> IcpProfile:
        db.add(profile)
        db.commit()
        db.refresh(profile)
        return profile

    def delete(self, db: Session, profile: IcpProfile) -> None:
        db.delete(profile)
        db.commit()

    def get_match(
        self,
        db: Session,
        *,
        workspace_id: int,
        lead_id: int,
        icp_profile_id: int,
    ) -> LeadIcpMatch | None:
        return db.scalar(
            select(LeadIcpMatch).where(
                LeadIcpMatch.workspace_id == workspace_id,
                LeadIcpMatch.lead_id == lead_id,
                LeadIcpMatch.icp_profile_id == icp_profile_id,
            )
        )

    def list_matches_for_lead(
        self, db: Session, *, workspace_id: int, lead_id: int
    ) -> list[LeadIcpMatch]:
        return list(
            db.scalars(
                select(LeadIcpMatch)
                .where(
                    LeadIcpMatch.workspace_id == workspace_id,
                    LeadIcpMatch.lead_id == lead_id,
                )
                .order_by(LeadIcpMatch.fit_score.desc(), LeadIcpMatch.id.desc())
            )
        )

    def save_match(self, db: Session, match: LeadIcpMatch) -> LeadIcpMatch:
        db.add(match)
        db.commit()
        db.refresh(match)
        return match
