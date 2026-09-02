"""Fraud and abuse detection for government benefit applications.

THREAT MODEL — how this system would actually be abused:

  T1 Identity fabrication   Invented Aadhaar numbers. Defeated cheaply by the
                            Verhoeff checksum in validation.py, so the realistic
                            attack is *reusing someone else's real* number.
  T2 Means-test gaming      Understating income, or declaring zero income while
                            also declaring substantial land — the declarations
                            contradict each other.
  T3 Demographic gaming     Claiming an age or gender the scheme requires:
                            "60" for an old-age pension, female for a widow
                            pension, a child under 10 for Sukanya Samriddhi.
  T4 Duplicate claiming     The same person claiming one scheme repeatedly, or
                            several members of one household each claiming a
                            per-household benefit.
  T5 Benefit diversion      The highest-value attack: a broker files many
                            applications for real, eligible villagers but routes
                            every payment to one bank account they control. The
                            applicants are genuine; the account is the tell.
  T6 Volume abuse           Bulk/automated filing by an agent or script.

DESIGN STANCE — why almost nothing here auto-rejects:

A false positive in a welfare system means a poor person is denied money they
are legally entitled to, and they usually have no practical way to appeal. A
false negative means a reviewer looks at one extra file. These costs are not
symmetric, so this module *scores and routes* rather than refuses.

Only two things stop an application outright, and neither lives here:
objectively invalid data (validation.py) and failing the scheme's own stated
eligibility rules (eligibility_engine.py). Everything in this file produces
ALLOW / REVIEW / ESCALATE — a human decides.
"""
from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from enum import Enum

from validation import compute_age, parse_date


class Decision(str, Enum):
    ALLOW = "allow"        # No meaningful risk signal
    REVIEW = "review"      # Route to a human before disbursement
    ESCALATE = "escalate"  # Strong signal; priority investigation


@dataclass
class Signal:
    code: str
    weight: int
    detail_en: str
    detail_hi: str = ""
    threat: str = ""        # which threat-model entry this covers

    def as_dict(self) -> dict:
        return {
            "code": self.code, "weight": self.weight, "threat": self.threat,
            "detail_en": self.detail_en, "detail_hi": self.detail_hi,
        }


@dataclass
class ApplicantHistory:
    """Cross-applicant context, supplied by the caller.

    Kept as a plain value object so the detection logic stays pure and unit
    testable; a database adapter populates it in production.
    """
    users_sharing_aadhaar: int = 1
    users_sharing_bank_account: int = 1
    users_sharing_mobile: int = 1
    prior_applications_same_scheme: int = 0
    household_claims_same_scheme: int = 0     # matched on ration card
    applications_last_24h: int = 0
    distinct_schemes_last_24h: int = 0

    def as_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class RiskAssessment:
    score: int
    decision: Decision
    signals: list[Signal] = dc_field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "risk_score": self.score,
            "decision": self.decision.value,
            "requires_human_review": self.decision != Decision.ALLOW,
            "signals": [s.as_dict() for s in self.signals],
        }


# Thresholds. Deliberately generous: REVIEW is cheap, refusal is not.
REVIEW_THRESHOLD = 25
ESCALATE_THRESHOLD = 60


def _num(value):
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    import re
    m = re.search(r"-?\d+(?:\.\d+)?", str(value).replace(",", ""))
    return float(m.group()) if m else None


# ── T2/T3: contradictions inside a single application ────────────────────

def check_internal_consistency(profile: dict) -> list[Signal]:
    """Contradictions between fields the same person declared."""
    signals: list[Signal] = []

    # Declared age vs age implied by date of birth. A mismatch is usually a
    # typo, but it is also exactly what age-gaming looks like.
    dob = parse_date(profile.get("date_of_birth"))
    declared_age = _num(profile.get("age"))
    if dob and declared_age is not None:
        implied = compute_age(dob)
        gap = abs(implied - declared_age)
        if gap > 2:
            signals.append(Signal(
                "age_dob_mismatch", 25 if gap > 5 else 15,
                f"Declared age {int(declared_age)} disagrees with date of birth "
                f"({dob.isoformat()} implies {implied}).",
                f"घोषित आयु {int(declared_age)} जन्म तिथि से मेल नहीं खाती "
                f"({dob.isoformat()} से {implied} वर्ष)।",
                threat="T3",
            ))

    # Zero/near-zero income declared alongside meaningful landholding.
    income = _num(profile.get("annual_income"))
    land = _num(profile.get("land_holding_acres"))
    if income is not None and land is not None:
        if income <= 0 and land >= 2:
            signals.append(Signal(
                "zero_income_with_land", 25,
                f"Zero income declared while holding {land} acres of land.",
                f"{land} एकड़ भूमि के साथ शून्य आय घोषित की गई।",
                threat="T2",
            ))
        elif land >= 10 and income < 50000:
            signals.append(Signal(
                "income_land_mismatch", 15,
                f"Income of ₹{int(income)} is low for a holding of {land} acres.",
                f"{land} एकड़ भूमि हेतु ₹{int(income)} आय असामान्य रूप से कम है।",
                threat="T2",
            ))

    # An income-tax payer declaring a below-poverty income.
    if str(profile.get("is_income_tax_payer", "")).strip().lower() == "yes":
        if income is not None and income < 250000:
            signals.append(Signal(
                "taxpayer_low_income", 20,
                f"Declared as an income-tax payer but reports only ₹{int(income)}.",
                f"आयकर दाता घोषित, परंतु केवल ₹{int(income)} आय बताई गई।",
                threat="T2",
            ))

    # BPL claim alongside an income well above any BPL line.
    if str(profile.get("is_bpl", "")).strip().lower() == "yes":
        if income is not None and income > 300000:
            signals.append(Signal(
                "bpl_high_income", 20,
                f"BPL status claimed with a declared income of ₹{int(income)}.",
                f"₹{int(income)} आय के साथ बीपीएल स्थिति का दावा।",
                threat="T2",
            ))

    return signals


# ── T3: scheme-specific demographic gaming ───────────────────────────────

def check_scheme_specific(profile: dict, scheme: dict | None) -> list[Signal]:
    """Signals that only make sense in the context of a particular scheme."""
    if not scheme:
        return []
    signals: list[Signal] = []
    name = (scheme.get("schemeName") or "").lower()

    # Widow/destitute-women pensions are sex-specific by statute.
    if "widow" in name or "destitute" in name:
        gender = str(profile.get("gender", "")).strip().lower()
        if gender and gender not in ("female", "f", "woman", "महिला"):
            signals.append(Signal(
                "gender_scheme_mismatch", 35,
                f"Applicant gender '{profile.get('gender')}' does not match a "
                f"women-only scheme.",
                "आवेदक का लिंग महिला-केवल योजना से मेल नहीं खाता।",
                threat="T3",
            ))
        marital = str(profile.get("marital_status", "")).strip().lower()
        if marital in ("married", "single"):
            signals.append(Signal(
                "marital_status_mismatch", 20,
                f"Marital status '{profile.get('marital_status')}' is "
                f"inconsistent with a widow/destitute pension.",
                "वैवाहिक स्थिति विधवा/निराश्रित पेंशन के अनुरूप नहीं है।",
                threat="T3",
            ))

    # Sukanya Samriddhi is for a girl child under 10.
    if "sukanya" in name:
        dob = parse_date(profile.get("girl_child_dob"))
        age = _num(profile.get("girl_child_age"))
        effective = compute_age(dob) if dob else age
        if effective is not None and effective >= 10:
            signals.append(Signal(
                "child_age_ineligible", 30,
                f"Girl child age {int(effective)} exceeds the 10-year limit.",
                f"बालिका की आयु {int(effective)} वर्ष, 10 वर्ष की सीमा से अधिक।",
                threat="T3",
            ))

    # Old-age pension: an age sitting exactly on the threshold, with no date of
    # birth to corroborate it, is the classic way to claim early.
    if "old age" in name or "ignoaps" in name or "vridha" in name:
        age = _num(profile.get("age"))
        if age is not None and 60 <= age <= 61 and not profile.get("date_of_birth"):
            signals.append(Signal(
                "threshold_age_unverified", 15,
                f"Age {int(age)} sits on the eligibility threshold with no "
                f"date of birth supplied to verify it.",
                f"आयु {int(age)} पात्रता सीमा पर है, परंतु जन्म तिथि नहीं दी गई।",
                threat="T3",
            ))

    return signals


# ── T1/T4/T5/T6: cross-applicant and velocity signals ────────────────────

def check_cross_applicant(history: ApplicantHistory) -> list[Signal]:
    """Signals that only emerge by comparing this application against others."""
    signals: list[Signal] = []
    h = history

    # T1: one Aadhaar across several accounts. Aadhaar is unique per person, so
    # this is either identity theft or one person farming multiple accounts.
    if h.users_sharing_aadhaar > 1:
        signals.append(Signal(
            "aadhaar_shared_across_users",
            40 if h.users_sharing_aadhaar > 2 else 30,
            f"This Aadhaar number is attached to {h.users_sharing_aadhaar} "
            f"different accounts.",
            f"यह आधार संख्या {h.users_sharing_aadhaar} अलग-अलग खातों से जुड़ी है।",
            threat="T1",
        ))

    # T5: the strongest signal in the whole model. Two beneficiaries sharing an
    # account is a plausible family arrangement; five is suspicious; ten or more
    # is a collection point and must escalate on this signal alone, without
    # needing a second signal to reach the threshold.
    if h.users_sharing_bank_account >= 10:
        signals.append(Signal(
            "bank_account_collection_point", ESCALATE_THRESHOLD,
            f"{h.users_sharing_bank_account} applicants are routing payment to "
            f"this one bank account — consistent with benefit diversion.",
            f"{h.users_sharing_bank_account} आवेदक इसी एक बैंक खाते में भुगतान ले रहे हैं।",
            threat="T5",
        ))
    elif h.users_sharing_bank_account >= 5:
        signals.append(Signal(
            "bank_account_collection_point", 45,
            f"{h.users_sharing_bank_account} applicants are routing payment to "
            f"this one bank account.",
            f"{h.users_sharing_bank_account} आवेदक इसी एक बैंक खाते में भुगतान ले रहे हैं।",
            threat="T5",
        ))
    elif h.users_sharing_bank_account >= 3:
        signals.append(Signal(
            "bank_account_shared", 25,
            f"{h.users_sharing_bank_account} applicants share this bank account.",
            f"{h.users_sharing_bank_account} आवेदक यह बैंक खाता साझा कर रहे हैं।",
            threat="T5",
        ))

    # Shared mobile numbers are weakly weighted on purpose: in rural India one
    # handset genuinely serves a whole family, and CSC operators file on behalf
    # of many citizens. Penalising this hard would punish the poorest users.
    if h.users_sharing_mobile >= 10:
        signals.append(Signal(
            "mobile_shared_widely", 15,
            f"This mobile number is used by {h.users_sharing_mobile} applicants "
            f"(may be a shared handset or a CSC operator).",
            f"यह मोबाइल नंबर {h.users_sharing_mobile} आवेदकों द्वारा उपयोग किया जा रहा है।",
            threat="T6",
        ))

    # T4: repeat claims on a one-per-person scheme.
    if h.prior_applications_same_scheme > 0:
        signals.append(Signal(
            "duplicate_scheme_application",
            35 if h.prior_applications_same_scheme > 1 else 25,
            f"This applicant already has {h.prior_applications_same_scheme} "
            f"application(s) for this scheme.",
            f"इस आवेदक के पहले से {h.prior_applications_same_scheme} आवेदन इस योजना हेतु हैं।",
            threat="T4",
        ))

    # T4: several members of one household claiming a per-household benefit.
    if h.household_claims_same_scheme > 1:
        signals.append(Signal(
            "household_duplicate_claim", 25,
            f"{h.household_claims_same_scheme} members of this household have "
            f"claimed the same scheme.",
            f"इस परिवार के {h.household_claims_same_scheme} सदस्यों ने यही योजना ली है।",
            threat="T4",
        ))

    # T6: burst filing.
    if h.applications_last_24h >= 20:
        signals.append(Signal(
            "velocity_extreme", 35,
            f"{h.applications_last_24h} applications filed from this account in "
            f"24 hours.",
            f"24 घंटों में इस खाते से {h.applications_last_24h} आवेदन दायर किए गए।",
            threat="T6",
        ))
    elif h.applications_last_24h >= 8:
        signals.append(Signal(
            "velocity_high", 15,
            f"{h.applications_last_24h} applications filed in 24 hours.",
            f"24 घंटों में {h.applications_last_24h} आवेदन दायर किए गए।",
            threat="T6",
        ))

    return signals


def check_identity_assurance(outcomes) -> list[Signal]:
    """Fold KYC evidence into the risk score.

    Runs in both directions, and the negative direction is the important one.
    A citizen who verified against a UIDAI-signed document has produced better
    evidence than this engine could ever infer from their form, and should meet
    *less* friction, not the same amount. Without that, verifying is all cost
    and no benefit and nobody bothers.

    The positive direction is narrow on purpose: only a contradiction that
    cannot be a spelling or transliteration difference adds weight. Name
    mismatches never reach here as suspicion — they arrive as review flags,
    because a married woman's maiden name on a bank account is not fraud.
    """
    signals: list[Signal] = []
    for outcome in outcomes or []:
        weight = getattr(outcome, "fraud_signal", 0)
        if not weight:
            continue
        method = getattr(outcome, "method", "kyc")
        if weight > 0:
            signals.append(Signal(
                code="identity_document_contradicted", weight=weight,
                threat="T1",
                detail_en=(f"The identity document supplied through {method} "
                           "disagrees with the application on a point that cannot "
                           "be a transcription difference."),
                detail_hi=("आवेदन और प्रस्तुत पहचान दस्तावेज़ में ऐसा अंतर है जो "
                           "लेखन-भिन्नता नहीं हो सकता।")))
        else:
            signals.append(Signal(
                code="identity_verified", weight=weight, threat="T1",
                detail_en=(f"Identity established through {method}, which lowers "
                           "the risk this application needs to be scrutinised for."),
                detail_hi=(f"{method} के माध्यम से पहचान स्थापित, जिससे इस आवेदन की "
                           "जाँच की आवश्यकता कम होती है।")))
    return signals


def assess(
    profile: dict,
    scheme: dict | None = None,
    history: ApplicantHistory | None = None,
    kyc_outcomes=None,
) -> RiskAssessment:
    """Score an application and route it. Never refuses on its own."""
    signals: list[Signal] = []
    signals += check_internal_consistency(profile or {})
    signals += check_scheme_specific(profile or {}, scheme)
    if history is not None:
        signals += check_cross_applicant(history)
    signals += check_identity_assurance(kyc_outcomes)

    # Floored at zero: verification can cancel out suspicion but must never
    # produce a negative score, which would let someone bank credit by
    # verifying and then spend it on genuinely suspicious behaviour.
    score = max(0, min(100, sum(s.weight for s in signals)))
    if score >= ESCALATE_THRESHOLD:
        decision = Decision.ESCALATE
    elif score >= REVIEW_THRESHOLD:
        decision = Decision.REVIEW
    else:
        decision = Decision.ALLOW

    signals.sort(key=lambda s: s.weight, reverse=True)
    return RiskAssessment(score=score, decision=decision, signals=signals)


# ── Database adapter ─────────────────────────────────────────────────────

async def build_history(user_id: str, profile: dict, scheme_name: str) -> ApplicantHistory:
    """Populate ApplicantHistory from stored users and applications.

    Falls back to an empty (all-clear) history if the database is unreachable —
    losing fraud signal is preferable to blocking a citizen because of an
    infrastructure fault.
    """
    import logging
    from datetime import datetime, timedelta, timezone

    logger = logging.getLogger(__name__)
    history = ApplicantHistory()

    try:
        from database import prisma

        # Shared-identifier counts, answered by indexed counting queries against
        # stored fingerprints. This previously loaded every user row and
        # compared in Python, which ran on the critical path of every single
        # application — an O(users) scan per submission.
        import identity_index

        fps = identity_index.fingerprints_for(profile)
        history.users_sharing_aadhaar = 1 + await identity_index.count_sharing(
            prisma, "aadhaarFp", fps["aadhaarFp"], user_id)
        history.users_sharing_bank_account = 1 + await identity_index.count_sharing(
            prisma, "bankAccountFp", fps["bankAccountFp"], user_id)
        history.users_sharing_mobile = 1 + await identity_index.count_sharing(
            prisma, "mobileFp", fps["mobileFp"], user_id)
        history.household_claims_same_scheme = await identity_index.count_sharing(
            prisma, "rationCardFp", fps["rationCardFp"], user_id)

        # Application history for this user.
        apps = await prisma.application.find_many(where={"userId": user_id})
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        recent = 0
        schemes_seen = set()
        for a in apps:
            created = getattr(a, "createdAt", None)
            if created is not None:
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                if created >= cutoff:
                    recent += 1
                    schemes_seen.add(a.schemeId)
        history.applications_last_24h = recent
        history.distinct_schemes_last_24h = len(schemes_seen)

        if scheme_name:
            scheme = await prisma.scheme.find_first(where={"name": scheme_name})
            if scheme:
                history.prior_applications_same_scheme = sum(
                    1 for a in apps if a.schemeId == scheme.id
                )
    except Exception as e:
        logger.warning(f"Fraud history lookup failed, proceeding without it: {e}")

    return history
