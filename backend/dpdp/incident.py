"""Cyber incident and data breach handling — CERT-In 2022 and DPDP s8(5).

Two regimes apply to the same event and they are not the same obligation, which
is the thing most implementations get wrong:

* **CERT-In Directions 2022** require reporting to CERT-In within **6 hours** of
  becoming aware of a cyber security incident, and maintenance of ICT logs for a
  rolling **180 days stored within India**.
* **DPDP s8(5)** requires notifying the Data Protection Board *and every affected
  Data Principal* of a personal data breach.

So one incident can carry three separate notifications on two different clocks.
They are tracked separately here rather than collapsed into a single "notified"
flag, because satisfying one does not satisfy the others.

What this module does not do is transmit anything. CERT-In reporting goes to a
specific channel with credentials an operator must supply, and silently
pretending to have reported would be worse than not reporting: it would hide the
gap. Instead the register computes the deadline, marks what is overdue, and
makes the outstanding obligation impossible to miss.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from enum import Enum

logger = logging.getLogger(__name__)

# CERT-In Directions 2022, direction (i).
CERT_IN_DEADLINE_HOURS = 6
# CERT-In Directions 2022, direction (iv) — rolling window, stored in India.
LOG_RETENTION_DAYS = 180


class IncidentSeverity(str, Enum):
    CRITICAL = "critical"   # personal data confirmed exposed
    HIGH = "high"           # exposure likely
    MEDIUM = "medium"
    LOW = "low"


class IncidentCategory(str, Enum):
    """Categories drawn from the CERT-In Annexure I incident types."""
    DATA_BREACH = "data_breach"
    UNAUTHORISED_ACCESS = "unauthorised_access"
    IDENTITY_THEFT = "identity_theft"
    MALICIOUS_CODE = "malicious_code"
    DENIAL_OF_SERVICE = "denial_of_service"
    DATA_LEAK = "data_leak"
    SYSTEM_COMPROMISE = "system_compromise"


async def record(
    *,
    category: str,
    severity: str,
    description: str,
    affected_count: int = 0,
    detected_at: datetime | None = None,
) -> dict:
    """Record an incident and compute what must be reported, and by when."""
    from database import prisma

    detected_at = detected_at or datetime.now(timezone.utc)
    row = await prisma.breachrecord.create(data={
        "detectedAt": detected_at,
        "severity": severity,
        "category": category,
        "description": description,
        "affectedCount": affected_count,
    })

    deadline = detected_at + timedelta(hours=CERT_IN_DEADLINE_HOURS)
    # Logged at ERROR so it surfaces in alerting rather than sitting in a table
    # nobody reads until an audit.
    logger.error(
        "SECURITY INCIDENT %s (%s/%s): %s. CERT-In report due by %s; "
        "%d data principal(s) affected.",
        row.id, category, severity, description,
        deadline.isoformat(), affected_count,
    )
    return _describe(row)


def _describe(row) -> dict:
    detected = row.detectedAt
    if detected and detected.tzinfo is None:
        detected = detected.replace(tzinfo=timezone.utc)
    deadline = detected + timedelta(hours=CERT_IN_DEADLINE_HOURS) if detected else None
    now = datetime.now(timezone.utc)

    overdue = bool(deadline and not row.boardNotified and now > deadline)
    hours_left = ((deadline - now).total_seconds() / 3600) if deadline else None

    return {
        "id": row.id,
        "detected_at": detected.isoformat() if detected else None,
        "severity": row.severity,
        "category": row.category,
        "description": row.description,
        "affected_count": row.affectedCount,
        "cert_in": {
            "deadline": deadline.isoformat() if deadline else None,
            "hours_remaining": round(hours_left, 2) if hours_left is not None else None,
            "overdue": overdue,
            "reported": row.boardNotified,
        },
        # DPDP s8(5) creates two distinct duties; a single flag would let one
        # be quietly forgotten once the other was done.
        "dpdp": {
            "board_notified": row.boardNotified,
            "principals_notified": row.principalsNotified,
            "both_complete": bool(row.boardNotified and row.principalsNotified),
        },
        "resolved_at": row.resolvedAt.isoformat() if row.resolvedAt else None,
    }


async def mark_notified(incident_id: str, *, board: bool | None = None,
                        principals: bool | None = None) -> dict:
    from database import prisma

    data = {}
    if board is not None:
        data["boardNotified"] = board
    if principals is not None:
        data["principalsNotified"] = principals
    if not data:
        raise ValueError("Specify board and/or principals")

    row = await prisma.breachrecord.update(where={"id": incident_id}, data=data)
    return _describe(row)


async def resolve(incident_id: str) -> dict:
    from database import prisma
    row = await prisma.breachrecord.update(
        where={"id": incident_id},
        data={"resolvedAt": datetime.now(timezone.utc)})
    return _describe(row)


async def register(include_resolved: bool = False) -> dict:
    """The incident register, with anything overdue surfaced first."""
    from database import prisma

    try:
        rows = await prisma.breachrecord.find_many()
    except Exception as e:
        logger.error(f"Incident register unavailable: {e}")
        return {"incidents": [], "error": str(e)}

    described = [_describe(r) for r in rows
                 if include_resolved or not r.resolvedAt]
    described.sort(key=lambda d: (not d["cert_in"]["overdue"],
                                  d["detected_at"] or ""), reverse=False)

    return {
        "incidents": described,
        "count": len(described),
        "overdue_cert_in": sum(1 for d in described if d["cert_in"]["overdue"]),
        "awaiting_principal_notification": sum(
            1 for d in described if not d["dpdp"]["principals_notified"]),
        "policy": {
            "cert_in_deadline_hours": CERT_IN_DEADLINE_HOURS,
            "log_retention_days": LOG_RETENTION_DAYS,
            "log_residency": "India",
            "source": "CERT-In Directions dated 28 April 2022, in force from "
                      "28 June 2022",
        },
    }


def log_policy() -> dict:
    """The declared logging posture, for the compliance report.

    Asserted here and enforced in the deployment: the application cannot
    guarantee where its logs are shipped, so this states the requirement rather
    than claiming it is met.
    """
    return {
        "retention_days": LOG_RETENTION_DAYS,
        "residency_required": "India",
        "requirement": "CERT-In Directions 2022 direction (iv): enable logs of "
                       "all ICT systems, maintain for a rolling 180 days within "
                       "Indian jurisdiction, and furnish to CERT-In on demand.",
        "time_sync_required": "NTP synchronised to NIC (samay1.nic.in) or NPL "
                              "(time.nplindia.org) per direction (ii).",
        "enforced_by": "deployment configuration, not the application",
    }
