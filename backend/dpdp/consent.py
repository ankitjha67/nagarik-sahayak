"""Section 6 consent, and the section 11–14 rights of the Data Principal.

Section 6 sets a specific bar: consent must be free, specific, informed,
unconditional and unambiguous, given by clear affirmative action, and limited to
the data *necessary* for the stated purpose. Two consequences shape this module.

First, consent is recorded **per purpose**, never as one blanket agreement. A
citizen who consented to having their form pre-filled has not thereby agreed to
service alerts, and the record has to be able to show that.

Second, section 6(4) requires withdrawal to be **as easy as giving**. So
withdrawal is one call with the same shape as granting, and it does not require
a reason. Withdrawing does not delete the consent row — the history of having
consented and then withdrawn is itself the evidence a Data Fiduciary must be
able to produce, and destroying it would defeat the audit the Act contemplates.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from dpdp import registry
from dpdp.registry import Purpose

logger = logging.getLogger(__name__)

# Bumped whenever the section 5 notice text changes. Consent is to a specific
# notice; if the notice changes materially, prior consent no longer covers it.
NOTICE_VERSION = "1.0"


class RequestType:
    """Section 11–14 rights."""
    ACCESS = "access"            # s11 — summary of data and processing
    CORRECTION = "correction"    # s12 — correct or complete
    ERASURE = "erasure"          # s12 — erase
    GRIEVANCE = "grievance"      # s13
    NOMINATION = "nomination"    # s14


async def grant(user_id: str, purposes: list[str], *, language: str = "hi",
                parental: bool = False) -> dict:
    """Record consent for specific purposes."""
    from database import prisma

    valid = {p.value for p in Purpose}
    unknown = [p for p in purposes if p not in valid]
    if unknown:
        raise ValueError(f"Unknown purpose(s): {', '.join(unknown)}")

    recorded = []
    for purpose in purposes:
        existing = await prisma.consentrecord.find_first(
            where={"userId": user_id, "purpose": purpose})
        data = {
            "granted": True, "withdrawnAt": None,
            "noticeVersion": NOTICE_VERSION, "language": language,
            "parentalConsent": parental, "grantedAt": datetime.now(timezone.utc),
        }
        if existing:
            await prisma.consentrecord.update(where={"id": existing.id}, data=data)
        else:
            await prisma.consentrecord.create(
                data={"userId": user_id, "purpose": purpose, **data})
        recorded.append(purpose)

    logger.info("Consent granted by %s for %s", user_id, ", ".join(recorded))
    return {"granted": recorded, "notice_version": NOTICE_VERSION,
            "parental_consent": parental}


async def withdraw(user_id: str, purposes: list[str] | None = None) -> dict:
    """Withdraw consent. No reason required — s6(4) makes this a right.

    Passing no purposes withdraws all of them, because a citizen who wants out
    should not have to enumerate what they once agreed to.
    """
    from database import prisma

    where = {"userId": user_id, "granted": True}
    if purposes:
        rows = [r for r in await prisma.consentrecord.find_many(where=where)
                if r.purpose in purposes]
    else:
        rows = await prisma.consentrecord.find_many(where=where)

    now = datetime.now(timezone.utc)
    for row in rows:
        await prisma.consentrecord.update(
            where={"id": row.id},
            data={"granted": False, "withdrawnAt": now})

    withdrawn = [r.purpose for r in rows]
    logger.info("Consent withdrawn by %s for %s", user_id, ", ".join(withdrawn) or "nothing")
    return {
        "withdrawn": withdrawn,
        # s6(5): processing must stop within a reasonable time. Being explicit
        # here means the caller can tell the citizen what actually happens next.
        "consequence": "Processing for these purposes will stop. Data kept only "
                       "where another law requires it.",
        "consequence_hi": "इन उद्देश्यों हेतु प्रसंस्करण रोक दिया जाएगा। "
                          "डेटा केवल तभी रखा जाएगा जब कोई अन्य कानून आवश्यक करे।",
    }


async def consented_purposes(user_id: str) -> set[str]:
    """Purposes this citizen currently consents to."""
    from database import prisma
    try:
        rows = await prisma.consentrecord.find_many(
            where={"userId": user_id, "granted": True})
        return {r.purpose for r in rows}
    except Exception as e:
        logger.error(f"Consent lookup failed for {user_id}: {e}")
        return set()


async def has_parental_consent(user_id: str) -> bool:
    """Whether a guardian has consented for a child's data (s9)."""
    from database import prisma
    try:
        rows = await prisma.consentrecord.find_many(
            where={"userId": user_id, "granted": True})
        return any(r.parentalConsent for r in rows)
    except Exception:
        return False


async def consent_status(user_id: str) -> dict:
    """Full consent position, including what has been withdrawn."""
    from database import prisma
    try:
        rows = await prisma.consentrecord.find_many(where={"userId": user_id})
    except Exception as e:
        logger.error(f"Consent status failed for {user_id}: {e}")
        rows = []

    granted = [r for r in rows if r.granted]
    return {
        "user_id": user_id,
        "notice_version": NOTICE_VERSION,
        "granted": [{
            "purpose": r.purpose,
            "granted_at": r.grantedAt.isoformat() if r.grantedAt else None,
            "notice_version": r.noticeVersion,
            "parental_consent": r.parentalConsent,
        } for r in granted],
        "withdrawn": [{
            "purpose": r.purpose,
            "withdrawn_at": r.withdrawnAt.isoformat() if r.withdrawnAt else None,
        } for r in rows if not r.granted],
        "available_purposes": [{
            "purpose": p.value,
            "field_count": len(registry.fields_for_purpose(p)),
            "consented": p.value in {r.purpose for r in granted},
        } for p in Purpose],
    }


# ── Section 11: right to access information ──────────────────────────────

async def access_summary(user_id: str) -> dict:
    """The summary section 11 entitles a citizen to.

    Section 11(1) requires a summary of the personal data being processed and
    the processing activities undertaken — not a raw dump. It also requires the
    identities of other Data Fiduciaries the data has been shared with, which is
    why third-party disclosure is listed explicitly rather than left implicit.
    """
    import json
    from database import prisma

    user = await prisma.user.find_unique(where={"id": user_id})
    if not user:
        return {"error": "No record found for this user."}

    profile: dict = {}
    for raw in (user.fullProfile, user.profile):
        if not raw:
            continue
        try:
            data = json.loads(raw) if isinstance(raw, str) else dict(raw)
        except (ValueError, TypeError):
            continue
        for k, v in data.items():
            if k not in profile or profile[k] in (None, ""):
                profile[k] = v

    held = []
    for key, value in profile.items():
        if value in (None, "") or key.startswith("_"):
            continue
        rec = registry.record_for(key)
        held.append({
            "field": key,
            "category": rec.category.value if rec else "unclassified",
            "purposes": [p.value for p in rec.purposes] if rec else [],
            "retention_days": rec.retention_days if rec else None,
            "used_for_decisions": rec.decisional if rec else False,
            # The value itself is deliberately not returned here; a separate,
            # explicitly-requested export carries it.
            "is_held": True,
        })

    try:
        applications = await prisma.application.find_many(where={"userId": user_id})
    except Exception:
        applications = []
    try:
        chat_count = len(await prisma.chatlog.find_many(where={"userId": user_id}))
    except Exception:
        chat_count = 0

    return {
        "user_id": user_id,
        "personal_data_held": held,
        "field_count": len(held),
        "processing_activities": [
            {"activity": "Eligibility assessment",
             "purpose": Purpose.SCHEME_ELIGIBILITY.value,
             "description": "Your declared details are compared against each "
                            "scheme's published conditions."},
            {"activity": "Form completion",
             "purpose": Purpose.FORM_COMPLETION.value,
             "description": "Your details are written into government "
                            "application forms you asked for."},
            {"activity": "Fraud prevention",
             "purpose": Purpose.FRAUD_PREVENTION.value,
             "description": "Identifiers are compared, as one-way hashes, "
                            "against other applications to detect misuse of "
                            "public funds."},
        ],
        "applications_count": len(applications),
        "chat_messages_count": chat_count,
        # s11(1)(c): who else has received the data.
        "shared_with": _disclosure_register(),
        "consent": await consent_status(user_id),
        "your_rights": _rights_summary(),
    }


def _disclosure_register() -> list[dict]:
    """Third parties that may receive personal data, and what they receive.

    Kept honest and specific: naming a recipient without saying what reaches
    them tells the citizen nothing useful.
    """
    return [
        {"recipient": "Analytics provider (Agnost)",
         "data": "Usage events with personal data redacted before sending.",
         "purpose": "Service quality monitoring"},
        {"recipient": "Language model provider",
         "data": "Text of blank government forms during field extraction. "
                 "Your own answers are not sent.",
         "purpose": "Reading form structure"},
        {"recipient": "Speech-to-text provider (Sarvam AI)",
         "data": "Voice recordings you choose to send, and their transcripts.",
         "purpose": "Voice input"},
        {"recipient": "Departmental reviewers",
         "data": "Application details, with identifiers masked to last four "
                 "digits, when an application is flagged for verification.",
         "purpose": "Fraud prevention"},
    ]


def _rights_summary() -> list[dict]:
    return [
        {"section": "11", "right": "Access information",
         "how": "GET /api/dpdp/my-data"},
        {"section": "12", "right": "Correction and completion",
         "how": "POST /api/dpdp/request with request_type=correction"},
        {"section": "12", "right": "Erasure",
         "how": "POST /api/dpdp/erase"},
        {"section": "13", "right": "Grievance redressal",
         "how": "POST /api/dpdp/request with request_type=grievance"},
        {"section": "14", "right": "Nominate another person",
         "how": "POST /api/dpdp/request with request_type=nomination"},
        {"section": "6(4)", "right": "Withdraw consent at any time",
         "how": "POST /api/dpdp/consent/withdraw"},
    ]


async def log_request(user_id: str, request_type: str, details: dict | None = None) -> dict:
    """Record a section 11–14 request so it is tracked to resolution."""
    from database import prisma
    from prisma import Json

    row = await prisma.dataprincipalrequest.create(data={
        "userId": user_id, "requestType": request_type,
        "details": Json(details or {}),
    })
    logger.info("DPDP %s request recorded for %s", request_type, user_id)
    return {"request_id": row.id, "request_type": request_type,
            "status": row.status,
            "created_at": row.createdAt.isoformat() if row.createdAt else None}
