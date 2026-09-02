"""Field-level validation for government benefit applications.

Design principle that governs every rule in this file: **this is a benefits
system, so a false positive denies a poor citizen money they are entitled to.**
That is a worse outcome than letting a questionable application through to a
human reviewer. Therefore:

* `ERROR` is reserved for data that is *objectively* impossible — a number that
  fails its own checksum, a birth date in the future. These block submission
  because no legitimate applicant can produce them.
* `WARNING` marks data that is merely unusual. It never blocks; it routes the
  application to manual review.

Every finding carries a bilingual message so the citizen is told plainly what to
fix, rather than being silently rejected.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field as dc_field
from datetime import date, datetime
from enum import Enum


class Severity(str, Enum):
    ERROR = "error"      # Objectively invalid — blocks submission
    WARNING = "warning"  # Suspicious but possible — routes to review
    INFO = "info"        # Advisory only


@dataclass
class Finding:
    severity: Severity
    code: str
    field: str
    message_en: str
    message_hi: str = ""

    def as_dict(self) -> dict:
        return {
            "severity": self.severity.value,
            "code": self.code,
            "field": self.field,
            "message_en": self.message_en,
            "message_hi": self.message_hi,
        }


@dataclass
class ValidationResult:
    findings: list[Finding] = dc_field(default_factory=list)

    def add(self, severity, code, field_name, en, hi=""):
        self.findings.append(Finding(severity, code, field_name, en, hi))

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == Severity.ERROR]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == Severity.WARNING]

    @property
    def is_blocking(self) -> bool:
        return bool(self.errors)

    @property
    def missing_required(self) -> list[Finding]:
        """Errors that are only 'you have not finished the form yet'."""
        return [f for f in self.errors if f.code == "required_missing"]

    @property
    def has_invalid_values(self) -> bool:
        """True when something submitted is actually wrong, as opposed to absent.

        Callers must distinguish these: telling a citizen their data is invalid
        when they have simply not reached the end of the form is both wrong and
        discouraging.
        """
        return any(f.code != "required_missing" for f in self.errors)

    def as_dict(self) -> dict:
        return {
            "valid": not self.is_blocking,
            "blocking": self.is_blocking,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "findings": [f.as_dict() for f in self.findings],
        }


# ══════════════════════════════════════════════════════════════════════
# Aadhaar — Verhoeff checksum
# ══════════════════════════════════════════════════════════════════════
# UIDAI generates Aadhaar numbers with a Verhoeff check digit. Validating it
# rejects typos and casually invented numbers ("123456789012") outright, which
# is the single highest-value identity check available offline.

_VERHOEFF_D = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9), (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6), (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8), (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2), (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4), (9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)
_VERHOEFF_P = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9), (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2), (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0), (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5), (7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
)
_VERHOEFF_INV = (0, 4, 3, 2, 1, 5, 6, 7, 8, 9)


def verhoeff_is_valid(number: str) -> bool:
    """True if `number` (digits only) carries a valid Verhoeff check digit."""
    if not number or not number.isdigit():
        return False
    c = 0
    for i, ch in enumerate(reversed(number)):
        c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][int(ch)]]
    return c == 0


def verhoeff_check_digit(payload: str) -> str:
    """Compute the Verhoeff check digit for an 11-digit payload.

    Exposed so tests can build synthetic-but-valid Aadhaar numbers instead of
    hardcoding real ones, which must never appear in a source repository.
    """
    if not payload or not payload.isdigit():
        raise ValueError("payload must be digits")
    c = 0
    for i, ch in enumerate(reversed(payload)):
        c = _VERHOEFF_D[c][_VERHOEFF_P[(i + 1) % 8][int(ch)]]
    return str(_VERHOEFF_INV[c])


def normalize_digits(value) -> str:
    """Strip spaces, hyphens and other separators from a numeric identifier."""
    return re.sub(r"\D", "", str(value or ""))


def _is_repeated_or_sequential(digits: str) -> bool:
    """Detect placeholder-looking numbers: 111111111111, 123456789012."""
    if len(set(digits)) == 1:
        return True
    ascending = "".join(str((int(digits[0]) + i) % 10) for i in range(len(digits)))
    descending = "".join(str((int(digits[0]) - i) % 10) for i in range(len(digits)))
    return digits in (ascending, descending)


def validate_aadhaar(value, field_name="aadhaar_number") -> ValidationResult:
    r = ValidationResult()
    digits = normalize_digits(value)

    if not digits:
        r.add(Severity.ERROR, "aadhaar_missing", field_name,
              "Aadhaar number is required.", "आधार संख्या आवश्यक है।")
        return r
    if len(digits) != 12:
        r.add(Severity.ERROR, "aadhaar_length", field_name,
              f"Aadhaar must be exactly 12 digits (got {len(digits)}).",
              f"आधार संख्या ठीक 12 अंकों की होनी चाहिए ({len(digits)} अंक मिले)।")
        return r
    # UIDAI never issues numbers beginning with 0 or 1.
    if digits[0] in "01":
        r.add(Severity.ERROR, "aadhaar_prefix", field_name,
              "Aadhaar numbers never begin with 0 or 1.",
              "आधार संख्या कभी 0 या 1 से शुरू नहीं होती।")
        return r
    if _is_repeated_or_sequential(digits):
        r.add(Severity.ERROR, "aadhaar_placeholder", field_name,
              "This looks like a placeholder, not a real Aadhaar number.",
              "यह वास्तविक आधार संख्या नहीं लगती।")
        return r
    if not verhoeff_is_valid(digits):
        r.add(Severity.ERROR, "aadhaar_checksum", field_name,
              "Aadhaar number failed its checksum — please re-check the digits.",
              "आधार संख्या सत्यापन में विफल — कृपया अंक दोबारा जाँचें।")
    return r


def validate_mobile(value, field_name="mobile_number") -> ValidationResult:
    r = ValidationResult()
    digits = normalize_digits(value)
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]          # tolerate +91 prefix
    if not digits:
        r.add(Severity.ERROR, "mobile_missing", field_name,
              "Mobile number is required.", "मोबाइल नंबर आवश्यक है।")
        return r
    if len(digits) != 10:
        r.add(Severity.ERROR, "mobile_length", field_name,
              f"Mobile number must be 10 digits (got {len(digits)}).",
              f"मोबाइल नंबर 10 अंकों का होना चाहिए ({len(digits)} अंक मिले)।")
        return r
    if digits[0] not in "6789":
        r.add(Severity.ERROR, "mobile_prefix", field_name,
              "Indian mobile numbers start with 6, 7, 8 or 9.",
              "भारतीय मोबाइल नंबर 6, 7, 8 या 9 से शुरू होते हैं।")
        return r
    if _is_repeated_or_sequential(digits):
        r.add(Severity.WARNING, "mobile_placeholder", field_name,
              "This mobile number looks artificial; it may not be reachable.",
              "यह मोबाइल नंबर कृत्रिम लगता है।")
    return r


def validate_ifsc(value, field_name="ifsc_code") -> ValidationResult:
    r = ValidationResult()
    code = str(value or "").strip().upper()
    if not code:
        r.add(Severity.ERROR, "ifsc_missing", field_name,
              "IFSC code is required to receive payment.",
              "भुगतान प्राप्त करने हेतु आईएफएससी कोड आवश्यक है।")
        return r
    # RBI format: 4-letter bank code, a reserved '0', then a 6-char branch code.
    if not re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", code):
        r.add(Severity.ERROR, "ifsc_format", field_name,
              "IFSC must be 4 letters, then 0, then 6 characters (e.g. SBIN0001234).",
              "आईएफएससी प्रारूप: 4 अक्षर, फिर 0, फिर 6 अक्षर (जैसे SBIN0001234)।")
    return r


def validate_bank_account(value, field_name="bank_account_number") -> ValidationResult:
    r = ValidationResult()
    digits = normalize_digits(value)
    if not digits:
        r.add(Severity.ERROR, "account_missing", field_name,
              "Bank account number is required.", "बैंक खाता संख्या आवश्यक है।")
        return r
    if not (9 <= len(digits) <= 18):
        r.add(Severity.ERROR, "account_length", field_name,
              f"Bank account numbers are 9–18 digits (got {len(digits)}).",
              f"बैंक खाता संख्या 9–18 अंकों की होती है ({len(digits)} अंक मिले)।")
        return r
    if len(set(digits)) == 1:
        r.add(Severity.WARNING, "account_placeholder", field_name,
              "This account number looks artificial.",
              "यह खाता संख्या कृत्रिम लगती है।")
    return r


def validate_pincode(value, field_name="pincode") -> ValidationResult:
    r = ValidationResult()
    digits = normalize_digits(value)
    if not digits:
        return r  # optional on many forms
    if len(digits) != 6 or digits[0] == "0":
        r.add(Severity.ERROR, "pincode_format", field_name,
              "PIN code must be 6 digits and cannot start with 0.",
              "पिन कोड 6 अंकों का होना चाहिए और 0 से शुरू नहीं हो सकता।")
    return r


def validate_pan(value, field_name="pan_number") -> ValidationResult:
    r = ValidationResult()
    pan = str(value or "").strip().upper()
    if not pan:
        return r
    if not re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", pan):
        r.add(Severity.ERROR, "pan_format", field_name,
              "PAN must be 5 letters, 4 digits, then 1 letter (e.g. ABCDE1234F).",
              "पैन प्रारूप: 5 अक्षर, 4 अंक, 1 अक्षर (जैसे ABCDE1234F)।")
    return r


DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d")


def parse_date(value) -> date | None:
    """Parse the date formats Indian forms actually use. None if unparseable."""
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    return None


def validate_date_of_birth(value, field_name="date_of_birth") -> ValidationResult:
    r = ValidationResult()
    if value in (None, ""):
        return r
    parsed = parse_date(value)
    if parsed is None:
        r.add(Severity.ERROR, "dob_unparseable", field_name,
              "Date of birth is not a valid date.",
              "जन्म तिथि वैध नहीं है।")
        return r

    today = date.today()
    if parsed > today:
        r.add(Severity.ERROR, "dob_future", field_name,
              "Date of birth cannot be in the future.",
              "जन्म तिथि भविष्य में नहीं हो सकती।")
        return r
    age = compute_age(parsed, today)
    if age > 120:
        r.add(Severity.ERROR, "dob_implausible", field_name,
              f"Date of birth implies an age of {age} years.",
              f"जन्म तिथि से आयु {age} वर्ष निकलती है, जो असंभव है।")
    return r


def compute_age(born: date, on: date | None = None) -> int:
    """Age in completed years."""
    on = on or date.today()
    return on.year - born.year - ((on.month, on.day) < (born.month, born.day))


def validate_income(value, field_name="annual_income") -> ValidationResult:
    r = ValidationResult()
    if value in (None, ""):
        return r
    # normalize_digits() must not be used here: it strips the minus sign and the
    # decimal point, which would silently turn -500 into 500 and let a negative
    # income declaration pass.
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        amount = float(value)
    else:
        text = str(value).strip().replace(",", "").replace("₹", "")
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        if not match:
            r.add(Severity.ERROR, "income_unparseable", field_name,
                  "Annual income must be a number.", "वार्षिक आय संख्या होनी चाहिए।")
            return r
        amount = float(match.group())
    if amount < 0:
        r.add(Severity.ERROR, "income_negative", field_name,
              "Annual income cannot be negative.", "वार्षिक आय ऋणात्मक नहीं हो सकती।")
    elif amount == 0:
        # Legitimate for the destitute, so this must never block — but a zero
        # declaration is also the cheapest way to fake means-test eligibility.
        r.add(Severity.WARNING, "income_zero", field_name,
              "Zero income declared — an income certificate will be required.",
              "शून्य आय घोषित — आय प्रमाण पत्र आवश्यक होगा।")
    elif amount > 100_000_000:
        r.add(Severity.WARNING, "income_implausible", field_name,
              "Declared income is unusually high; please confirm the amount.",
              "घोषित आय असामान्य रूप से अधिक है; कृपया पुष्टि करें।")
    return r


def validate_name(value, field_name="name") -> ValidationResult:
    r = ValidationResult()
    text = str(value or "").strip()
    if not text:
        r.add(Severity.ERROR, "name_missing", field_name,
              "Name is required.", "नाम आवश्यक है।")
        return r
    if len(text) < 2:
        r.add(Severity.ERROR, "name_too_short", field_name,
              "Name is too short.", "नाम बहुत छोटा है।")
        return r
    # Allow Latin and Devanagari letters, spaces, apostrophes and periods.
    if not re.search(r"[A-Za-zऀ-ॿ]{2,}", text):
        r.add(Severity.ERROR, "name_no_letters", field_name,
              "Name must contain letters.", "नाम में अक्षर होने चाहिए।")
        return r
    if re.fullmatch(r"(?i)(test|dummy|abc|xyz|na|n/a|none|asdf)\W*", text):
        r.add(Severity.WARNING, "name_placeholder", field_name,
              "This looks like placeholder text rather than a real name.",
              "यह वास्तविक नाम नहीं लगता।")
    return r


# Dispatch by canonical profileKey / field type, so any form — catalog or
# freshly extracted — gets the right checks without per-scheme wiring.
_VALIDATORS_BY_KEY = {
    "aadhaar_number": validate_aadhaar,
    "guardian_aadhaar": validate_aadhaar,
    "mobile_number": validate_mobile,
    "ifsc_code": validate_ifsc,
    "bank_account_number": validate_bank_account,
    "pincode": validate_pincode,
    "pan_number": validate_pan,
    "date_of_birth": validate_date_of_birth,
    "girl_child_dob": validate_date_of_birth,
    "annual_income": validate_income,
    "name": validate_name,
}

_VALIDATORS_BY_TYPE = {
    "aadhaar": validate_aadhaar,
    "phone": validate_mobile,
    "date": validate_date_of_birth,
}


def validate_profile(profile: dict, fields: list[dict] | None = None) -> ValidationResult:
    """Validate a citizen profile, optionally guided by a form's field list.

    `fields` supplies the form's declared types and which fields are required,
    so a missing mandatory answer is caught before a PDF is ever generated.
    """
    result = ValidationResult()
    profile = profile or {}

    checked: set[str] = set()

    # Aadhaar Act s7 proviso: a person without Aadhaar must be offered an
    # alternative means of identification. So a missing Aadhaar is only an error
    # when no other accepted document was supplied — and the message then names
    # the alternatives rather than demanding Aadhaar specifically.
    from dpdp import identity_documents

    has_identity = identity_documents.has_any(profile)

    for f in fields or []:
        key = f.get("profileKey") or f.get("fieldName")
        if not key or key in checked:
            continue
        checked.add(key)
        value = profile.get(key)

        if key in identity_documents.DOCUMENT_KEYS and f.get("required"):
            if has_identity:
                # Some accepted document is present; this particular one is not
                # required. Validate it only if it was actually supplied.
                if value in (None, ""):
                    continue
            else:
                ok, en, hi = identity_documents.validate_profile_identity(profile)
                if not ok:
                    result.add(Severity.ERROR, "identity_document_missing", key, en, hi)
                    continue

        if f.get("required") and (value is None or str(value).strip() == ""):
            label = f.get("labelEnglish") or key
            label_hi = f.get("labelHindi") or ""
            result.add(Severity.ERROR, "required_missing", key,
                       f"{label} is required.",
                       f"{label_hi} आवश्यक है।" if label_hi else "यह फ़ील्ड आवश्यक है।")
            continue

        if value is None or str(value).strip() == "":
            continue

        validator = _VALIDATORS_BY_KEY.get(key) or _VALIDATORS_BY_TYPE.get(f.get("type"))
        if validator:
            result.findings.extend(validator(value, key).findings)

    # Also validate any known-sensitive keys present in the profile but not
    # declared by this form — a bad Aadhaar is a bad Aadhaar regardless.
    for key, validator in _VALIDATORS_BY_KEY.items():
        if key in checked:
            continue
        value = profile.get(key)
        if value not in (None, ""):
            result.findings.extend(validator(value, key).findings)

    return result
