"""Section 14 nomination, and terms acceptance.

Section 14 lets a Data Principal nominate someone to exercise their rights "in
the event of death or incapacity". Recording a name was the easy half; the hard
half is that the nominee must actually be able to act, and only then.

The design turns on one risk. A nomination that activates on the nominee's own
say-so is a standing account-takeover primitive: anyone who can name themselves
nominee could later assert the citizen has died and take over their record. So
activation is a separate, reviewer-gated step requiring death or incapacity to
have been established, and it is recorded with who established it. Until then a
nominee has no access whatsoever.

The converse risk is real too. A nominee who cannot act when the citizen has
genuinely died leaves a family unable to close out a pension application, which
is exactly the situation section 14 exists to prevent. So activation is
deliberately possible — through a person, on evidence, with an audit trail —
rather than impossible.

What an activated nominee can do is narrower than what the citizen could: read
the record (s11), erase it (s12), and raise a grievance (s13). They cannot
modify the profile or submit new applications in the deceased's name.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# What an activated nominee may exercise. Deliberately excludes anything that
# would let them apply for a benefit as the deceased.
NOMINEE_RIGHTS = ("access", "erasure", "grievance")


async def record(user_id: str, *, name: str, relation: str,
                 contact: str = "") -> dict:
    """Record or replace a nomination (s14).

    Recording confers nothing by itself — the nominee gains access only if a
    reviewer later activates it on evidence of death or incapacity.
    """
    from database import prisma

    name = (name or "").strip()
    relation = (relation or "").strip()
    if not name:
        raise ValueError("A nominee's name is required.")
    if not relation:
        raise ValueError("State the nominee's relationship to you.")

    await prisma.user.update(where={"id": user_id}, data={
        "nomineeName": name,
        "nomineeRelation": relation,
        "nomineeContact": (contact or "").strip(),
        "nomineeRecordedAt": datetime.now(timezone.utc),
        # Replacing a nomination clears any prior activation: the new nominee
        # must be activated on its own evidence.
        "nomineeActivatedAt": None,
        "nomineeActivatedBy": None,
    })
    logger.info("Nomination recorded for %s", user_id)
    return {
        "recorded": True,
        "nominee": {"name": name, "relation": relation},
        "message_en": "Your nominee has been recorded. They can act only if "
                      "you die or become unable to act for yourself, and only "
                      "after that has been verified.",
        "message_hi": "आपका नामित व्यक्ति दर्ज कर लिया गया है। वे केवल आपकी "
                      "मृत्यु या अक्षमता की स्थिति में, सत्यापन के बाद ही "
                      "कार्य कर सकते हैं।",
    }


async def remove(user_id: str) -> dict:
    """Withdraw a nomination."""
    from database import prisma

    await prisma.user.update(where={"id": user_id}, data={
        "nomineeName": None, "nomineeRelation": None, "nomineeContact": None,
        "nomineeRecordedAt": None,
        "nomineeActivatedAt": None, "nomineeActivatedBy": None,
    })
    return {"removed": True}


async def status(user_id: str) -> dict:
    """The citizen's own view of their nomination."""
    from database import prisma

    user = await prisma.user.find_unique(where={"id": user_id})
    if not user:
        return {"error": "User not found"}

    name = getattr(user, "nomineeName", None)
    if not name:
        return {
            "has_nominee": False,
            "right": "DPDP Act 2023, s14 — you may nominate someone to "
                     "exercise your rights if you die or become incapable.",
            "rights_they_would_have": list(NOMINEE_RIGHTS),
        }

    recorded = getattr(user, "nomineeRecordedAt", None)
    activated = getattr(user, "nomineeActivatedAt", None)
    return {
        "has_nominee": True,
        "nominee": {
            "name": name,
            "relation": getattr(user, "nomineeRelation", ""),
            "contact": getattr(user, "nomineeContact", ""),
        },
        "recorded_at": recorded.isoformat() if recorded else None,
        "active": bool(activated),
        "activated_at": activated.isoformat() if activated else None,
        "rights_they_would_have": list(NOMINEE_RIGHTS),
        "note_en": "Your nominee has no access unless and until your death or "
                   "incapacity is verified.",
        "note_hi": "आपकी मृत्यु या अक्षमता के सत्यापन तक नामित व्यक्ति को कोई "
                   "पहुँच नहीं है।",
    }


async def activate(user_id: str, *, reviewer_id: str, evidence: str) -> dict:
    """Allow a nominee to act, on established death or incapacity.

    Reviewer-gated and evidence-bearing by design. Activation transfers control
    of a citizen's record, so it must be attributable to a person who can be
    asked why they did it.
    """
    from database import prisma

    evidence = (evidence or "").strip()
    if not evidence:
        raise ValueError(
            "State the evidence of death or incapacity. Activation transfers "
            "control of a citizen's record and must be justifiable.")
    if not reviewer_id:
        raise ValueError("Activation must be attributable to a reviewer.")

    user = await prisma.user.find_unique(where={"id": user_id})
    if not user:
        raise LookupError("User not found")
    if not getattr(user, "nomineeName", None):
        raise LookupError("This citizen has not nominated anyone.")
    if getattr(user, "nomineeActivatedAt", None):
        raise ValueError("This nomination is already active.")

    now = datetime.now(timezone.utc)
    await prisma.user.update(where={"id": user_id}, data={
        "nomineeActivatedAt": now,
        "nomineeActivatedBy": reviewer_id,
    })

    # Logged at WARNING: this is a rare, high-consequence action and should
    # surface in alerting rather than sit unnoticed in an access log.
    logger.warning(
        "NOMINATION ACTIVATED for %s by reviewer %s — nominee '%s' may now "
        "exercise %s. Evidence: %s",
        user_id, reviewer_id, user.nomineeName, ", ".join(NOMINEE_RIGHTS),
        evidence,
    )

    # Recorded as a request so it appears in the same audit trail as every
    # other rights action taken on this citizen's behalf.
    try:
        from dpdp import consent
        await consent.log_request(user_id, "nomination_activated", {
            "reviewer": reviewer_id, "evidence": evidence,
            "nominee": user.nomineeName,
        })
    except Exception as e:
        logger.error(f"Could not log nomination activation: {e}")

    return {
        "activated": True,
        "nominee": user.nomineeName,
        "activated_by": reviewer_id,
        "activated_at": now.isoformat(),
        "rights_granted": list(NOMINEE_RIGHTS),
    }


async def is_active(user_id: str) -> bool:
    """Whether a nominee may currently act for this citizen."""
    from database import prisma
    try:
        user = await prisma.user.find_unique(where={"id": user_id})
        return bool(user and getattr(user, "nomineeActivatedAt", None))
    except Exception as e:
        logger.error(f"Nomination check failed for {user_id}: {e}")
        # Fail closed: an infrastructure fault must not grant access to
        # someone else's record.
        return False


# ── Terms acceptance (IT Rules 3(1)(a)) ──────────────────────────────────

async def accept_terms(user_id: str, version: str) -> dict:
    """Record that this citizen accepted a specific version of the terms."""
    from database import prisma

    await prisma.user.update(where={"id": user_id}, data={
        "termsVersion": version,
        "termsAcceptedAt": datetime.now(timezone.utc),
    })
    return {"accepted": True, "version": version}


async def terms_status(user_id: str) -> dict:
    """Whether the citizen has accepted the current terms.

    A superseded acceptance counts as not accepted: material changes should be
    read, not inherited silently from a version the person never saw.
    """
    from database import prisma
    from dpdp.terms import TERMS_VERSION

    try:
        user = await prisma.user.find_unique(where={"id": user_id})
    except Exception:
        user = None

    accepted_version = getattr(user, "termsVersion", None) if user else None
    accepted_at = getattr(user, "termsAcceptedAt", None) if user else None
    current = accepted_version == TERMS_VERSION

    return {
        "current_version": TERMS_VERSION,
        "accepted_version": accepted_version,
        "accepted_at": accepted_at.isoformat() if accepted_at else None,
        "accepted": current,
        "needs_acceptance": not current,
        "reason": None if current else (
            "You have not accepted the terms yet."
            if not accepted_version else
            f"The terms have changed since you accepted version "
            f"{accepted_version}. Please read the new version."
        ),
    }
