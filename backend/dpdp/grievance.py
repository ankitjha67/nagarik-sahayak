"""Grievance redressal — IT Rules 2021 rule 3(2) and DPDP s13.

Rule 3(2) of the Intermediary Guidelines fixes two hard deadlines: acknowledge a
complaint within **24 hours** and resolve it within **15 days**. DPDP s13 gives a
parallel right to grievance redressal, and s8(7) requires the responsible
person's contact details to be published.

The deadlines are computed and tracked rather than merely documented, because a
complaint whose clock nobody is watching is the normal way these obligations
fail. Anything breached or approaching breach sorts to the top of the queue.

Acknowledgement is automatic on lodgement. A citizen who has just reported a
problem with how their data was handled should not wait a day to learn the
complaint arrived, and the rule's 24-hour limit is an outer bound rather than a
target.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

ACK_DEADLINE_HOURS = 24      # IT Rules 2021, rule 3(2)(i)
RESOLVE_DEADLINE_DAYS = 15   # IT Rules 2021, rule 3(2)(i)


def officer() -> dict:
    """Published contact for the Grievance Officer / DPO.

    Rule 3(2) requires the name and contact to be published. Unset values are
    reported as unset rather than filled with a plausible placeholder — a fake
    officer is worse than a visibly missing one, because it looks satisfied.
    """
    name = os.environ.get("GRIEVANCE_OFFICER_NAME", "")
    email = os.environ.get("GRIEVANCE_OFFICER_EMAIL", "")
    phone = os.environ.get("GRIEVANCE_OFFICER_PHONE", "")
    address = os.environ.get("GRIEVANCE_OFFICER_ADDRESS", "")

    configured = bool(name and email)
    return {
        "name": name or None,
        "email": email or None,
        "phone": phone or None,
        "address": address or None,
        "configured": configured,
        "role": "Grievance Officer and Data Protection contact",
        "statutory_basis": [
            "IT (Intermediary Guidelines) Rules 2021, rule 3(2)",
            "DPDP Act 2023, s8(7) and s13",
        ],
        "service_levels": {
            "acknowledgement_hours": ACK_DEADLINE_HOURS,
            "resolution_days": RESOLVE_DEADLINE_DAYS,
        },
        "escalation": {
            "en": "If your grievance is not resolved, you may complain to the "
                  "Data Protection Board of India.",
            "hi": "यदि आपकी शिकायत का समाधान नहीं होता, तो आप भारतीय डेटा संरक्षण "
                  "बोर्ड को शिकायत कर सकते हैं।",
        },
        # Surfaced so a deployment missing this configuration is visible in the
        # compliance report rather than discovered by a regulator.
        "warning": None if configured else
                   "GRIEVANCE_OFFICER_NAME and GRIEVANCE_OFFICER_EMAIL are not "
                   "set. Rule 3(2) requires these to be published.",
    }


def deadlines_for(created_at: datetime) -> dict:
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return {
        "acknowledge_by": created_at + timedelta(hours=ACK_DEADLINE_HOURS),
        "resolve_by": created_at + timedelta(days=RESOLVE_DEADLINE_DAYS),
    }


def _describe(row) -> dict:
    created = row.createdAt
    if created and created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    dl = deadlines_for(created) if created else {}

    resolved = row.status in ("resolved", "closed") or bool(row.resolvedAt)
    acknowledged = row.status != "received" or resolved

    resolve_by = dl.get("resolve_by")
    overdue = bool(resolve_by and not resolved and now > resolve_by)
    days_left = ((resolve_by - now).days if resolve_by and not resolved else None)

    details = row.details if isinstance(row.details, dict) else {}

    return {
        "id": row.id,
        "user_id": row.userId,
        "request_type": row.requestType,
        "status": row.status,
        "message": details.get("message", ""),
        "created_at": created.isoformat() if created else None,
        "acknowledge_by": dl["acknowledge_by"].isoformat() if dl else None,
        "resolve_by": resolve_by.isoformat() if resolve_by else None,
        "acknowledged": acknowledged,
        "resolved": resolved,
        "overdue": overdue,
        "days_remaining": days_left,
        "resolved_at": row.resolvedAt.isoformat() if row.resolvedAt else None,
    }


async def acknowledge(request_id: str) -> dict:
    """Mark a complaint acknowledged. Done automatically on lodgement."""
    from database import prisma
    row = await prisma.dataprincipalrequest.update(
        where={"id": request_id}, data={"status": "acknowledged"})
    return _describe(row)


async def resolve(request_id: str, resolution: str, officer_id: str = "") -> dict:
    """Close a complaint with a stated resolution.

    The resolution text is required: closing a grievance without saying what was
    done leaves the citizen no better informed than when they complained.
    """
    from database import prisma
    from prisma import Json

    if not resolution.strip():
        raise ValueError("A resolution must say what was done.")

    row = await prisma.dataprincipalrequest.find_unique(where={"id": request_id})
    if not row:
        raise LookupError(f"No such request: {request_id}")

    row = await prisma.dataprincipalrequest.update(
        where={"id": request_id},
        data={
            "status": "resolved",
            "resolvedAt": datetime.now(timezone.utc),
            "response": Json({"resolution": resolution, "officer": officer_id}),
        })
    logger.info("Grievance %s resolved by %s", request_id, officer_id or "unattributed")
    return _describe(row)


async def queue(include_resolved: bool = False) -> dict:
    """Open grievances, most urgent first."""
    from database import prisma

    try:
        rows = await prisma.dataprincipalrequest.find_many()
    except Exception as e:
        logger.error(f"Grievance queue unavailable: {e}")
        return {"grievances": [], "error": str(e)}

    described = [_describe(r) for r in rows]
    if not include_resolved:
        described = [d for d in described if not d["resolved"]]

    # Breached first, then closest to breaching.
    described.sort(key=lambda d: (not d["overdue"],
                                  d["days_remaining"] if d["days_remaining"] is not None else 999))

    return {
        "grievances": described,
        "count": len(described),
        "overdue": sum(1 for d in described if d["overdue"]),
        "awaiting_acknowledgement": sum(1 for d in described if not d["acknowledged"]),
        "officer": officer(),
        "service_levels": {
            "acknowledgement_hours": ACK_DEADLINE_HOURS,
            "resolution_days": RESOLVE_DEADLINE_DAYS,
            "source": "IT (Intermediary Guidelines and Digital Media Ethics "
                      "Code) Rules 2021, rule 3(2)",
        },
    }
