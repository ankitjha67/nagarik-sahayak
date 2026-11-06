"""Reviewer queue for benefit applications flagged by the fraud screen.

The screen deliberately never refuses an application on suspicion alone — it
routes it to a person. That promise is empty unless someone can actually see and
work the resulting pile, which is what this module provides.

Two properties this queue is built around:

* **A pending case must not stall the citizen.** The form is already issued; the
  review governs whether the *benefit* is released. An unreviewed case is a
  backlog for the department, not a silent rejection of the applicant.
* **Decisions are attributable and reversible.** Every outcome records who
  decided, when, and why, because a citizen refused on suspicion is entitled to
  know a human looked and on what basis.

The prioritisation and state-transition logic is kept as pure functions so it
can be tested without a database; only the thin persistence wrappers touch
Prisma.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


class CaseStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"   # reviewer is satisfied; benefit may be released
    REJECTED = "rejected"   # reviewer found the concern substantiated


# A reviewer may only act on a case nobody has decided yet. Re-deciding a closed
# case would overwrite the audit trail, so reopening is a separate, explicit act.
VALID_TRANSITIONS = {
    CaseStatus.PENDING: {CaseStatus.APPROVED, CaseStatus.REJECTED},
    CaseStatus.APPROVED: set(),
    CaseStatus.REJECTED: set(),
}


@dataclass
class TransitionError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


def validate_transition(current: str, target: str) -> None:
    """Raise TransitionError if this status change is not permitted."""
    try:
        cur = CaseStatus(current)
        tgt = CaseStatus(target)
    except ValueError:
        raise TransitionError(f"Unknown status: {current!r} -> {target!r}")

    if tgt not in VALID_TRANSITIONS[cur]:
        if cur != CaseStatus.PENDING:
            raise TransitionError(
                f"This case was already {cur.value}. Reopen it before deciding again."
            )
        raise TransitionError(f"Cannot move a case from {cur.value} to {tgt.value}.")


def priority_of(case: dict) -> tuple:
    """Sort key placing the cases most worth a reviewer's time first.

    Highest risk first, then oldest first — so a high-risk case cannot be
    starved by newer arrivals, and an old low-risk case still eventually
    surfaces rather than sitting forever behind fresh traffic.
    """
    created = case.get("createdAt") or ""
    return (-int(case.get("riskScore") or 0), str(created))


def prioritise(cases: list[dict]) -> list[dict]:
    return sorted(cases, key=priority_of)


def summarise(cases: list[dict]) -> dict:
    """Queue-level counts, for an at-a-glance view of the backlog."""
    pending = [c for c in cases if c.get("status") == CaseStatus.PENDING.value]
    by_signal: dict[str, int] = {}
    for c in pending:
        for s in c.get("signals", []) or []:
            code = s.get("code") if isinstance(s, dict) else str(s)
            if code:
                by_signal[code] = by_signal.get(code, 0) + 1

    return {
        "pending": len(pending),
        "approved": sum(1 for c in cases if c.get("status") == CaseStatus.APPROVED.value),
        "rejected": sum(1 for c in cases if c.get("status") == CaseStatus.REJECTED.value),
        # A case scoring at or above the escalation threshold warrants attention
        # ahead of routine review.
        "high_risk_pending": sum(1 for c in pending if (c.get("riskScore") or 0) >= 60),
        "top_signals": dict(sorted(by_signal.items(), key=lambda kv: -kv[1])[:5]),
        "total": len(cases),
    }


def _serialise(case) -> dict:
    """Prisma record -> plain dict, with the signals JSON decoded."""
    signals = getattr(case, "signals", None)
    if isinstance(signals, str):
        try:
            signals = json.loads(signals)
        except (ValueError, TypeError):
            signals = []
    created = getattr(case, "createdAt", None)
    reviewed = getattr(case, "reviewedAt", None)
    return {
        "id": case.id,
        "userId": case.userId,
        "schemeName": case.schemeName,
        "outcome": case.outcome,
        "riskScore": case.riskScore,
        "signals": signals or [],
        "status": case.status,
        "reviewerId": case.reviewerId,
        "reviewerNote": case.reviewerNote,
        "reviewedAt": reviewed.isoformat() if reviewed else None,
        "createdAt": created.isoformat() if created else None,
    }


# ── Persistence ──────────────────────────────────────────────────────────

async def enqueue(user_id: str, gate_result, dedupe: bool = True) -> str | None:
    """Raise a review case for a flagged application. Returns the case id.

    Returns None (rather than raising) if the queue is unavailable: a database
    fault must not stop the citizen from receiving their form, and losing a
    review case is recoverable while blocking an entitled applicant is not.
    """
    # Decide whether there is anything to record before touching the database.
    # The overwhelming majority of applications are clean, and they should cost
    # nothing — not even a client import.
    risk = gate_result.risk or {}
    if not risk.get("requires_human_review"):
        return None

    from prisma import Json

    from database import prisma

    try:
        if dedupe:
            # One open case per applicant per scheme. Re-submitting the same
            # application should not multiply the reviewer's workload.
            existing = await prisma.reviewcase.find_first(where={
                "userId": user_id,
                "schemeName": gate_result.scheme,
                "status": CaseStatus.PENDING.value,
            })
            if existing:
                return existing.id

        case = await prisma.reviewcase.create(data={
            "userId": user_id,
            "schemeName": gate_result.scheme,
            "outcome": gate_result.outcome.value,
            "riskScore": int(risk.get("risk_score") or 0),
            "signals": Json(risk.get("signals") or []),
            "status": CaseStatus.PENDING.value,
        })
        logger.info("Review case %s raised for %s (risk %s)",
                    case.id, gate_result.scheme, risk.get("risk_score"))
        return case.id
    except Exception as e:
        logger.error(f"Could not raise review case for {gate_result.scheme}: {e}")
        return None


async def list_cases(status: str = "", limit: int = 50, offset: int = 0) -> dict:
    """List review cases, most deserving of attention first."""
    from database import prisma

    where = {"status": status} if status else {}
    records = await prisma.reviewcase.find_many(where=where)
    cases = prioritise([_serialise(r) for r in records])

    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    page = cases[offset:offset + limit]
    return {
        "cases": page,
        "count": len(cases),
        "limit": limit,
        "offset": offset,
        "summary": summarise([_serialise(r) for r in records]),
    }


async def get_case(case_id: str) -> dict | None:
    from database import prisma

    record = await prisma.reviewcase.find_unique(where={"id": case_id})
    return _serialise(record) if record else None


async def decide(case_id: str, decision: str, reviewer_id: str,
                 note: str = "") -> dict:
    """Record a reviewer's decision on a case.

    A rejection must carry a note — refusing a citizen's benefit without a
    stated reason gives them nothing to appeal against.
    """
    from database import prisma

    record = await prisma.reviewcase.find_unique(where={"id": case_id})
    if not record:
        raise TransitionError(f"No review case with id {case_id}")

    validate_transition(record.status, decision)

    if decision == CaseStatus.REJECTED.value and not note.strip():
        raise TransitionError("A rejection must include a reason for the applicant.")
    if not reviewer_id.strip():
        raise TransitionError("Decisions must be attributable to a reviewer.")

    updated = await prisma.reviewcase.update(
        where={"id": case_id},
        data={
            "status": decision,
            "reviewerId": reviewer_id.strip(),
            "reviewerNote": note.strip(),
            "reviewedAt": datetime.now(timezone.utc),
        },
    )
    logger.info("Review case %s %s by %s", case_id, decision, reviewer_id)
    return _serialise(updated)


async def reopen(case_id: str, reviewer_id: str, note: str = "") -> dict:
    """Return a decided case to the queue, preserving why it was reopened."""
    from database import prisma

    record = await prisma.reviewcase.find_unique(where={"id": case_id})
    if not record:
        raise TransitionError(f"No review case with id {case_id}")
    if record.status == CaseStatus.PENDING.value:
        raise TransitionError("This case is already pending.")
    if not reviewer_id.strip():
        raise TransitionError("Reopening must be attributable to a reviewer.")

    prior = f"[reopened from {record.status} by {reviewer_id}]"
    updated = await prisma.reviewcase.update(
        where={"id": case_id},
        data={
            "status": CaseStatus.PENDING.value,
            "reviewerNote": f"{record.reviewerNote} {prior} {note}".strip(),
            "reviewedAt": None,
        },
    )
    return _serialise(updated)


async def cases_for_user(user_id: str) -> list[dict]:
    """A citizen's own review cases, so they can be told a check is in progress."""
    from database import prisma

    records = await prisma.reviewcase.find_many(where={"userId": user_id})
    return prioritise([_serialise(r) for r in records])
