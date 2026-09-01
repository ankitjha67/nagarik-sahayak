"""Single gate every benefit application passes through before a form is issued.

Composes the three independent checks into one verdict:

  1. validation.py         — is the data objectively valid?
  2. eligibility_engine.py — does the applicant meet the scheme's stated rules?
  3. fraud_detection.py    — does this application look abusive?

Only (1) and (2) can stop an application, and both give the citizen a concrete,
translated reason. (3) never refuses on its own; it routes to a human. See the
design stance documented in fraud_detection.py for why.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field as dc_field
from enum import Enum

import fraud_detection
from eligibility_engine import Verdict, evaluate_scheme
from validation import validate_profile

logger = logging.getLogger(__name__)


class GateOutcome(str, Enum):
    APPROVED = "approved"                # issue the form
    APPROVED_WITH_REVIEW = "approved_with_review"  # issue, but flag for review
    BLOCKED_INVALID_DATA = "blocked_invalid_data"
    BLOCKED_NOT_ELIGIBLE = "blocked_not_eligible"
    INCOMPLETE = "incomplete"            # need more answers first


@dataclass
class GateResult:
    outcome: GateOutcome
    scheme: str
    validation: dict = dc_field(default_factory=dict)
    eligibility: dict = dc_field(default_factory=dict)
    risk: dict = dc_field(default_factory=dict)
    reasons_en: list[str] = dc_field(default_factory=list)
    reasons_hi: list[str] = dc_field(default_factory=list)

    @property
    def may_issue_form(self) -> bool:
        return self.outcome in (GateOutcome.APPROVED, GateOutcome.APPROVED_WITH_REVIEW)

    def as_dict(self) -> dict:
        return {
            "outcome": self.outcome.value,
            "scheme": self.scheme,
            "may_issue_form": self.may_issue_form,
            "requires_human_review": self.risk.get("requires_human_review", False),
            "reasons_en": self.reasons_en,
            "reasons_hi": self.reasons_hi,
            "validation": self.validation,
            "eligibility": self.eligibility,
            "risk": self.risk,
        }


async def evaluate_application(
    profile: dict,
    scheme: dict,
    user_id: str = "",
    history: fraud_detection.ApplicantHistory | None = None,
    check_fraud: bool = True,
) -> GateResult:
    """Run the full gate for one applicant against one scheme."""
    scheme_name = scheme.get("schemeName", "Unknown scheme")
    fields = scheme.get("extractedFields", []) or []

    # 1. Data validity — blocks only on objectively impossible values.
    v = validate_profile(profile, fields)
    validation = v.as_dict()

    # 2. Scheme eligibility — deterministic, explainable, per-rule.
    e = evaluate_scheme(profile, scheme)
    eligibility = e.as_dict()

    # 3. Fraud signals — advisory. Computed even when the application is
    #    blocked, so that repeated invalid attempts remain visible to reviewers.
    risk = {}
    if check_fraud:
        if history is None and user_id:
            history = await fraud_detection.build_history(user_id, profile, scheme_name)
        risk = fraud_detection.assess(profile, scheme, history).as_dict()

    reasons_en: list[str] = []
    reasons_hi: list[str] = []

    if v.has_invalid_values:
        # Something submitted is actually wrong — a failed checksum, an
        # impossible date. Report only those, not the fields still blank.
        outcome = GateOutcome.BLOCKED_INVALID_DATA
        for f in v.errors:
            if f.code == "required_missing":
                continue
            reasons_en.append(f.message_en)
            if f.message_hi:
                reasons_hi.append(f.message_hi)
    elif v.missing_required:
        # The form is merely unfinished. This is not a refusal, and must not be
        # phrased as one — the citizen is told what is still needed.
        outcome = GateOutcome.INCOMPLETE
        for f in v.missing_required:
            reasons_en.append(f.message_en)
            if f.message_hi:
                reasons_hi.append(f.message_hi)
    elif e.verdict == Verdict.NOT_ELIGIBLE:
        outcome = GateOutcome.BLOCKED_NOT_ELIGIBLE
        for r in e.failed:
            reasons_en.append(r.message_en)
            if r.message_hi:
                reasons_hi.append(r.message_hi)
    elif e.verdict == Verdict.INCOMPLETE:
        outcome = GateOutcome.INCOMPLETE
        missing = ", ".join(r.field for r in e.unknown)
        reasons_en.append(f"More information needed: {missing}.")
        reasons_hi.append(f"अधिक जानकारी आवश्यक: {missing}।")
    elif risk.get("requires_human_review"):
        outcome = GateOutcome.APPROVED_WITH_REVIEW
        reasons_en.append(
            "Your form has been generated and sent for verification before "
            "the benefit is released."
        )
        reasons_hi.append(
            "आपका फॉर्म तैयार हो गया है और लाभ जारी होने से पहले सत्यापन हेतु भेजा गया है।"
        )
    else:
        outcome = GateOutcome.APPROVED

    return GateResult(
        outcome=outcome, scheme=scheme_name,
        validation=validation, eligibility=eligibility, risk=risk,
        reasons_en=reasons_en, reasons_hi=reasons_hi,
    )


def audit_record(user_id: str, result: GateResult) -> dict:
    """Immutable-shaped record of a gate decision, for audit and appeal.

    A citizen refused a benefit is entitled to know why; a reviewer needs to see
    what the system saw at decision time. Identifiers are deliberately excluded
    — this is a decision log, not a copy of the applicant's personal data.
    """
    from datetime import datetime, timezone

    return {
        "user_id": user_id,
        "scheme": result.scheme,
        "outcome": result.outcome.value,
        "risk_score": result.risk.get("risk_score", 0),
        "signal_codes": [s["code"] for s in result.risk.get("signals", [])],
        "validation_error_codes": [
            f["code"] for f in result.validation.get("findings", [])
            if f["severity"] == "error"
        ],
        "failed_rule_fields": [
            r["field"] for r in result.eligibility.get("failed_rules", [])
        ],
        "decided_at": datetime.now(timezone.utc).isoformat(),
    }
