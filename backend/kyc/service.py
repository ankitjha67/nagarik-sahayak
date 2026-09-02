"""KYC orchestration — run a method, compare the result, decide what happens next.

The single rule this module enforces is that **verification decides nothing**.
It produces evidence: an assurance level, a set of field comparisons, and a
recommendation. Approval and refusal remain with the eligibility engine and a
human reviewer.

That is not timidity. Every automated identity check in this design has a
predictable false-negative population, and it is always the same people: the
widow whose bank account carries her maiden name, the labourer whose UIDAI
record holds only a year of birth, the migrant struck off an electoral roll.
An automatic refusal on a name mismatch would exclude them silently and at
scale, and they have no way to appeal something they were never told about. A
review queue costs an officer four minutes.

The one thing that *is* decided automatically is the opposite direction: a
verified match raises assurance, which lowers fraud scrutiny and lets an honest
application through faster. Automation is used to admit, not to refuse.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field as dc_field
from datetime import datetime, timezone

from kyc import aadhaar_offline, matching
from kyc.methods import Assurance, Availability, KycMethod, get as get_method

logger = logging.getLogger(__name__)

# Below this aggregate score the outcome goes to a reviewer. Set generously:
# the cost of a needless review is an officer's minute, the cost of a wrong
# refusal is a family's entitlement.
REVIEW_THRESHOLD = 0.85

# Attempts allowed against a share code before the artefact is locked out, so
# a stolen e-KYC ZIP cannot be brute-forced through this endpoint.
MAX_SHARE_CODE_ATTEMPTS = 5


@dataclass
class VerificationOutcome:
    """Evidence produced by one KYC attempt. Not a decision."""
    method: str
    succeeded: bool
    assurance: Assurance
    established: dict = dc_field(default_factory=dict)
    matches: list[matching.MatchResult] = dc_field(default_factory=list)
    score: float = 0.0
    contradicted: bool = False
    needs_review: bool = False
    message_en: str = ""
    message_hi: str = ""
    warnings: list[str] = dc_field(default_factory=list)
    verified_at: str = ""
    # Weight handed to the fraud engine. Positive raises suspicion; negative
    # lowers it, because a verified identity is evidence of honesty and should
    # reduce the friction an honest applicant meets.
    fraud_signal: int = 0

    def as_dict(self) -> dict:
        return {
            "method": self.method,
            "succeeded": self.succeeded,
            "assurance": int(self.assurance),
            "assuranceLabel": self.assurance.label_en,
            "assuranceLabelHindi": self.assurance.label_hi,
            "established": dict(self.established),
            "matches": [m.as_dict() for m in self.matches],
            "score": round(self.score, 3),
            "contradicted": self.contradicted,
            "needsReview": self.needs_review,
            "message": self.message_en,
            "messageHindi": self.message_hi,
            "warnings": list(self.warnings),
            "verifiedAt": self.verified_at,
            "fraudSignal": self.fraud_signal,
        }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_usable(key: str) -> KycMethod:
    method = get_method(key)
    if method is None:
        raise ValueError(f"Unknown KYC method: {key}")
    if not method.effective_availability.is_usable:
        missing = ", ".join(k for k in method.config_keys) or "an external licence"
        raise RuntimeError(
            f"{method.name_en} is not enabled on this deployment "
            f"({method.effective_availability.value}; needs {missing})")
    return method


def _assess(profile: dict, record_demographics: dict, method: str,
            achieved: Assurance, warnings: list[str]) -> VerificationOutcome:
    """Compare a verified record against what the citizen claimed."""
    matches = matching.compare_profile(profile, record_demographics)
    score, contradicted = matching.overall(matches)

    # No overlapping fields to compare — the citizen has not filled anything in
    # yet. Not a failure: the record is used to *populate* the profile.
    if not matches:
        return VerificationOutcome(
            method=method, succeeded=True, assurance=achieved,
            established=record_demographics, matches=[], score=1.0,
            needs_review=achieved < Assurance.VERIFIED,
            message_en="Your details were read from the document and filled in. "
                       "Please check them before you submit.",
            message_hi="आपका विवरण दस्तावेज़ से पढ़कर भर दिया गया है। जमा करने से "
                       "पहले कृपया जाँच लें।",
            warnings=warnings, verified_at=_now(),
            fraud_signal=-10 if achieved >= Assurance.VERIFIED else 0)

    needs_review = contradicted or score < REVIEW_THRESHOLD or achieved < Assurance.VERIFIED

    if contradicted:
        msg_en = ("The document does not agree with what was entered on a point "
                  "that cannot be a spelling difference. Your application will "
                  "go to an officer, who will contact you. It has not been "
                  "refused.")
        msg_hi = ("दस्तावेज़ और दर्ज विवरण में ऐसा अंतर है जो वर्तनी की भिन्नता "
                  "नहीं हो सकती। आपका आवेदन अधिकारी के पास जाएगा, जो आपसे संपर्क "
                  "करेंगे। इसे अस्वीकार नहीं किया गया है।")
        signal = 35
    elif score < REVIEW_THRESHOLD:
        msg_en = ("Some details differ slightly from your document. This is "
                  "common and usually harmless — an officer will check and your "
                  "application continues meanwhile.")
        msg_hi = ("कुछ विवरण आपके दस्तावेज़ से थोड़े भिन्न हैं। यह सामान्य एवं "
                  "प्रायः निर्दोष है — अधिकारी जाँच करेंगे और इस बीच आपका आवेदन "
                  "चलता रहेगा।")
        signal = 5
    else:
        msg_en = "Your details match the document."
        msg_hi = "आपका विवरण दस्तावेज़ से मेल खाता है।"
        signal = -15 if achieved >= Assurance.VERIFIED else -5

    return VerificationOutcome(
        method=method, succeeded=True, assurance=achieved,
        established=record_demographics, matches=matches, score=score,
        contradicted=contradicted, needs_review=needs_review,
        message_en=msg_en, message_hi=msg_hi, warnings=warnings,
        verified_at=_now(), fraud_signal=signal)


# ── Concrete methods ─────────────────────────────────────────────────────

def verify_offline_xml(profile: dict, zip_bytes: bytes,
                       share_code: str) -> VerificationOutcome:
    """Aadhaar Offline e-KYC ZIP. Raises OfflineKycError with a citizen-facing
    message; the caller turns that into a 400 rather than a 500."""
    _require_usable("aadhaar_offline_xml")
    record = aadhaar_offline.parse_offline_xml(zip_bytes, share_code)
    return _assess(profile, aadhaar_offline.to_profile(record),
                   "aadhaar_offline_xml", record.assurance,
                   list(record.warnings) + _signature_warning(record))


def verify_secure_qr(profile: dict, qr_value: str) -> VerificationOutcome:
    """Aadhaar Secure QR from an e-Aadhaar letter or PVC card."""
    _require_usable("aadhaar_secure_qr")
    record = aadhaar_offline.parse_secure_qr(qr_value)
    return _assess(profile, aadhaar_offline.to_profile(record),
                   "aadhaar_secure_qr", record.assurance,
                   list(record.warnings) + _signature_warning(record))


def _signature_warning(record) -> list[str]:
    if record.signature_verified:
        return []
    return [record.signature_note_en]


def record_attestation(profile: dict, *, method: str, attestor_name: str,
                       attestor_role: str, attestor_id: str = "",
                       documents_seen: list[str] | None = None) -> VerificationOutcome:
    """A human attests, on the record, that they saw the applicant and documents.

    The attestor's own identity is captured, which is the whole point: an
    unattributable attestation is worthless, and an attributable one lets the
    fraud engine notice a single operator vouching for an implausible number of
    applications without ever refusing an individual citizen for the operator's
    behaviour.
    """
    m = _require_usable(method)
    if not attestor_name.strip() or not attestor_role.strip():
        return VerificationOutcome(
            method=method, succeeded=False, assurance=Assurance.NONE,
            message_en="An attestation must name the officer or operator making it.",
            message_hi="प्रमाणन में उसे करने वाले अधिकारी अथवा संचालक का नाम आवश्यक है।",
            verified_at=_now())

    established = {k: profile[k] for k in m.establishes
                   if profile.get(k) not in (None, "")}
    return VerificationOutcome(
        method=method, succeeded=True, assurance=m.assurance,
        established=established, score=1.0,
        # Always reviewed: a human vouching is evidence, not proof, and the
        # attestation itself is what a reviewer is checking.
        needs_review=True,
        message_en=f"Recorded as attested by {attestor_name} ({attestor_role}). "
                   "An officer will confirm the attestation.",
        message_hi=f"{attestor_name} ({attestor_role}) द्वारा प्रमाणित के रूप में "
                   "दर्ज। अधिकारी प्रमाणन की पुष्टि करेंगे।",
        warnings=[] if attestor_id else
                 ["No identifier was recorded for the attestor, so repeat "
                  "attestations by the same person cannot be linked."],
        verified_at=_now(), fraud_signal=-5)


def record_document_upload(profile: dict, *, document_type: str,
                           artefact_id: str) -> VerificationOutcome:
    """A document was uploaded and stored encrypted for a reviewer."""
    _require_usable("document_upload")
    return VerificationOutcome(
        method="document_upload", succeeded=True, assurance=Assurance.DOCUMENTED,
        established={}, score=1.0, needs_review=True,
        message_en=f"Your {document_type} has been received and will be checked by "
                   "an officer. Nothing further is needed from you right now.",
        message_hi=f"आपका {document_type} प्राप्त हो गया है और अधिकारी द्वारा जाँचा "
                   "जाएगा। अभी आपसे और कुछ अपेक्षित नहीं है।",
        verified_at=_now(), fraud_signal=0)


def record_self_declaration(profile: dict) -> VerificationOutcome:
    """Format and checksum validation only — recorded as self-declared."""
    from dpdp import identity_documents
    ok, en, hi = identity_documents.validate_profile_identity(profile)
    return VerificationOutcome(
        method="self_declaration", succeeded=ok,
        assurance=Assurance.ASSERTED if ok else Assurance.NONE,
        established={}, score=1.0 if ok else 0.0, needs_review=True,
        message_en=("Your details were recorded as self-declared. They have not "
                    "been checked against any records yet."
                    if ok else en),
        message_hi=("आपका विवरण स्व-घोषित के रूप में दर्ज किया गया है। इसे अभी किसी "
                    "अभिलेख से नहीं मिलाया गया है।" if ok else hi),
        verified_at=_now(), fraud_signal=0)


# ── Aggregation ──────────────────────────────────────────────────────────

def profile_assurance(outcomes: list[VerificationOutcome]) -> Assurance:
    """The assurance a profile actually carries: the best *successful* check.

    Best rather than latest, so a citizen who verifies with UIDAI and later
    uploads a photo of a ration card is not demoted for supplying more evidence.
    """
    return max((o.assurance for o in outcomes if o.succeeded), default=Assurance.NONE)


def assurance_summary(outcomes: list[VerificationOutcome]) -> dict:
    """What to show the citizen about their own verification state."""
    level = profile_assurance(outcomes)
    contradicted = any(o.contradicted for o in outcomes)
    pending = [o.method for o in outcomes if o.needs_review]
    return {
        "assurance": int(level),
        "label": level.label_en,
        "labelHindi": level.label_hi,
        "methodsUsed": [o.method for o in outcomes if o.succeeded],
        "awaitingReview": pending,
        "contradiction": contradicted,
        # Never phrased as a refusal, and never phrased as an approval either.
        "nextStep": _next_step(level, contradicted),
        "nextStepHindi": _next_step_hi(level, contradicted),
    }


def _next_step(level: Assurance, contradicted: bool) -> str:
    if contradicted:
        return ("An officer is checking a difference between your documents. You "
                "do not need to do anything; you will be contacted if more is "
                "needed.")
    if level >= Assurance.VERIFIED:
        return "Your identity is verified. You can apply to any scheme you qualify for."
    if level >= Assurance.DOCUMENTED:
        return ("Your documents are with an officer. You can continue applying "
                "while they are checked.")
    if level >= Assurance.ASSERTED:
        return ("You can strengthen your application by verifying with an Aadhaar "
                "offline e-KYC file, a QR scan, or by visiting a service centre. "
                "None of these is compulsory.")
    return ("Add any one identity document to continue. Aadhaar is one option "
            "among several — a voter ID, ration card or job card also works.")


def _next_step_hi(level: Assurance, contradicted: bool) -> str:
    if contradicted:
        return ("अधिकारी आपके दस्तावेज़ों के बीच के अंतर की जाँच कर रहे हैं। आपको कुछ "
                "करने की आवश्यकता नहीं; आवश्यकता होने पर आपसे संपर्क किया जाएगा।")
    if level >= Assurance.VERIFIED:
        return "आपकी पहचान सत्यापित है। आप किसी भी पात्र योजना हेतु आवेदन कर सकते हैं।"
    if level >= Assurance.DOCUMENTED:
        return ("आपके दस्तावेज़ अधिकारी के पास हैं। जाँच के दौरान आप आवेदन जारी रख "
                "सकते हैं।")
    if level >= Assurance.ASSERTED:
        return ("आप आधार ऑफ़लाइन ई-केवाईसी फ़ाइल, क्यूआर स्कैन अथवा सेवा केंद्र पर "
                "जाकर अपना आवेदन और सुदृढ़ कर सकते हैं। इनमें से कोई भी अनिवार्य नहीं है।")
    return ("जारी रखने हेतु कोई एक पहचान दस्तावेज़ जोड़ें। आधार कई विकल्पों में से एक "
            "है — मतदाता पहचान पत्र, राशन कार्ड अथवा जॉब कार्ड भी चलेगा।")


def required_assurance_for(scheme: dict) -> Assurance:
    """The assurance a scheme's *disbursing department* would want.

    Advisory only. It is used to tell a citizen what will make their claim
    smoother, never to block a submission — deciding that someone may not even
    apply is a power this application does not have.
    """
    benefit = (scheme.get("eligibilityCriteria") or {}).get("benefit", "").lower()
    category = scheme.get("category", "")
    if any(w in benefit for w in ("loan", "credit", "subsidy on", "insurance")):
        return Assurance.SUBSTANTIAL
    if category in ("health",):
        return Assurance.VERIFIED
    return Assurance.DOCUMENTED


def gap_for_scheme(outcomes: list[VerificationOutcome], scheme: dict) -> dict:
    """What, if anything, would strengthen a claim on this scheme."""
    have = profile_assurance(outcomes)
    want = required_assurance_for(scheme)
    from kyc.methods import available_methods
    suggestions = [m.key for m in available_methods() if m.assurance > have]
    return {
        "have": int(have),
        "recommended": int(want),
        "sufficient": have >= want,
        # Always true. Stated explicitly so no caller invents a block.
        "canStillApply": True,
        "suggestedMethods": suggestions,
    }
