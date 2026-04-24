from __future__ import annotations

# ruff: noqa: E402
import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import delete, select

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.modules.ai_analysis.models import AIAnalysisSnapshot, PromptTemplate, ServiceRecommendation
from app.modules.ai_analysis.schemas import LeadAnalysisResult
from app.modules.audit_logs.models import AuditLog
from app.modules.leads.models import Lead, LeadNote, LeadStatusHistory
from app.modules.outreach.models import OutreachMessage
from app.modules.provider_serpapi.models import (
    LeadIdentity,
    LeadSourceRecord,
    ProviderFetch,
    ProviderNormalizedFact,
    ProviderRawPayload,
    ProviderSettings,
)
from app.modules.scoring.models import (
    LeadScore,
    ScoreBreakdown,
    ScoringConfigVersion,
    WorkspaceScoringActive,
)
from app.modules.search_jobs.models import SearchJob, SearchRequest
from app.modules.users.models import User
from app.modules.users.service import seed_default_workspace_and_admin
from app.shared.enums.jobs import (
    LeadScoreBand,
    LeadStatus,
    OutreachTone,
    ProviderFetchStatus,
    SearchJobStatus,
    WebsitePreference,
)


@dataclass(frozen=True)
class DemoUserSpec:
    email: str
    full_name: str
    password: str
    role: str


@dataclass(frozen=True)
class DemoLeadSpec:
    company_name: str
    category: str
    address: str
    city: str
    phone: str
    website_url: str | None
    website_domain: str | None
    review_count: int
    rating: float | None
    lat: float
    lng: float
    data_completeness: float
    data_confidence: float
    has_website: bool
    status: str
    assigned_to_email: str | None
    score_total: float
    score_band: str
    score_qualified: bool
    score_breakdown: list[tuple[str, str, float, float, str]]
    analysis: LeadAnalysisResult | None
    recommendation_rationales: list[str]
    outreach_tone: str | None
    outreach_edit: tuple[str, str] | None
    note_entries: list[str]
    status_history: list[tuple[str | None, str]]


DEMO_USERS = [
    DemoUserSpec(
        email="manager@prospectiq.dev",
        full_name="Demo Operations Manager",
        password="ManagerPass123!",
        role="manager",
    ),
    DemoUserSpec(
        email="sales@prospectiq.dev",
        full_name="Demo Sales User",
        password="SalesPass123!",
        role="member",
    ),
]

DEMO_LEADS_BY_JOB: dict[str, list[DemoLeadSpec]] = {
    "job_demo_dental": [
        DemoLeadSpec(
            company_name="Marmara Smile Clinic",
            category="Dental Clinic",
            address="Bagdat Avenue 112, Kadikoy, Istanbul",
            city="Istanbul",
            phone="+90 216 555 0101",
            website_url="https://www.marmarasmile.example",
            website_domain="marmarasmile.example",
            review_count=146,
            rating=4.8,
            lat=40.9879,
            lng=29.0371,
            data_completeness=0.94,
            data_confidence=0.92,
            has_website=True,
            status=LeadStatus.QUALIFIED.value,
            assigned_to_email="manager@prospectiq.dev",
            score_total=88.0,
            score_band=LeadScoreBand.HIGH.value,
            score_qualified=True,
            score_breakdown=[
                (
                    "local_trust",
                    "Local trust",
                    0.25,
                    24.0,
                    "Strong rating and high review volume support high local trust.",
                ),
                (
                    "website_presence",
                    "Website presence",
                    0.25,
                    22.0,
                    "The clinic has a clear official site with consistent brand/domain signals.",
                ),
                (
                    "search_visibility",
                    "Search visibility",
                    0.20,
                    18.0,
                    "The business is easy to discover with official properties showing early in results.",
                ),
                (
                    "opportunity",
                    "Commercial opportunity",
                    0.20,
                    16.0,
                    "There is visible demand and room to improve conversion from branded discovery.",
                ),
                (
                    "data_confidence",
                    "Data confidence",
                    0.10,
                    8.0,
                    "Maps and website evidence are aligned and complete.",
                ),
            ],
            analysis=LeadAnalysisResult(
                summary=(
                    "Marmara Smile Clinic is a strong-fit lead with a healthy local profile, strong "
                    "review volume, and an official website that looks credible but still leaves room "
                    "for conversion and local SEO improvements."
                ),
                weaknesses=[
                    "The website explains treatments clearly but does not push consultation conversion strongly enough.",
                    "Review freshness is solid, but recent testimonials are not highlighted on the site.",
                ],
                opportunities=[
                    "Improve local landing pages around implant and smile-design intent.",
                    "Tighten Google Business Profile conversion cues and review merchandising.",
                ],
                recommended_services=[
                    "Local SEO Retainer",
                    "Conversion-Focused Website Refresh",
                    "Review Generation Workflow",
                ],
                outreach_subject="Marmara Smile Clinic: two evidence-backed growth opportunities",
                outreach_message=(
                    "Hi Marmara Smile Clinic team,\n\n"
                    "We reviewed your local presence and found a strong foundation: high review volume, "
                    "credible branding, and good discoverability. The clearest upside appears to be in "
                    "conversion-focused website improvements plus tighter local SEO around treatment-specific intent.\n\n"
                    "If useful, we can share a short walkthrough of the fastest wins."
                ),
                confidence=0.88,
            ),
            recommendation_rationales=[
                "Strong local authority means local SEO improvements should compound quickly.",
                "The website looks trustworthy but can do more to turn traffic into booked consultations.",
                "Review momentum exists, so a structured follow-up program can improve social proof efficiently.",
            ],
            outreach_tone=OutreachTone.CONSULTATIVE.value,
            outreach_edit=(
                "Priority growth ideas for Marmara Smile Clinic",
                "Hi Marmara Smile Clinic team,\n\nWe found two high-confidence growth opportunities: treatment-intent local SEO and a clearer consultation conversion path on the site.\n\nIf helpful, we can walk through the evidence in a short 10-minute review.",
            ),
            note_entries=[
                "Priority demo lead: strong balance of credibility, reviews, and website quality.",
                "Manager wants to use this lead when presenting score breakdown and outreach editing.",
            ],
            status_history=[
                (LeadStatus.NEW.value, LeadStatus.REVIEWED.value),
                (LeadStatus.REVIEWED.value, LeadStatus.QUALIFIED.value),
            ],
        ),
        DemoLeadSpec(
            company_name="Moda Implant Studio",
            category="Dental Clinic",
            address="Moda Caddesi 48, Kadikoy, Istanbul",
            city="Istanbul",
            phone="+90 216 555 0102",
            website_url="https://www.modaimplant.example",
            website_domain="modaimplant.example",
            review_count=79,
            rating=4.5,
            lat=40.9852,
            lng=29.0295,
            data_completeness=0.87,
            data_confidence=0.84,
            has_website=True,
            status=LeadStatus.REVIEWED.value,
            assigned_to_email="sales@prospectiq.dev",
            score_total=72.0,
            score_band=LeadScoreBand.MEDIUM.value,
            score_qualified=True,
            score_breakdown=[
                ("local_trust", "Local trust", 0.25, 19.0, "Solid reviews, though not top-tier volume."),
                ("website_presence", "Website presence", 0.25, 18.0, "Official site exists and matches the brand."),
                ("search_visibility", "Search visibility", 0.20, 14.0, "Some visibility signals are present but not dominant."),
                ("opportunity", "Commercial opportunity", 0.20, 14.0, "Room to grow around implant and cosmetic treatment positioning."),
                ("data_confidence", "Data confidence", 0.10, 7.0, "Evidence is good, but some fields are thinner than the top leads."),
            ],
            analysis=LeadAnalysisResult(
                summary=(
                    "Moda Implant Studio is a credible mid-funnel lead. The practice already has an "
                    "official site and decent review proof, but its positioning and conversion story "
                    "look less mature than the strongest clinics in the workspace."
                ),
                weaknesses=[
                    "Service positioning is generic and does not differentiate implant expertise clearly.",
                    "The site lacks stronger conversion cues on high-value service pages.",
                ],
                opportunities=[
                    "Sharpen implant-specific messaging and local landing pages.",
                    "Improve appointment CTAs and proof blocks for higher-intent visitors.",
                ],
                recommended_services=[
                    "Service Positioning Sprint",
                    "Landing Page Optimization",
                ],
                outreach_subject="A few focused visibility improvements for Moda Implant Studio",
                outreach_message=(
                    "Hi Moda Implant Studio team,\n\n"
                    "Your digital presence already has a credible foundation, especially around core business "
                    "information and reviews. The biggest upside appears to be clearer implant-specific positioning "
                    "plus stronger conversion paths on the site.\n\n"
                    "We can share a concise evidence-backed review if that would be helpful."
                ),
                confidence=0.79,
            ),
            recommendation_rationales=[
                "Positioning work would make the clinic's strongest services easier to understand quickly.",
                "Landing page improvements should help convert branded and local-intent visits more effectively.",
            ],
            outreach_tone=OutreachTone.FRIENDLY.value,
            outreach_edit=None,
            note_entries=[
                "Good supporting example for a medium-band lead with clear upside.",
            ],
            status_history=[(LeadStatus.NEW.value, LeadStatus.REVIEWED.value)],
        ),
        DemoLeadSpec(
            company_name="Acibadem Oral Care",
            category="Dental Clinic",
            address="Acibadem Mahallesi 23, Uskudar, Istanbul",
            city="Istanbul",
            phone="+90 216 555 0103",
            website_url=None,
            website_domain=None,
            review_count=41,
            rating=4.3,
            lat=41.0028,
            lng=29.0419,
            data_completeness=0.71,
            data_confidence=0.74,
            has_website=False,
            status=LeadStatus.CONTACTED.value,
            assigned_to_email="sales@prospectiq.dev",
            score_total=61.0,
            score_band=LeadScoreBand.MEDIUM.value,
            score_qualified=True,
            score_breakdown=[
                ("local_trust", "Local trust", 0.25, 16.0, "Reasonable rating and review count for a local clinic."),
                ("website_presence", "Website presence", 0.25, 7.0, "No clear official website is visible."),
                ("search_visibility", "Search visibility", 0.20, 13.0, "The business is visible in maps but weak on web presence."),
                ("opportunity", "Commercial opportunity", 0.20, 17.0, "Missing owned digital assets creates a strong improvement angle."),
                ("data_confidence", "Data confidence", 0.10, 8.0, "Enough evidence exists to support outreach with confidence."),
            ],
            analysis=None,
            recommendation_rationales=[],
            outreach_tone=None,
            outreach_edit=None,
            note_entries=[
                "Useful example of a clinic with strong local presence but weak owned digital presence.",
            ],
            status_history=[
                (LeadStatus.NEW.value, LeadStatus.REVIEWED.value),
                (LeadStatus.REVIEWED.value, LeadStatus.CONTACTED.value),
            ],
        ),
    ],
    "job_demo_physio": [
        DemoLeadSpec(
            company_name="Ankara Motion Physio",
            category="Physiotherapy Center",
            address="Ataturk Bulvari 301, Cankaya, Ankara",
            city="Ankara",
            phone="+90 312 555 0201",
            website_url="https://www.ankaramotion.example",
            website_domain="ankaramotion.example",
            review_count=93,
            rating=4.7,
            lat=39.9205,
            lng=32.8541,
            data_completeness=0.91,
            data_confidence=0.89,
            has_website=True,
            status=LeadStatus.INTERESTED.value,
            assigned_to_email="manager@prospectiq.dev",
            score_total=83.0,
            score_band=LeadScoreBand.HIGH.value,
            score_qualified=True,
            score_breakdown=[
                ("local_trust", "Local trust", 0.25, 22.0, "Review profile is both strong and recent."),
                ("website_presence", "Website presence", 0.25, 20.0, "Official site is present and looks trustworthy."),
                ("search_visibility", "Search visibility", 0.20, 16.0, "The brand is discoverable across local and web surfaces."),
                ("opportunity", "Commercial opportunity", 0.20, 17.0, "There is room to sharpen service-line demand capture."),
                ("data_confidence", "Data confidence", 0.10, 8.0, "Evidence consistency is high."),
            ],
            analysis=LeadAnalysisResult(
                summary=(
                    "Ankara Motion Physio is presentation-ready as an 'interested' lead: strong review proof, "
                    "good discoverability, and a credible website suggest both maturity and a practical upsell path."
                ),
                weaknesses=[
                    "Service-line pages do not clearly differentiate sports recovery vs. general physiotherapy intent.",
                ],
                opportunities=[
                    "Create clearer service clusters and stronger lead-capture offers for high-intent visitors.",
                ],
                recommended_services=[
                    "Local SEO Retainer",
                    "Conversion Audit",
                ],
                outreach_subject="Evidence-backed growth ideas for Ankara Motion Physio",
                outreach_message=(
                    "Hi Ankara Motion Physio team,\n\n"
                    "Your practice already shows strong credibility signals, especially around reviews and discoverability. "
                    "The clearest next step appears to be tightening service-line messaging so high-intent visitors convert faster.\n\n"
                    "We can share a short audit if useful."
                ),
                confidence=0.84,
            ),
            recommendation_rationales=[
                "Existing authority means SEO improvements have a strong base to build on.",
                "Conversion work can help turn already-strong visibility into more consultations.",
            ],
            outreach_tone=OutreachTone.SHORT_PITCH.value,
            outreach_edit=None,
            note_entries=[
                "Good example for showing an already-engaged lead in the pipeline.",
            ],
            status_history=[
                (LeadStatus.NEW.value, LeadStatus.REVIEWED.value),
                (LeadStatus.REVIEWED.value, LeadStatus.QUALIFIED.value),
                (LeadStatus.QUALIFIED.value, LeadStatus.INTERESTED.value),
            ],
        ),
        DemoLeadSpec(
            company_name="Cankaya Recovery Lab",
            category="Physiotherapy Center",
            address="Bestekar Sokak 14, Cankaya, Ankara",
            city="Ankara",
            phone="+90 312 555 0202",
            website_url="https://www.cankayarecovery.example",
            website_domain="cankayarecovery.example",
            review_count=28,
            rating=4.1,
            lat=39.9124,
            lng=32.8609,
            data_completeness=0.76,
            data_confidence=0.69,
            has_website=True,
            status=LeadStatus.NEW.value,
            assigned_to_email=None,
            score_total=54.0,
            score_band=LeadScoreBand.LOW.value,
            score_qualified=False,
            score_breakdown=[
                ("local_trust", "Local trust", 0.25, 13.0, "Review volume is still developing."),
                ("website_presence", "Website presence", 0.25, 15.0, "Official site exists but is lightweight."),
                ("search_visibility", "Search visibility", 0.20, 9.0, "Search visibility is inconsistent."),
                ("opportunity", "Commercial opportunity", 0.20, 11.0, "There is upside, but not as immediate as the stronger leads."),
                ("data_confidence", "Data confidence", 0.10, 6.0, "Evidence is usable but not especially rich."),
            ],
            analysis=None,
            recommendation_rationales=[],
            outreach_tone=None,
            outreach_edit=None,
            note_entries=[],
            status_history=[],
        ),
    ],
}


def _sha(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _slugify(value: str) -> str:
    normalized = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    return "-".join(part for part in normalized.split("-") if part)


def run_migrations() -> None:
    config = Config("alembic.ini")
    command.upgrade(config, "head")


def ensure_base_workspace_configuration(db, *, workspace_id: int, admin_id: int) -> None:
    existing_provider_settings = db.scalar(
        select(ProviderSettings).where(ProviderSettings.workspace_id == workspace_id)
    )
    if existing_provider_settings is None:
        db.add(
            ProviderSettings(
                workspace_id=workspace_id,
                hl="en",
                gl="tr",
                google_domain="google.com",
                enrich_top_n=20,
            )
        )
        db.commit()

    active = db.scalar(
        select(WorkspaceScoringActive).where(WorkspaceScoringActive.workspace_id == workspace_id)
    )
    if active is None:
        version = ScoringConfigVersion(
            workspace_id=workspace_id,
            created_by_user_id=admin_id,
            weights_json={
                "local_trust": 0.25,
                "website_presence": 0.25,
                "search_visibility": 0.2,
                "opportunity": 0.2,
                "data_confidence": 0.1,
            },
            thresholds_json={
                "high_min": 75,
                "medium_min": 55,
                "low_min": 35,
                "confidence_min": 0.45,
            },
            note="Seed default scoring config",
        )
        db.add(version)
        db.commit()
        db.refresh(version)
        db.add(
            WorkspaceScoringActive(
                workspace_id=workspace_id,
                active_scoring_config_version_id=version.id,
                updated_at=datetime.now(tz=UTC),
            )
        )
        db.commit()

    prompt = db.scalar(
        select(PromptTemplate).where(
            PromptTemplate.workspace_id == workspace_id,
            PromptTemplate.is_active.is_(True),
        )
    )
    if prompt is None:
        db.add(
            PromptTemplate(
                workspace_id=workspace_id,
                name="Default lead analysis",
                template_text=(
                    "Analyze the lead using only normalized facts and deterministic "
                    "score context."
                ),
                is_active=True,
                created_by_user_id=admin_id,
            )
        )
        db.commit()


def _ensure_user(
    db,
    *,
    workspace_id: int,
    email: str,
    full_name: str,
    password: str,
    role: str,
) -> User:
    existing = db.scalar(
        select(User).where(
            User.workspace_id == workspace_id,
            User.email == email.lower(),
        )
    )
    if existing is None:
        existing = User(
            workspace_id=workspace_id,
            email=email.lower(),
            full_name=full_name,
            hashed_password=hash_password(password),
            role=role,
        )
    else:
        existing.full_name = full_name
        existing.hashed_password = hash_password(password)
        existing.role = role
    db.add(existing)
    db.commit()
    db.refresh(existing)
    return existing


def _reset_workspace_demo_data(db, *, workspace_id: int) -> None:
    lead_ids = list(db.scalars(select(Lead.id).where(Lead.workspace_id == workspace_id)))
    fetch_ids = list(
        db.scalars(select(ProviderFetch.id).where(ProviderFetch.workspace_id == workspace_id))
    )
    score_ids = []
    snapshot_ids = []
    if lead_ids:
        score_ids = list(
            db.scalars(select(LeadScore.id).where(LeadScore.lead_id.in_(lead_ids)))
        )
        snapshot_ids = list(
            db.scalars(select(AIAnalysisSnapshot.id).where(AIAnalysisSnapshot.lead_id.in_(lead_ids)))
        )
        if score_ids:
            db.execute(delete(ScoreBreakdown).where(ScoreBreakdown.lead_score_id.in_(score_ids)))
        if snapshot_ids:
            db.execute(
                delete(ServiceRecommendation).where(
                    ServiceRecommendation.ai_analysis_snapshot_id.in_(snapshot_ids)
                )
            )
        db.execute(delete(OutreachMessage).where(OutreachMessage.lead_id.in_(lead_ids)))
        db.execute(delete(AIAnalysisSnapshot).where(AIAnalysisSnapshot.lead_id.in_(lead_ids)))
        db.execute(delete(LeadStatusHistory).where(LeadStatusHistory.lead_id.in_(lead_ids)))
        db.execute(delete(LeadNote).where(LeadNote.lead_id.in_(lead_ids)))
        db.execute(delete(LeadSourceRecord).where(LeadSourceRecord.lead_id.in_(lead_ids)))
        db.execute(delete(LeadIdentity).where(LeadIdentity.lead_id.in_(lead_ids)))
        db.execute(delete(LeadScore).where(LeadScore.lead_id.in_(lead_ids)))
        db.execute(delete(ProviderNormalizedFact).where(ProviderNormalizedFact.lead_id.in_(lead_ids)))
        db.execute(delete(Lead).where(Lead.id.in_(lead_ids)))

    if fetch_ids:
        db.execute(delete(ProviderRawPayload).where(ProviderRawPayload.provider_fetch_id.in_(fetch_ids)))
    db.execute(delete(ProviderFetch).where(ProviderFetch.workspace_id == workspace_id))
    db.execute(delete(SearchJob).where(SearchJob.workspace_id == workspace_id))
    db.execute(delete(SearchRequest).where(SearchRequest.workspace_id == workspace_id))
    db.execute(delete(AuditLog).where(AuditLog.workspace_id == workspace_id))
    db.execute(delete(WorkspaceScoringActive).where(WorkspaceScoringActive.workspace_id == workspace_id))
    db.execute(delete(ScoringConfigVersion).where(ScoringConfigVersion.workspace_id == workspace_id))
    db.execute(delete(PromptTemplate).where(PromptTemplate.workspace_id == workspace_id))
    db.execute(delete(ProviderSettings).where(ProviderSettings.workspace_id == workspace_id))
    db.commit()


def _seed_secondary_admin_records(db, *, workspace_id: int, admin_id: int) -> None:
    if db.scalar(
        select(ScoringConfigVersion).where(
            ScoringConfigVersion.workspace_id == workspace_id,
            ScoringConfigVersion.note == "Demo aggressive scoring config",
        )
    ) is None:
        db.add(
            ScoringConfigVersion(
                workspace_id=workspace_id,
                created_by_user_id=admin_id,
                weights_json={
                    "local_trust": 0.2,
                    "website_presence": 0.3,
                    "search_visibility": 0.15,
                    "opportunity": 0.25,
                    "data_confidence": 0.1,
                },
                thresholds_json={
                    "high_min": 78,
                    "medium_min": 58,
                    "low_min": 40,
                    "confidence_min": 0.5,
                },
                note="Demo aggressive scoring config",
            )
        )
    if db.scalar(
        select(PromptTemplate).where(
            PromptTemplate.workspace_id == workspace_id,
            PromptTemplate.name == "Demo concise outreach prompt",
        )
    ) is None:
        db.add(
            PromptTemplate(
                workspace_id=workspace_id,
                name="Demo concise outreach prompt",
                template_text=(
                    "Summarize the lead in practical sales language. Keep claims tied to stored "
                    "evidence, and make the outreach draft concise enough for a presentation demo."
                ),
                is_active=False,
                created_by_user_id=admin_id,
            )
        )
    db.commit()


def _create_search_request_and_job(
    db,
    *,
    workspace_id: int,
    requested_by_user_id: int,
    business_type: str,
    city: str,
    region: str | None,
    radius_km: int,
    max_results: int,
    website_preference: str,
    keyword_filter: str,
    status: str,
    candidates_found: int,
    leads_upserted: int,
    enriched_count: int,
    provider_error_count: int,
    queued_at: datetime,
    started_at: datetime | None,
    finished_at: datetime | None,
) -> SearchJob:
    request = SearchRequest(
        workspace_id=workspace_id,
        requested_by_user_id=requested_by_user_id,
        business_type=business_type,
        city=city,
        region=region,
        radius_km=radius_km,
        max_results=max_results,
        min_rating=4.0,
        max_rating=5.0,
        min_reviews=10,
        max_reviews=250,
        website_preference=website_preference,
        keyword_filter=keyword_filter,
        created_at=queued_at,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    job = SearchJob(
        workspace_id=workspace_id,
        search_request_id=request.id,
        requested_by_user_id=requested_by_user_id,
        business_type=business_type,
        city=city,
        region=region,
        radius_km=radius_km,
        max_results=max_results,
        min_rating=4.0,
        max_rating=5.0,
        min_reviews=10,
        max_reviews=250,
        website_preference=website_preference,
        keyword_filter=keyword_filter,
        status=status,
        queued_at=queued_at,
        started_at=started_at,
        finished_at=finished_at,
        candidates_found=candidates_found,
        leads_upserted=leads_upserted,
        enriched_count=enriched_count,
        provider_error_count=provider_error_count,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _create_provider_fact(
    db,
    *,
    workspace_id: int,
    search_job_id: int,
    lead_id: int,
    company_name: str,
    category: str,
    address: str,
    city: str,
    phone: str,
    website_url: str | None,
    website_domain: str | None,
    rating: float | None,
    review_count: int,
    lat: float,
    lng: float,
    source_type: str,
    mode: str,
    facts_json: dict[str, object],
) -> ProviderNormalizedFact:
    payload = {
        "search_metadata": {"id": f"demo-{source_type}-{_slugify(company_name)}"},
        "company_name": company_name,
        "address": address,
        "website": website_url,
    }
    fetch = ProviderFetch(
        workspace_id=workspace_id,
        provider="demo",
        engine="google_maps" if source_type != "web_search" else "google",
        mode=mode,
        search_job_id=search_job_id,
        request_fingerprint=_sha({"lead_id": lead_id, "source_type": source_type, "mode": mode}),
        request_params_json={"company_name": company_name, "source_type": source_type},
        serpapi_search_id=payload["search_metadata"]["id"],
        status=ProviderFetchStatus.OK.value,
        http_status=200,
        started_at=datetime.now(tz=UTC),
        finished_at=datetime.now(tz=UTC),
        attempt=1,
    )
    db.add(fetch)
    db.commit()
    db.refresh(fetch)
    db.add(
        ProviderRawPayload(
            provider_fetch_id=fetch.id,
            payload_json=payload,
            payload_sha256=_sha(payload),
        )
    )
    db.commit()
    fact = ProviderNormalizedFact(
        workspace_id=workspace_id,
        lead_id=lead_id,
        provider_fetch_id=fetch.id,
        source_type=source_type,
        data_cid=f"demo-cid-{_slugify(company_name)}",
        data_id=f"demo-data-{_slugify(company_name)}-{source_type}",
        place_id=f"demo-place-{_slugify(company_name)}",
        company_name=company_name,
        category=category,
        address=address,
        city=city,
        phone=phone,
        website_url=website_url,
        website_domain=website_domain,
        rating=rating,
        review_count=review_count,
        lat=lat,
        lng=lng,
        confidence=0.88 if website_url else 0.76,
        completeness=0.91 if website_url else 0.73,
        facts_json=facts_json,
    )
    db.add(fact)
    db.commit()
    db.refresh(fact)
    db.add(
        LeadSourceRecord(
            lead_id=lead_id,
            provider_normalized_fact_id=fact.id,
            priority=10 if source_type == "maps_place" else 20,
            is_current=source_type == "maps_place",
        )
    )
    if website_domain:
        existing_identity = db.scalar(
            select(LeadIdentity).where(
                LeadIdentity.workspace_id == workspace_id,
                LeadIdentity.identity_type == "website_domain",
                LeadIdentity.identity_value == website_domain,
            )
        )
        if existing_identity is None:
            db.add(
                LeadIdentity(
                    workspace_id=workspace_id,
                    lead_id=lead_id,
                    identity_type="website_domain",
                    identity_value=website_domain,
                )
            )
    db.commit()
    return fact


def _seed_analysis_and_outreach(
    db,
    *,
    lead: Lead,
    admin_id: int,
    analysis: LeadAnalysisResult,
    rationales: list[str],
    outreach_tone: str,
    outreach_edit: tuple[str, str] | None,
    created_at: datetime,
) -> None:
    snapshot = AIAnalysisSnapshot(
        lead_id=lead.id,
        prompt_template_id=db.scalar(
            select(PromptTemplate.id).where(
                PromptTemplate.workspace_id == lead.workspace_id,
                PromptTemplate.is_active.is_(True),
            )
        ),
        ai_provider="demo",
        model_name="seeded-demo-analysis-v1",
        input_hash=_sha({"lead_id": lead.id, "summary": analysis.summary}),
        output_json=analysis.model_dump(mode="json"),
        created_by_user_id=admin_id,
        created_at=created_at,
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    db.add_all(
        [
            ServiceRecommendation(
                lead_id=lead.id,
                ai_analysis_snapshot_id=snapshot.id,
                service_name=service_name,
                rationale=rationales[index - 1] if index - 1 < len(rationales) else None,
                confidence=analysis.confidence,
                rank_order=index,
                created_by_user_id=admin_id,
                created_at=created_at + timedelta(minutes=index),
            )
            for index, service_name in enumerate(analysis.recommended_services, start=1)
        ]
    )
    db.commit()
    message = OutreachMessage(
        lead_id=lead.id,
        ai_analysis_snapshot_id=snapshot.id,
        subject=analysis.outreach_subject,
        message=analysis.outreach_message,
        tone=outreach_tone,
        version_number=1,
        edited_subject=outreach_edit[0] if outreach_edit else None,
        edited_message=outreach_edit[1] if outreach_edit else None,
        created_by_user_id=admin_id,
        created_at=created_at + timedelta(minutes=5),
        updated_at=created_at + timedelta(minutes=7),
    )
    db.add(message)
    db.commit()


def _seed_demo_workspace(db) -> None:
    workspace, admin = seed_default_workspace_and_admin(db)
    admin.full_name = "LeadScope Demo Admin"
    admin.hashed_password = hash_password("ChangeMe123!")
    admin.role = "account_owner"
    db.add(admin)
    db.commit()
    db.refresh(admin)

    ensure_base_workspace_configuration(db, workspace_id=workspace.id, admin_id=admin.id)
    _seed_secondary_admin_records(db, workspace_id=workspace.id, admin_id=admin.id)

    demo_users = {
        spec.email: _ensure_user(
            db,
            workspace_id=workspace.id,
            email=spec.email,
            full_name=spec.full_name,
            password=spec.password,
            role=spec.role,
        )
        for spec in DEMO_USERS
    }

    base_time = datetime(2026, 4, 3, 10, 0, tzinfo=UTC)
    dental_job = _create_search_request_and_job(
        db,
        workspace_id=workspace.id,
        requested_by_user_id=admin.id,
        business_type="Dental Clinic",
        city="Istanbul",
        region="Kadikoy",
        radius_km=10,
        max_results=25,
        website_preference=WebsitePreference.ANY.value,
        keyword_filter="implant",
        status=SearchJobStatus.COMPLETED.value,
        candidates_found=14,
        leads_upserted=3,
        enriched_count=3,
        provider_error_count=0,
        queued_at=base_time,
        started_at=base_time + timedelta(minutes=1),
        finished_at=base_time + timedelta(minutes=8),
    )
    physio_job = _create_search_request_and_job(
        db,
        workspace_id=workspace.id,
        requested_by_user_id=admin.id,
        business_type="Physiotherapy Center",
        city="Ankara",
        region="Cankaya",
        radius_km=12,
        max_results=20,
        website_preference=WebsitePreference.MUST_HAVE.value,
        keyword_filter="sports rehab",
        status=SearchJobStatus.PARTIALLY_COMPLETED.value,
        candidates_found=9,
        leads_upserted=2,
        enriched_count=2,
        provider_error_count=1,
        queued_at=base_time + timedelta(hours=3),
        started_at=base_time + timedelta(hours=3, minutes=2),
        finished_at=base_time + timedelta(hours=3, minutes=10),
    )

    jobs_by_key = {
        "job_demo_dental": dental_job,
        "job_demo_physio": physio_job,
    }
    analysis_counter = 0
    for job_key, lead_specs in DEMO_LEADS_BY_JOB.items():
        job = jobs_by_key[job_key]
        for lead_index, spec in enumerate(lead_specs, start=1):
            lead_created_at = job.started_at or job.queued_at
            lead = Lead(
                workspace_id=workspace.id,
                search_job_id=job.id,
                assigned_to_user_id=(
                    demo_users[spec.assigned_to_email].id if spec.assigned_to_email else None
                ),
                company_name=spec.company_name,
                category=spec.category,
                address=spec.address,
                city=spec.city,
                phone=spec.phone,
                website_url=spec.website_url,
                website_domain=spec.website_domain,
                review_count=spec.review_count,
                rating=spec.rating,
                lat=spec.lat,
                lng=spec.lng,
                data_completeness=spec.data_completeness,
                data_confidence=spec.data_confidence,
                has_website=spec.has_website,
                status=spec.status,
                created_at=lead_created_at + timedelta(minutes=lead_index * 3),
                updated_at=lead_created_at + timedelta(minutes=lead_index * 5),
            )
            db.add(lead)
            db.commit()
            db.refresh(lead)

            _create_provider_fact(
                db,
                workspace_id=workspace.id,
                search_job_id=job.id,
                lead_id=lead.id,
                company_name=lead.company_name,
                category=spec.category,
                address=spec.address,
                city=spec.city,
                phone=spec.phone,
                website_url=spec.website_url,
                website_domain=spec.website_domain,
                rating=spec.rating,
                review_count=spec.review_count,
                lat=spec.lat,
                lng=spec.lng,
                source_type="maps_place",
                mode="maps_place",
                facts_json={
                    "company_name": lead.company_name,
                    "address": spec.address,
                    "website": spec.website_url,
                    "rating": spec.rating,
                    "reviews": spec.review_count,
                    "coordinates": {"lat": spec.lat, "lng": spec.lng},
                },
            )
            _create_provider_fact(
                db,
                workspace_id=workspace.id,
                search_job_id=job.id,
                lead_id=lead.id,
                company_name=lead.company_name,
                category=spec.category,
                address=spec.address,
                city=spec.city,
                phone=spec.phone,
                website_url=spec.website_url,
                website_domain=spec.website_domain,
                rating=spec.rating,
                review_count=spec.review_count,
                lat=spec.lat,
                lng=spec.lng,
                source_type="web_search",
                mode="web_search",
                facts_json={
                    "official_website_found": bool(spec.website_url),
                    "official_website_source": "web_search" if spec.website_url else None,
                    "visibility_signal": "strong" if spec.review_count >= 80 else "developing",
                },
            )

            lead_score = LeadScore(
                lead_id=lead.id,
                scoring_config_version_id=db.scalar(
                    select(WorkspaceScoringActive.active_scoring_config_version_id).where(
                        WorkspaceScoringActive.workspace_id == workspace.id
                    )
                ),
                total_score=spec.score_total,
                band=spec.score_band,
                qualified=spec.score_qualified,
                scored_at=lead.created_at + timedelta(minutes=10),
            )
            db.add(lead_score)
            db.commit()
            db.refresh(lead_score)
            db.add_all(
                [
                    ScoreBreakdown(
                        lead_score_id=lead_score.id,
                        key=key,
                        label=label,
                        weight=weight,
                        contribution=contribution,
                        reason=reason,
                    )
                    for key, label, weight, contribution, reason in spec.score_breakdown
                ]
            )
            db.commit()

            for note_index, note in enumerate(spec.note_entries, start=1):
                db.add(
                    LeadNote(
                        lead_id=lead.id,
                        note=note,
                        created_by_user_id=admin.id,
                        created_at=lead.updated_at + timedelta(minutes=note_index),
                    )
                )
            for status_index, (from_status, to_status) in enumerate(spec.status_history, start=1):
                db.add(
                    LeadStatusHistory(
                        lead_id=lead.id,
                        from_status=from_status,
                        to_status=to_status,
                        changed_by_user_id=admin.id,
                        changed_at=lead.created_at + timedelta(minutes=status_index),
                    )
                )
            db.commit()

            if spec.analysis and spec.outreach_tone:
                analysis_counter += 1
                _seed_analysis_and_outreach(
                    db,
                    lead=lead,
                    admin_id=admin.id,
                    analysis=spec.analysis,
                    rationales=spec.recommendation_rationales,
                    outreach_tone=spec.outreach_tone,
                    outreach_edit=spec.outreach_edit,
                    created_at=lead.updated_at + timedelta(minutes=12 + analysis_counter),
                )

    failed_fetch = ProviderFetch(
        workspace_id=workspace.id,
        provider="demo",
        engine="google_maps",
        mode="maps_place",
        search_job_id=physio_job.id,
        request_fingerprint=_sha({"job": physio_job.public_id, "failure": "rate-limit"}),
        request_params_json={"job_public_id": physio_job.public_id, "mode": "maps_place"},
        serpapi_search_id="demo-failed-fetch",
        status=ProviderFetchStatus.RATE_LIMITED.value,
        http_status=429,
        started_at=physio_job.started_at or physio_job.queued_at,
        finished_at=physio_job.finished_at,
        error_message="Demo rate-limit example for admin health visibility.",
        attempt=1,
    )
    db.add(failed_fetch)
    db.commit()

    db.add_all(
        [
            AuditLog(
                workspace_id=workspace.id,
                actor_user_id=admin.id,
                event_name="provider_settings.updated",
                details="Prepared the workspace for the graduation demo using presentation-safe defaults.",
            ),
            AuditLog(
                workspace_id=workspace.id,
                actor_user_id=admin.id,
                event_name="prompt_template.created",
                details="Added a demo-only prompt variation for presentation walkthroughs.",
            ),
            AuditLog(
                workspace_id=workspace.id,
                actor_user_id=admin.id,
                event_name="leads.exported_csv",
                details="Exported the seeded lead list as CSV during demo preparation.",
            ),
        ]
    )
    db.commit()


def seed(*, demo_data: bool = False, reset_demo_data: bool = False) -> None:
    with SessionLocal() as db:
        workspace, admin = seed_default_workspace_and_admin(db)
        if reset_demo_data:
            _reset_workspace_demo_data(db, workspace_id=workspace.id)
            workspace, admin = seed_default_workspace_and_admin(db)
        ensure_base_workspace_configuration(db, workspace_id=workspace.id, admin_id=admin.id)
        if demo_data:
            _seed_demo_workspace(db)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the LeadScope AI database.")
    parser.add_argument(
        "--migrate",
        action="store_true",
        help="Run alembic migrations before seeding.",
    )
    parser.add_argument(
        "--demo-data",
        action="store_true",
        help="Seed presentation-ready demo users, jobs, leads, scores, recommendations, and outreach.",
    )
    parser.add_argument(
        "--reset-demo-data",
        action="store_true",
        help="Clear workspace operational data before reseeding. Intended for reproducible demos.",
    )
    args = parser.parse_args()

    if args.migrate:
        run_migrations()
    seed(demo_data=args.demo_data, reset_demo_data=args.reset_demo_data)
    print("Seed completed.")


if __name__ == "__main__":
    main()
