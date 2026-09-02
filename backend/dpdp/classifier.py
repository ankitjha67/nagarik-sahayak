"""Personal data detection and redaction.

The detection core of the DPDP engine. Everything else — the leak scanner, the
analytics redactor, the response middleware — asks this module one question:
*does this value or text contain personal data, and of what kind?*

Precision matters more than recall here, and the reason is specific. A detector
that flags every 12-digit number as an Aadhaar produces so many false positives
on bank accounts, reference numbers and timestamps that engineers stop reading
its output, at which point it protects nobody. So the Aadhaar detector verifies
the Verhoeff checksum that UIDAI actually issues against, which rejects almost
every incidental 12-digit string while keeping every real Aadhaar.

Categories follow the DPDP Act's own framing: it does not define "sensitive
personal data" as a separate tier the way GDPR does, but it does treat some
processing — children's data (s9), and anything used to decide a person's
entitlement (s8(3)) — as carrying heightened duty. `Sensitivity` encodes that.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field as dc_field
from enum import Enum

from validation import verhoeff_is_valid


class PIICategory(str, Enum):
    AADHAAR = "aadhaar"
    PAN = "pan"
    BANK_ACCOUNT = "bank_account"
    IFSC = "ifsc"
    MOBILE = "mobile"
    EMAIL = "email"
    RATION_CARD = "ration_card"
    VOTER_ID = "voter_id"
    PASSPORT = "passport"
    DATE_OF_BIRTH = "date_of_birth"
    NAME = "name"
    ADDRESS = "address"
    FINANCIAL = "financial"          # income, land holding
    CASTE_CATEGORY = "caste_category"
    CHILD_DATA = "child_data"        # s9 — heightened duty
    HEALTH = "health"
    BIOMETRIC = "biometric"


class Sensitivity(str, Enum):
    """How much harm disclosure would do, which sets handling duty."""
    CRITICAL = "critical"   # Aadhaar, bank, biometric — enables impersonation or theft
    HIGH = "high"           # caste, health, child data, income
    MODERATE = "moderate"   # name, address, contact
    LOW = "low"             # language preference, district


@dataclass
class Detection:
    category: PIICategory
    sensitivity: Sensitivity
    value_preview: str      # redacted; never the raw value
    location: str = ""      # field name, JSON path, or file:line
    confidence: float = 1.0

    def as_dict(self) -> dict:
        return {
            "category": self.category.value,
            "sensitivity": self.sensitivity.value,
            "value_preview": self.value_preview,
            "location": self.location,
            "confidence": self.confidence,
        }


SENSITIVITY_OF = {
    PIICategory.AADHAAR: Sensitivity.CRITICAL,
    PIICategory.BANK_ACCOUNT: Sensitivity.CRITICAL,
    PIICategory.BIOMETRIC: Sensitivity.CRITICAL,
    PIICategory.PAN: Sensitivity.CRITICAL,
    PIICategory.PASSPORT: Sensitivity.CRITICAL,
    PIICategory.CHILD_DATA: Sensitivity.HIGH,
    PIICategory.CASTE_CATEGORY: Sensitivity.HIGH,
    PIICategory.HEALTH: Sensitivity.HIGH,
    PIICategory.FINANCIAL: Sensitivity.HIGH,
    PIICategory.VOTER_ID: Sensitivity.HIGH,
    PIICategory.RATION_CARD: Sensitivity.HIGH,
    PIICategory.IFSC: Sensitivity.MODERATE,
    PIICategory.MOBILE: Sensitivity.MODERATE,
    PIICategory.EMAIL: Sensitivity.MODERATE,
    PIICategory.DATE_OF_BIRTH: Sensitivity.MODERATE,
    PIICategory.NAME: Sensitivity.MODERATE,
    PIICategory.ADDRESS: Sensitivity.MODERATE,
}


# ── Value patterns ────────────────────────────────────────────────────────
# Each is deliberately anchored on word boundaries. Loose patterns are the
# reason PII scanners get switched off.

_AADHAAR_RE = re.compile(r"\b[2-9]\d{3}[\s-]?\d{4}[\s-]?\d{4}\b")
_PAN_RE = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
_IFSC_RE = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")
_MOBILE_RE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)")
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_VOTER_RE = re.compile(r"\b[A-Z]{3}\d{7}\b")
_PASSPORT_RE = re.compile(r"\b[A-Z]\d{7}\b")
# Bank accounts have no checksum and vary 9–18 digits, so this only fires with a
# nearby cue word. Without that it would match almost any long number.
_BANK_CUE_RE = re.compile(
    r"(?:a/?c|account|khata|खाता)\D{0,20}(\d{9,18})", re.IGNORECASE)


def _redact(value: str, keep: int = 4) -> str:
    """Preview that proves a match without reproducing the identifier."""
    text = str(value)
    if len(text) <= keep:
        return "*" * len(text)
    return "*" * (len(text) - keep) + text[-keep:]


def detect_in_text(text: str, location: str = "") -> list[Detection]:
    """Find personal data inside free text — a log line, an LLM prompt, a note."""
    if not text:
        return []
    found: list[Detection] = []
    seen: set[tuple] = set()

    def add(category, raw, confidence=1.0):
        key = (category, str(raw))
        if key in seen:
            return
        seen.add(key)
        found.append(Detection(
            category=category,
            sensitivity=SENSITIVITY_OF.get(category, Sensitivity.MODERATE),
            value_preview=_redact(raw), location=location, confidence=confidence,
        ))

    for m in _AADHAAR_RE.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        # The checksum is what separates a real Aadhaar from any 12 digits.
        if len(digits) == 12 and verhoeff_is_valid(digits):
            add(PIICategory.AADHAAR, digits)
    for m in _PAN_RE.finditer(text):
        add(PIICategory.PAN, m.group())
    for m in _IFSC_RE.finditer(text):
        add(PIICategory.IFSC, m.group())
    for m in _MOBILE_RE.finditer(text):
        add(PIICategory.MOBILE, re.sub(r"\D", "", m.group())[-10:])
    for m in _EMAIL_RE.finditer(text):
        add(PIICategory.EMAIL, m.group())
    for m in _BANK_CUE_RE.finditer(text):
        add(PIICategory.BANK_ACCOUNT, m.group(1), confidence=0.8)
    for m in _VOTER_RE.finditer(text):
        add(PIICategory.VOTER_ID, m.group(), confidence=0.7)
    for m in _PASSPORT_RE.finditer(text):
        add(PIICategory.PASSPORT, m.group(), confidence=0.6)

    return found


def detect_in_object(obj, path: str = "$") -> list[Detection]:
    """Walk a dict/list structure, classifying by field name *and* by value.

    Field names are the stronger signal — `annual_income` is financial data
    whatever it contains — so both are used and the field-name rule wins.
    """
    from dpdp.registry import category_for_field

    found: list[Detection] = []

    if isinstance(obj, dict):
        for key, value in obj.items():
            child = f"{path}.{key}"
            category = category_for_field(str(key))
            if category and value not in (None, ""):
                found.append(Detection(
                    category=category,
                    sensitivity=SENSITIVITY_OF.get(category, Sensitivity.MODERATE),
                    value_preview=_redact(value), location=child,
                ))
                # A recognised field needs no value-pattern scan; it is already
                # classified, and scanning again would double-report it.
                continue
            found.extend(detect_in_object(value, child))
    elif isinstance(obj, (list, tuple)):
        for i, item in enumerate(obj):
            found.extend(detect_in_object(item, f"{path}[{i}]"))
    elif isinstance(obj, str):
        found.extend(detect_in_text(obj, path))

    return found


def redact_text(text: str) -> str:
    """Replace personal data in free text with category placeholders.

    Used before anything reaches a log, an external analytics call, or an LLM
    prompt. Structure is preserved so the message stays diagnostically useful.
    """
    if not text:
        return text
    out = text

    def sub_aadhaar(m):
        digits = re.sub(r"\D", "", m.group())
        if len(digits) == 12 and verhoeff_is_valid(digits):
            return "[AADHAAR_REDACTED]"
        return m.group()

    out = _AADHAAR_RE.sub(sub_aadhaar, out)
    out = _PAN_RE.sub("[PAN_REDACTED]", out)
    out = _IFSC_RE.sub("[IFSC_REDACTED]", out)
    out = _EMAIL_RE.sub("[EMAIL_REDACTED]", out)
    out = _MOBILE_RE.sub("[MOBILE_REDACTED]", out)
    out = _BANK_CUE_RE.sub(lambda m: m.group().replace(m.group(1), "[ACCOUNT_REDACTED]"), out)
    return out


def redact_object(obj, _depth: int = 0):
    """Deep-copy a structure with every personal-data field redacted.

    The safe form to log, to send to analytics, or to attach to an error report.
    """
    if _depth > 12:               # guard against pathological nesting
        return "[TRUNCATED]"
    from dpdp.registry import category_for_field

    if isinstance(obj, dict):
        out = {}
        for key, value in obj.items():
            category = category_for_field(str(key))
            if category and value not in (None, ""):
                out[key] = f"[{category.value.upper()}_REDACTED]"
            else:
                out[key] = redact_object(value, _depth + 1)
        return out
    if isinstance(obj, list):
        return [redact_object(v, _depth + 1) for v in obj]
    if isinstance(obj, tuple):
        return tuple(redact_object(v, _depth + 1) for v in obj)
    if isinstance(obj, str):
        return redact_text(obj)
    return obj


def highest_sensitivity(detections: list[Detection]) -> Sensitivity | None:
    """The worst sensitivity present, for prioritising findings."""
    if not detections:
        return None
    order = [Sensitivity.CRITICAL, Sensitivity.HIGH,
             Sensitivity.MODERATE, Sensitivity.LOW]
    for level in order:
        if any(d.sensitivity == level for d in detections):
            return level
    return None
