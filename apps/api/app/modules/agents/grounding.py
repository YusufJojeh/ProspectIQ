from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.agents.models import AgentToolCall

# --- Evidence-reference grounding -----------------------------------------
#
# A final answer may cite lead evidence only by the refs the backend itself
# put into tool results during THIS run. The observed set is rebuilt from
# persisted AgentToolCall.result_json -- never from Python memory -- so it
# is identical before a pause and after a same-run resume. Every surviving
# ref is then re-checked against the database for workspace + lead
# ownership, so a ref can never be laundered in from another tenant.

#: Result keys whose string values are citable evidence ids, by prefix.
_REF_KEYS: dict[str, str] = {
    "evidence_ref": "ev_",
    "change_id": "rce_",
    "run_id": "rrun_",
}
_MAX_WALK_DEPTH = 12


def _walk(value: Any, depth: int, found: set[str]) -> None:
    if depth > _MAX_WALK_DEPTH:
        return
    if isinstance(value, dict):
        for key, item in value.items():
            prefix = _REF_KEYS.get(key)
            if prefix and isinstance(item, str) and item.startswith(prefix):
                found.add(item)
            else:
                _walk(item, depth + 1, found)
    elif isinstance(value, list):
        for item in value:
            _walk(item, depth + 1, found)


def observed_evidence_refs(db: Session, agent_run_id: int) -> set[str]:
    """Evidence refs present in successful tool results of this run."""
    found: set[str] = set()
    rows = db.scalars(
        select(AgentToolCall.result_json).where(
            AgentToolCall.agent_run_id == agent_run_id, AgentToolCall.status == "ok"
        )
    ).all()
    for result in rows:
        _walk(result, 0, found)
    return found


def owned_evidence_refs(
    db: Session, *, workspace_id: int, lead_id: int | None, refs: Iterable[str]
) -> set[str]:
    """The subset of `refs` that resolve to records of this workspace AND lead."""
    from app.modules.provider_serpapi.models import ProviderNormalizedFact
    from app.modules.research.models import ResearchChangeEvent, ResearchRun

    if lead_id is None:
        return set()
    refs = set(refs)
    fact_ids = {int(ref[3:]) for ref in refs if ref.startswith("ev_") and ref[3:].isdigit()}
    change_ids = {ref for ref in refs if ref.startswith("rce_")}
    run_ids = {ref for ref in refs if ref.startswith("rrun_")}
    owned: set[str] = set()
    if fact_ids:
        owned.update(
            f"ev_{fact_id}"
            for fact_id in db.scalars(
                select(ProviderNormalizedFact.id).where(
                    ProviderNormalizedFact.id.in_(fact_ids),
                    ProviderNormalizedFact.workspace_id == workspace_id,
                    ProviderNormalizedFact.lead_id == lead_id,
                )
            )
        )
    if change_ids:
        owned.update(
            db.scalars(
                select(ResearchChangeEvent.public_id).where(
                    ResearchChangeEvent.public_id.in_(change_ids),
                    ResearchChangeEvent.workspace_id == workspace_id,
                    ResearchChangeEvent.lead_id == lead_id,
                )
            )
        )
    if run_ids:
        owned.update(
            db.scalars(
                select(ResearchRun.public_id).where(
                    ResearchRun.public_id.in_(run_ids),
                    ResearchRun.workspace_id == workspace_id,
                    ResearchRun.lead_id == lead_id,
                )
            )
        )
    return owned


def ground_evidence_refs(
    db: Session,
    *,
    agent_run_id: int,
    workspace_id: int,
    lead_id: int | None,
    requested: list[str],
) -> tuple[list[str], list[str]]:
    """Returns (kept, dropped): requested ∩ observed ∩ owned, order preserved."""
    observed = observed_evidence_refs(db, agent_run_id)
    candidates = [ref for ref in dict.fromkeys(requested) if ref in observed]
    owned = owned_evidence_refs(db, workspace_id=workspace_id, lead_id=lead_id, refs=candidates)
    kept = [ref for ref in candidates if ref in owned]
    dropped = [ref for ref in dict.fromkeys(requested) if ref not in owned]
    return kept, dropped
