"""The DPDP compliance engine — checks rows, code and payloads against the Act.

Three surfaces, one finding model:

  check_row()      every stored personal-data row, against the registry
  scan_source()    the codebase, for paths that leak personal data
  scan_payload()   an outbound response or third-party call, at runtime

Findings carry the section they derive from, because "this is non-compliant" is
not actionable while "section 8(6) requires erasure once the purpose is served,
and this row is 400 days past its retention" is. Severity is about consequence
to the citizen, not tidiness: an unprotected Aadhaar is CRITICAL, an inventory
gap is a WARNING.

Deliberately conservative in one direction: the engine reports, it never
deletes or mutates. Erasure is a separate, explicit operation (see retention.py)
because an over-eager compliance job that silently destroys a citizen's
in-progress application would cause more harm than the gap it closed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field as dc_field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path

from dpdp import registry
from dpdp.classifier import (
    Detection, PIICategory, Sensitivity, detect_in_object, detect_in_text,
)


class Severity(str, Enum):
    CRITICAL = "critical"   # personal data is exposed, or exposable now
    HIGH = "high"           # a mandatory obligation is unmet
    WARNING = "warning"     # a gap that needs a decision
    INFO = "info"


@dataclass
class Finding:
    severity: Severity
    code: str
    section: str            # DPDP Act section this derives from
    title: str
    detail: str
    location: str = ""
    remediation: str = ""

    def as_dict(self) -> dict:
        return {
            "severity": self.severity.value, "code": self.code,
            "section": self.section, "title": self.title, "detail": self.detail,
            "location": self.location, "remediation": self.remediation,
        }


@dataclass
class Report:
    findings: list[Finding] = dc_field(default_factory=list)
    checked: int = 0
    scope: str = ""

    def add(self, *args, **kwargs):
        self.findings.append(Finding(*args, **kwargs))

    def of(self, severity: Severity) -> list[Finding]:
        return [f for f in self.findings if f.severity == severity]

    @property
    def compliant(self) -> bool:
        """Compliant means nothing CRITICAL or HIGH is outstanding."""
        return not (self.of(Severity.CRITICAL) or self.of(Severity.HIGH))

    def as_dict(self) -> dict:
        return {
            "scope": self.scope,
            "compliant": self.compliant,
            "checked": self.checked,
            "counts": {s.value: len(self.of(s)) for s in Severity},
            "findings": [f.as_dict() for f in self.findings],
        }


# ══════════════════════════════════════════════════════════════════════
# 1. Row-level: every stored personal-data row against the registry
# ══════════════════════════════════════════════════════════════════════

def check_row(
    profile: dict,
    *,
    row_id: str = "",
    created_at: datetime | None = None,
    consented_purposes: set[str] | None = None,
    has_parental_consent: bool = False,
) -> Report:
    """Check one citizen's stored data for DPDP compliance.

    `consented_purposes` is the set of purposes the citizen actually agreed to.
    Passing None means "no consent record exists", which is itself the finding —
    silently assuming consent is exactly the failure mode the Act targets.
    """
    report = Report(scope=f"row:{row_id or 'anonymous'}")
    profile = profile or {}
    report.checked = len(profile)

    # s6(1) — data must serve a declared purpose.
    for key in registry.undeclared_fields(profile):
        report.add(
            Severity.WARNING, "undeclared_field", "s6(1)",
            "Field processed outside any declared purpose",
            f"'{key}' is stored but appears in no registry entry, so no notice "
            f"describes it and no purpose justifies it.",
            location=f"profile.{key}",
            remediation="Declare it in dpdp/registry.py with a purpose and "
                        "retention, or stop collecting it.",
        )

    present = [k for k, v in profile.items() if v not in (None, "")]

    # s4/s6 — a lawful basis is required for each purpose being served.
    consent_required_purposes: set[str] = set()
    for key in present:
        rec = registry.record_for(key)
        if rec and rec.basis == registry.LawfulBasis.CONSENT:
            consent_required_purposes.update(p.value for p in rec.purposes)

    if consent_required_purposes:
        if consented_purposes is None:
            report.add(
                Severity.HIGH, "no_consent_record", "s6(1)",
                "Personal data held with no consent record",
                f"{len(consent_required_purposes)} purpose(s) require consent "
                f"but no consent record exists for this data principal.",
                location=f"row:{row_id}",
                remediation="Capture consent via POST /api/dpdp/consent before "
                            "further processing, or stop processing.",
            )
        else:
            missing = sorted(consent_required_purposes - consented_purposes)
            if missing:
                report.add(
                    Severity.HIGH, "purpose_without_consent", "s6(1)",
                    "Processing for a purpose the citizen did not consent to",
                    f"Data is held for {', '.join(missing)}, which this citizen "
                    f"has not agreed to.",
                    location=f"row:{row_id}",
                    remediation="Obtain consent for these purposes or erase the "
                                "fields that serve only them.",
                )

    # s9 — children's data needs verifiable parental consent.
    child_present = [k for k in present
                     if (r := registry.record_for(k)) and r.child_data]
    if child_present and not has_parental_consent:
        report.add(
            Severity.HIGH, "child_data_without_parental_consent", "s9(1)",
            "Child's data held without verifiable parental consent",
            f"Fields {', '.join(child_present)} concern a child. Section 9 "
            f"requires verifiable consent of a parent or lawful guardian.",
            location=f"row:{row_id}",
            remediation="Record guardian consent before processing, and never "
                        "use this data for tracking or behavioural advertising.",
        )

    # s8(3) — data used to decide an entitlement must be accurate and complete.
    for key in present:
        rec = registry.record_for(key)
        if not rec or not rec.decisional:
            continue
        value = profile[key]
        if isinstance(value, str) and value.strip().lower() in {
            "na", "n/a", "none", "null", "unknown", "-", "tbd", "test",
        }:
            report.add(
                Severity.HIGH, "decisional_field_placeholder", "s8(3)",
                "Placeholder value in a field that decides an entitlement",
                f"'{key}' holds {value!r}. Section 8(3) requires data used to "
                f"decide a matter affecting the data principal to be accurate "
                f"and complete.",
                location=f"profile.{key}",
                remediation="Re-collect this value before any decision is made "
                            "on it.",
            )

    # s8(6) — erase once the purpose is served.
    if created_at:
        now = datetime.now(timezone.utc)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        age_days = (now - created_at).days
        overdue = []
        for key in present:
            rec = registry.record_for(key)
            if rec and age_days > rec.retention_days:
                overdue.append((key, age_days - rec.retention_days))
        if overdue:
            worst = max(d for _, d in overdue)
            report.add(
                Severity.HIGH, "retention_exceeded", "s8(6)",
                "Personal data held beyond its retention period",
                f"{len(overdue)} field(s) are past retention, the oldest by "
                f"{worst} days.",
                location=f"row:{row_id}",
                remediation="Run scripts/dpdp_erase.py, or erase via "
                            "POST /api/dpdp/erase.",
            )

    return report


# ══════════════════════════════════════════════════════════════════════
# 2. Source-level: code paths that leak personal data
# ══════════════════════════════════════════════════════════════════════

# Logging a whole profile/message object is the most common way PII reaches a
# log aggregator, where it is retained far longer and read by more people than
# the database ever is.
#
# The value must be *interpolated or passed*, not merely named in the message
# text: logger.error(f"Profile reset failed: {e}") logs an exception, not a
# profile. Matching on the word alone produced exactly that false positive, and
# a scanner that cries wolf gets switched off — which protects nobody.
_PII_VARS = r"profile|full_profile|filled_fields|msg_dict|profile_data|fields"
_LOG_LEAK_RE = re.compile(
    r"log(?:ger)?\.(?:debug|info|warning|error|critical|exception)\s*\("
    r"(?:"
    r"[^)]*\{[^{}]*\b(?:" + _PII_VARS + r")\b[^{}]*\}"   # f-string interpolation
    r"|[^)]*,\s*(?:" + _PII_VARS + r")\b"                 # %-style argument
    r")",
)

# Sending raw objects to a third-party analytics service is a disclosure under
# s6 and, if the service is offshore, a transfer under s16.
_ANALYTICS_LEAK_RE = re.compile(
    r"agnost\.track\s*\([^)]*\b(?:input|output|properties)\s*=\s*"
    r"(?:str\()?\s*(profile|full_profile|content|filled_fields|answer)\b",
    re.IGNORECASE,
)

_PRINT_LEAK_RE = re.compile(r"\bprint\s*\([^)]*\b(profile|aadhaar|full_profile)\b",
                            re.IGNORECASE)


def scan_source(root: str | Path, skip: tuple[str, ...] = ("tests", "scripts", "dpdp")) -> Report:
    """Scan Python source for code paths that would disclose personal data."""
    report = Report(scope=f"source:{root}")
    root = Path(root)

    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root)
        if any(part in skip for part in rel.parts):
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        report.checked += 1

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            where = f"{rel}:{i}"

            if _ANALYTICS_LEAK_RE.search(line):
                report.add(
                    Severity.CRITICAL, "pii_to_third_party", "s6(1), s16",
                    "Personal data sent to a third-party service",
                    "A raw profile or message object is passed to analytics. "
                    "This discloses personal data to another party, and if that "
                    "party is outside India it is also a cross-border transfer.",
                    location=where,
                    remediation="Wrap the value in dpdp.classifier.redact_object() "
                                "or send only non-identifying counts.",
                )
            if _LOG_LEAK_RE.search(line):
                report.add(
                    Severity.HIGH, "pii_in_logs", "s8(4)",
                    "Personal data written to logs",
                    "Logs are retained longer and read more widely than the "
                    "database, so this widens exposure well beyond the purpose.",
                    location=where,
                    remediation="Log an identifier or a redacted object, never "
                                "the profile itself.",
                )
            if _PRINT_LEAK_RE.search(line):
                report.add(
                    Severity.WARNING, "pii_in_stdout", "s8(4)",
                    "Personal data printed to stdout",
                    "Captured by process supervisors and container logs.",
                    location=where,
                    remediation="Remove, or redact before printing.",
                )

    return report


# ══════════════════════════════════════════════════════════════════════
# 3. Payload-level: what is about to leave the process
# ══════════════════════════════════════════════════════════════════════

def scan_payload(payload, *, destination: str = "response",
                 allow: frozenset[PIICategory] = frozenset()) -> Report:
    """Detect personal data in an outbound payload.

    `allow` names categories legitimately present — a citizen reading their own
    profile must of course receive it. Anything outside that set leaving the
    process is unintended.
    """
    report = Report(scope=f"payload:{destination}")
    detections = (detect_in_object(payload) if not isinstance(payload, str)
                  else detect_in_text(payload))
    report.checked = len(detections)

    for d in detections:
        if d.category in allow:
            continue
        critical = d.sensitivity in (Sensitivity.CRITICAL, Sensitivity.HIGH)
        report.add(
            Severity.CRITICAL if critical else Severity.WARNING,
            "pii_in_outbound_payload", "s8(4)",
            f"{d.category.value} present in an outbound {destination}",
            f"Detected at {d.location} (value ends {d.value_preview[-4:]}).",
            location=d.location,
            remediation="Redact before sending, or add the category to the "
                        "endpoint's allow-list if disclosure is intended.",
        )
    return report


def merge(*reports: Report) -> Report:
    """Combine reports into one, worst-first."""
    out = Report(scope="combined")
    order = {Severity.CRITICAL: 0, Severity.HIGH: 1,
             Severity.WARNING: 2, Severity.INFO: 3}
    for r in reports:
        out.findings.extend(r.findings)
        out.checked += r.checked
    out.findings.sort(key=lambda f: order.get(f.severity, 9))
    return out
