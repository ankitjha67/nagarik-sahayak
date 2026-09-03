"""Applicant context for reviewers, assembled at read time.

The ReviewCase table stores no personal data by design. But a reviewer cannot
adjudicate "is this application legitimate?" from a risk score alone — they need
to see who applied and what the flagged signal actually refers to.

This module resolves that context live, on each authorised read, rather than
denormalising it into the queue. Two consequences that matter:

* The queue never becomes a second, less-protected copy of everyone's Aadhaar
  and bank details. Delete the user record and the context disappears with it.
* Reviewers see current data, not a snapshot frozen at flagging time. If the
  citizen has since corrected a typo, the reviewer sees the correction.

Identifiers are masked. A reviewer needs to confirm *which* number was used and
whether two applicants share it — both of which last-four digits answer — not to
read the full number.
"""
from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

# Fields a reviewer legitimately needs to judge an application. Anything not
# listed here is withheld: the queue is for adjudicating a specific flag, not a
# general-purpose window into a citizen's file.
DISCLOSABLE_FIELDS = (
    "name", "father_husband_name", "age", "date_of_birth", "gender",
    "category", "marital_status", "district", "state", "annual_income",
    "land_holding_acres", "is_bpl", "is_income_tax_payer", "occupation",
    "family_members", "girl_child_age",
)

MASKED_FIELDS = {
    "aadhaar_number": "aadhaar",
    "bank_account_number": "account",
    "mobile_number": "phone",
    "ration_card_number": "generic",
}


def mask_identifier(value, kind: str = "generic") -> str:
    """Show only enough of an identifier to compare and verify it.

    Returns "" for empty input so callers can distinguish "not supplied" from
    "supplied but hidden" — the difference matters when the flag is about a
    missing document.
    """
    digits = "".join(ch for ch in str(value or "") if ch.isalnum())
    if not digits:
        return ""
    if kind == "aadhaar" and len(digits) == 12:
        return f"XXXX XXXX {digits[-4:]}"
    if kind == "phone" and len(digits) >= 10:
        return f"XXXXXX{digits[-4:]}"
    if len(digits) <= 4:
        return "X" * len(digits)
    return f"{'X' * (len(digits) - 4)}{digits[-4:]}"


def _load_profile(user) -> dict:
    """Merge a user's extended and basic profiles into one dict."""
    from dpdp import profile_store
    return profile_store.load(user)


def build_applicant_context(user, profile: dict | None = None) -> dict:
    """Assemble the reviewer-visible view of an applicant."""
    profile = profile if profile is not None else _load_profile(user)

    disclosed = {
        k: profile[k] for k in DISCLOSABLE_FIELDS
        if profile.get(k) not in (None, "")
    }
    masked = {
        k: mask_identifier(profile.get(k), kind)
        for k, kind in MASKED_FIELDS.items()
        if profile.get(k) not in (None, "")
    }

    return {
        "user_id": getattr(user, "id", ""),
        "phone_masked": mask_identifier(getattr(user, "phone", ""), "phone"),
        "fields": disclosed,
        "identifiers_masked": masked,
        "fields_supplied": len([v for v in profile.values() if v not in (None, "")]),
        "registered_at": (
            user.createdAt.isoformat() if getattr(user, "createdAt", None) else None
        ),
    }


def explain_signal(signal: dict) -> dict:
    """Attach the reviewer-facing meaning of a risk signal.

    A code and a weight tell a reviewer nothing actionable. What they need is
    what the signal claims, and — just as importantly — the innocent explanation
    they should rule out before treating it as fraud.
    """
    code = signal.get("code", "")
    guidance = SIGNAL_GUIDANCE.get(code, {})
    return {
        **signal,
        "what_it_means": guidance.get("means", ""),
        "innocent_explanation": guidance.get("innocent", ""),
        "suggested_check": guidance.get("check", ""),
    }


# For each signal: what it asserts, the benign reading a reviewer must exclude,
# and the concrete step that settles it. Written so that clearing a flagged
# citizen is as easy as confirming one.
SIGNAL_GUIDANCE: dict[str, dict[str, str]] = {
    "identity_verified": {
        "means": "The applicant produced an identity document that was checked, "
                 "so their identity rests on more than the form they filled in.",
        "innocent": "Not a suspicion at all — this signal lowers the risk score. "
                    "It appears here so a reviewer can see what evidence exists, "
                    "not so it can be second-guessed.",
        "check": "Read the assurance level in the identity panel. VERIFIED means "
                 "a UIDAI signature was checked; DOCUMENTED means a document was "
                 "supplied but its signature was not, and is worth a glance.",
    },
    "identity_document_contradicted": {
        "means": "A document the applicant supplied disagrees with their form on "
                 "a point that cannot be a spelling or transliteration "
                 "difference — in practice, a date of birth off by years.",
        "innocent": "The wrong document may have been uploaded, or it may belong "
                    "to a relative with a similar name. A name or gender "
                    "mismatch NEVER reaches this signal, precisely because those "
                    "have innocent explanations that are more common than fraud.",
        "check": "Open the identity panel and read the per-field comparison. Ask "
                 "the applicant for the document again before drawing any "
                 "conclusion; do not refuse on this alone.",
    },
    "aadhaar_shared_across_users": {
        "means": "The same Aadhaar number is registered to more than one account.",
        "innocent": "A family member or CSC operator may have registered on the "
                    "applicant's behalf using a shared handset and mistyped an entry.",
        "check": "Compare the names and dates of birth on the linked accounts. "
                 "If they differ, treat as identity misuse.",
    },
    "bank_account_collection_point": {
        "means": "Many applicants are routing payment to a single bank account, "
                 "which is the signature of benefit diversion by a middleman.",
        "innocent": "A joint family account, or a guardian receiving on behalf of "
                    "minors or disabled dependants.",
        "check": "Confirm the account holder's name and their stated relationship "
                 "to each applicant. Unrelated applicants sharing one account "
                 "should be escalated.",
    },
    "bank_account_shared": {
        "means": "A small number of applicants share one bank account.",
        "innocent": "Spouses and households routinely share a single account.",
        "check": "Confirm the applicants belong to one household.",
    },
    "mobile_shared_widely": {
        "means": "One mobile number appears across many applications.",
        "innocent": "Very common and usually legitimate — one handset per "
                    "household, or a Common Service Centre operator filing for "
                    "many citizens.",
        "check": "Only pursue if combined with a shared bank account. On its own "
                 "this is weak evidence and should not delay a payment.",
    },
    "duplicate_scheme_application": {
        "means": "This applicant already has an application for this scheme.",
        "innocent": "An earlier attempt may have failed or been abandoned "
                    "mid-form, or the citizen resubmitted after a correction.",
        "check": "Confirm no benefit was disbursed against the earlier "
                 "application before treating this as a duplicate claim.",
    },
    "household_duplicate_claim": {
        "means": "Several members of one household have claimed the same scheme.",
        "innocent": "Some schemes are per-person; only per-household benefits are "
                    "affected.",
        "check": "Confirm whether this scheme is per-household or per-individual "
                 "before acting.",
    },
    "velocity_extreme": {
        "means": "A very large number of applications were filed from this "
                 "account within 24 hours.",
        "innocent": "A CSC operator or NGO assisting many citizens during a camp.",
        "check": "Confirm the operator's identity. Assisted filing is legitimate; "
                 "the applications themselves may all be genuine.",
    },
    "velocity_high": {
        "means": "An elevated number of applications in 24 hours.",
        "innocent": "Assisted filing, or one person applying for several schemes "
                    "in a single sitting — which the app actively encourages.",
        "check": "Usually benign. Check only if paired with a shared account.",
    },
    "age_dob_mismatch": {
        "means": "The declared age does not agree with the date of birth given.",
        "innocent": "Age is frequently recorded approximately, and many older "
                    "citizens have documents with a nominal 1 January birth date.",
        "check": "Take the date of birth on the supporting document as "
                 "authoritative and correct the record.",
    },
    "zero_income_with_land": {
        "means": "Zero income declared alongside a substantial landholding.",
        "innocent": "Genuine after crop failure, or where land is disputed, "
                    "unirrigated or not in the applicant's effective possession.",
        "check": "Request the income certificate and the land record together.",
    },
    "income_land_mismatch": {
        "means": "Declared income is low relative to the landholding.",
        "innocent": "Unirrigated or low-yield land, or land held jointly with "
                    "several other family members.",
        "check": "Verify against the income certificate.",
    },
    "taxpayer_low_income": {
        "means": "Declared as an income-tax payer while reporting an income below "
                 "the taxable threshold.",
        "innocent": "The applicant may have filed a nil return, or misunderstood "
                    "the question.",
        "check": "Request the most recent income-tax return.",
    },
    "bpl_high_income": {
        "means": "BPL status claimed alongside an income well above any BPL line.",
        "innocent": "The income figure may have been entered monthly where the "
                    "form asks for annual, or in the wrong unit.",
        "check": "Confirm the income period, then verify the BPL card.",
    },
    "gender_scheme_mismatch": {
        "means": "The applicant's gender does not match a scheme restricted by sex.",
        "innocent": "A data-entry error, or a guardian applying on behalf of an "
                    "eligible woman using their own details.",
        "check": "Confirm whose application this is before refusing.",
    },
    "marital_status_mismatch": {
        "means": "Marital status is inconsistent with a widow or destitute pension.",
        "innocent": "Status may not have been updated after bereavement, or the "
                    "field may have been left at its default.",
        "check": "Request the death certificate or destitution certificate.",
    },
    "child_age_ineligible": {
        "means": "The girl child's age exceeds the scheme's limit.",
        "innocent": "A mistyped year of birth.",
        "check": "Verify against the birth certificate.",
    },
    "threshold_age_unverified": {
        "means": "Age sits exactly on the eligibility threshold with no date of "
                 "birth supplied to corroborate it.",
        "innocent": "Very common — many older citizens hold no birth record at all.",
        "check": "Accept any recognised age proof; do not refuse for lack of a "
                 "birth certificate alone.",
    },
}


def build_identity_context(case: dict) -> dict:
    """What identity evidence, if any, stands behind this application.

    A reviewer looking at a flagged case needs to know whether the applicant is
    someone who produced a UIDAI-signed document or someone who typed a number
    into a form — those warrant different amounts of scrutiny, and without this
    panel the reviewer cannot tell them apart.

    Absence is reported as a neutral state. "Self-declared" is the normal
    condition of a lawful applicant under the Aadhaar Act s7 proviso, and a
    reviewer must not read it as a strike.
    """
    from kyc import service as kyc_service
    from services.application_guard import _normalise_outcomes

    outcomes = _normalise_outcomes(case.get("kycOutcomes")
                                   or case.get("kyc_outcomes") or [])
    summary = kyc_service.assurance_summary(outcomes)
    # assurance_summary() is written for the citizen and addresses them
    # directly ("Your identity is verified"). Moved under its own key so a
    # reviewer reading this panel knows they are looking at what the applicant
    # was told, not at advice addressed to them.
    summary["citizen_is_told"] = {
        "en": summary.pop("nextStep", ""),
        "hi": summary.pop("nextStepHindi", ""),
    }
    summary["verificationIsOptional"] = True
    summary["reviewer_note"] = (
        "No identity check was completed. That is a normal, lawful state — a "
        "benefit cannot be refused for want of authentication — so weigh this "
        "case on its other evidence."
        if not outcomes else
        "Weigh the assurance level: a checked UIDAI signature is stronger "
        "evidence than anything this system can infer from the form."
    )
    summary["comparisons"] = [
        m.as_dict() if hasattr(m, "as_dict") else m
        for o in outcomes for m in getattr(o, "matches", [])
    ]
    return summary


async def enrich_case(case: dict) -> dict:
    """Add applicant context, identity evidence and signal guidance."""
    enriched = dict(case)
    enriched["signals"] = [explain_signal(s) for s in case.get("signals", []) or []]
    enriched["identity"] = build_identity_context(case)

    try:
        from database import prisma

        user = await prisma.user.find_unique(where={"id": case["userId"]})
        if user:
            profile = _load_profile(user)
            enriched["applicant"] = build_applicant_context(user, profile)

            # The other cases for this applicant are the single most useful piece
            # of context: one flag is noise, a pattern is a decision.
            others = await prisma.reviewcase.find_many(
                where={"userId": case["userId"]}
            )
            enriched["applicant"]["other_cases"] = [
                {
                    "id": o.id, "scheme": o.schemeName, "status": o.status,
                    "risk_score": o.riskScore,
                    "created_at": o.createdAt.isoformat() if o.createdAt else None,
                }
                for o in others if o.id != case.get("id")
            ]
        else:
            enriched["applicant"] = None
            enriched["applicant_error"] = "Applicant record not found"
    except Exception as e:
        logger.warning(f"Could not load applicant context for case {case.get('id')}: {e}")
        enriched["applicant"] = None
        enriched["applicant_error"] = "Applicant context unavailable"

    return enriched
