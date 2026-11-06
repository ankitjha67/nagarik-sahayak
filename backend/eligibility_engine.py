"""Deterministic eligibility evaluation against declared scheme rules.

The catalog (`data/gov_forms.py`) states each scheme's eligibility as structured
rules — `{"field": "age", "op": ">=", "value": 60}` — rather than prose. This
module evaluates a citizen's profile against them and returns a verdict with a
per-rule explanation.

Two properties matter more than cleverness here:

* **Explainable.** A citizen refused a benefit must be told exactly which
  condition failed and what value was read, in their own language. Opaque
  refusal is how entitlement systems lose legitimacy.
* **Conservative about missing data.** A field the applicant has not supplied
  yet is `UNKNOWN`, never a failure. Otherwise an incomplete form would look
  identical to an ineligible applicant, and people would be turned away for
  paperwork they simply had not reached.
"""
from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from datetime import date
from enum import Enum

from validation import compute_age, normalize_digits, parse_date


class RuleOutcome(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"     # applicant has not supplied the value yet


class Verdict(str, Enum):
    ELIGIBLE = "eligible"
    NOT_ELIGIBLE = "not_eligible"
    INCOMPLETE = "incomplete"   # cannot decide until more is supplied


@dataclass
class RuleResult:
    field: str
    op: str
    expected: object
    actual: object
    outcome: RuleOutcome
    message_en: str = ""
    message_hi: str = ""

    def as_dict(self) -> dict:
        return {
            "field": self.field, "op": self.op,
            "expected": self.expected, "actual": self.actual,
            "outcome": self.outcome.value,
            "message_en": self.message_en, "message_hi": self.message_hi,
        }


@dataclass
class EligibilityResult:
    scheme: str
    verdict: Verdict
    rules: list[RuleResult] = dc_field(default_factory=list)
    benefit: str = ""
    summary_en: str = ""
    summary_hi: str = ""

    @property
    def is_eligible(self) -> bool:
        return self.verdict == Verdict.ELIGIBLE

    @property
    def failed(self) -> list[RuleResult]:
        return [r for r in self.rules if r.outcome == RuleOutcome.FAIL]

    @property
    def unknown(self) -> list[RuleResult]:
        return [r for r in self.rules if r.outcome == RuleOutcome.UNKNOWN]

    def as_dict(self) -> dict:
        return {
            "scheme": self.scheme,
            "verdict": self.verdict.value,
            "eligible": self.is_eligible,
            "benefit": self.benefit,
            "summary_en": self.summary_en,
            "summary_hi": self.summary_hi,
            "failed_rules": [r.as_dict() for r in self.failed],
            "unknown_rules": [r.as_dict() for r in self.unknown],
            "rules": [r.as_dict() for r in self.rules],
        }


_NUMERIC_OPS = {">", ">=", "<", "<=" }


def _coerce_number(value):
    """Best-effort numeric read of a form value. None if not numeric."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    # Strip currency symbols, commas, and trailing units ("2.5 acres")
    cleaned = text.replace(",", "").replace("₹", "").strip()
    import re
    m = re.search(r"-?\d+(?:\.\d+)?", cleaned)
    return float(m.group()) if m else None


def _resolve(profile: dict, field: str):
    """Read a rule's field from the profile, deriving age from DOB if needed."""
    value = profile.get(field)
    if value not in (None, ""):
        return value
    # Age is routinely absent while date_of_birth is present; derive rather
    # than treating the applicant as having withheld it.
    if field == "age":
        dob = parse_date(profile.get("date_of_birth"))
        if dob:
            return compute_age(dob)
    if field == "girl_child_age":
        dob = parse_date(profile.get("girl_child_dob"))
        if dob:
            return compute_age(dob)
    return None


def evaluate_rule(profile: dict, rule: dict) -> RuleResult:
    field = rule.get("field", "")
    op = rule.get("op", "==")
    expected = rule.get("value")
    actual = _resolve(profile, field)

    if actual is None:
        return RuleResult(
            field, op, expected, None, RuleOutcome.UNKNOWN,
            message_en=f"'{field}' has not been provided yet.",
            message_hi=f"'{field}' अभी तक नहीं भरा गया है।",
        )

    if op in _NUMERIC_OPS:
        a, e = _coerce_number(actual), _coerce_number(expected)
        if a is None or e is None:
            return RuleResult(
                field, op, expected, actual, RuleOutcome.UNKNOWN,
                message_en=f"'{field}' could not be read as a number.",
                message_hi=f"'{field}' संख्या के रूप में नहीं पढ़ा जा सका।",
            )
        ok = {">": a > e, ">=": a >= e, "<": a < e, "<=": a <= e}[op]
        human = {">": "greater than", ">=": "at least",
                 "<": "less than", "<=": "at most"}[op]
        return RuleResult(
            field, op, expected, actual,
            RuleOutcome.PASS if ok else RuleOutcome.FAIL,
            message_en=("" if ok else
                        f"{field.replace('_', ' ')} must be {human} {expected} "
                        f"(you entered {actual})."),
            message_hi=("" if ok else
                        f"{field.replace('_', ' ')} {expected} होना चाहिए "
                        f"(आपने {actual} दर्ज किया)।"),
        )

    # Equality/inequality — compare case-insensitively as text so "yes"/"Yes"
    # and 60/"60" behave the way a form-filler expects.
    a_txt, e_txt = str(actual).strip().lower(), str(expected).strip().lower()
    ok = (a_txt == e_txt) if op == "==" else (a_txt != e_txt)
    return RuleResult(
        field, op, expected, actual,
        RuleOutcome.PASS if ok else RuleOutcome.FAIL,
        message_en=("" if ok else
                    f"{field.replace('_', ' ')} must be '{expected}' "
                    f"(you entered '{actual}')."),
        message_hi=("" if ok else
                    f"{field.replace('_', ' ')} '{expected}' होना चाहिए "
                    f"(आपने '{actual}' दर्ज किया)।"),
    )


def evaluate_scheme(profile: dict, scheme: dict) -> EligibilityResult:
    """Evaluate one catalog scheme against a profile."""
    criteria = scheme.get("eligibilityCriteria", {}) or {}
    rules = criteria.get("rules", []) or []
    name = scheme.get("schemeName", "Unknown scheme")

    results = [evaluate_rule(profile, r) for r in rules]

    if any(r.outcome == RuleOutcome.FAIL for r in results):
        verdict = Verdict.NOT_ELIGIBLE
    elif any(r.outcome == RuleOutcome.UNKNOWN for r in results):
        verdict = Verdict.INCOMPLETE
    else:
        verdict = Verdict.ELIGIBLE

    if verdict == Verdict.ELIGIBLE:
        summary_en = f"You meet the stated conditions for {name}."
        summary_hi = f"आप {name} की शर्तें पूरी करते हैं।"
    elif verdict == Verdict.NOT_ELIGIBLE:
        reasons = "; ".join(r.message_en for r in results
                            if r.outcome == RuleOutcome.FAIL and r.message_en)
        summary_en = f"Not eligible for {name}. {reasons}"
        summary_hi = "; ".join(r.message_hi for r in results
                               if r.outcome == RuleOutcome.FAIL and r.message_hi)
    else:
        missing = ", ".join(r.field for r in results
                            if r.outcome == RuleOutcome.UNKNOWN)
        summary_en = f"Eligibility for {name} needs: {missing}."
        summary_hi = f"{name} हेतु पात्रता जाँचने के लिए चाहिए: {missing}।"

    return EligibilityResult(
        scheme=name, verdict=verdict, rules=results,
        benefit=criteria.get("benefit", ""),
        summary_en=summary_en, summary_hi=summary_hi,
    )


def evaluate_all(profile: dict, schemes: list[dict] | None = None) -> list[EligibilityResult]:
    """Evaluate a profile against every catalog scheme (or a supplied subset)."""
    if schemes is None:
        from data.gov_forms import get_catalog
        schemes = get_catalog()
    return [evaluate_scheme(profile, s) for s in schemes]
