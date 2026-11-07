"""Form intake - collect every detail a chosen form needs, one question at a time.

The static profiler (`services/profiler.py`) only ever learns four things: name,
age, income, State. Real government forms ask for a great deal more - a
scholarship wants the course and institution, a pension wants the bank account
and IFSC, a girl-child scheme wants the child's date of birth. Those details
differ form to form and are not known in advance.

This module is the brain that closes that gap. Given the forms a citizen has
chosen and whatever is already stored about them, it works out:

  * which of the form's fields are already answered,
  * which are still missing (required *and* optional - "store all new details",
    not just the mandatory ones),
  * what the next question is, localised, with its type and any options, and
  * whether a typed answer is valid, returning the normalised value to store.

Two rules are baked in so the layers above cannot get them wrong:

* **Transient fields are never stored.** The Aadhaar number is stripped before
  storage everywhere else in the system (`dpdp/profile_store`), so a naive
  "ask for every missing field and save it" loop would ask for the Aadhaar on
  every turn forever - it is supplied, stripped, found missing again, asked
  again. Transient fields are collected only at the moment of filling and used
  once; they are not part of profile completeness.

* **Absence is not invalidity.** A field the citizen has not reached yet is
  missing, not wrong. Only an answer that is actually malformed is rejected,
  with a message in the citizen's language.

The module is pure and needs no database, network or model, so it is cheap to
test and safe to call from a request handler.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Optional

import validation

# Fields collected for a single fill and then discarded. The Aadhaar number must
# never be persisted (Aadhaar (Authentication) Regulations; enforced in
# dpdp/profile_store and dpdp/aadhaar_policy). It is asked for, if the form needs
# it, at the moment the PDF is generated and used only for that one document.
TRANSIENT_KEYS = frozenset({"aadhaar_number", "guardian_aadhaar"})


def field_key(field: dict) -> str:
    """The canonical key a field writes to in the profile."""
    return field.get("profileKey") or field.get("fieldName") or ""


def collect_fields(schemes: list[dict]) -> list[dict]:
    """Every distinct field the given forms ask for, in form order.

    `schemes` is a list of catalog entries or form templates, each carrying an
    `extractedFields` list. A field is kept once, under its profile key, the
    first time it is seen - so choosing two schemes that both want a mobile
    number asks for it once, not twice.

    When two forms disagree about the same field, the stricter view wins: a
    field that any selected form marks required is required (or the citizen
    would be allowed to skip it and then be refused by the form that needed
    it), and labels or options a later form supplies fill gaps in the first.
    """
    by_key: dict[str, dict] = {}
    fields: list[dict] = []
    for scheme in schemes or []:
        for f in (scheme or {}).get("extractedFields") or []:
            key = field_key(f)
            if not key:
                continue
            kept = by_key.get(key)
            if kept is None:
                kept = dict(f)
                by_key[key] = kept
                fields.append(kept)
                continue
            if f.get("required") and not kept.get("required"):
                kept["required"] = True
            for extra in ("options", "labelHindi", "labelEnglish", "maxLength"):
                if not kept.get(extra) and f.get(extra):
                    kept[extra] = f[extra]
    return fields


def _is_answered(profile: dict, key: str) -> bool:
    value = profile.get(key)
    return value is not None and str(value).strip() != ""


def question_for(field: dict) -> dict:
    """A localised question for one field, with everything a form needs to ask it.

    Returns both languages; the client shows whichever the citizen is using. The
    app only guarantees English and Hindi as first-class, and every catalog
    field carries both labels, so no machine translation is involved.
    """
    key = field_key(field)
    label_en = field.get("labelEnglish") or key.replace("_", " ").title()
    label_hi = field.get("labelHindi") or ""
    ftype = field.get("type", "text")

    question_en = f"Please provide: {label_en}"
    question_hi = f"कृपया बताएं: {label_hi}" if label_hi else f"कृपया बताएं: {label_en}"
    q = {
        "profileKey": key,
        "labelEnglish": label_en,
        "labelHindi": label_hi,
        "type": ftype,
        "required": bool(field.get("required", False)),
        "transient": key in TRANSIENT_KEYS,
        "questionEnglish": question_en,
        "questionHindi": question_hi,
        # The raw field, and a combined prompt string, are kept for existing
        # callers (the SmartProfiler UI reads nextQuestion.field.labelHindi).
        "field": field,
        "questionText": f"{label_hi} ({label_en})" if label_hi else label_en,
    }
    if field.get("options"):
        q["options"] = list(field["options"])
    if field.get("maxLength"):
        q["maxLength"] = field["maxLength"]
    if key in TRANSIENT_KEYS:
        # Say plainly that this one is used once and not kept, so the interface
        # can reassure the citizen rather than making them wonder.
        q["note_en"] = "Used only to fill this form. It is not stored."
        q["note_hi"] = "केवल यह फॉर्म भरने के लिए। इसे सहेजा नहीं जाता।"
    return q


# Fields whose value is a number the machine reads back (an account, a phone,
# a PIN): these must be stored as ASCII digits whatever script they were typed
# in. A PIN code typed in Devanagari numerals is a correct answer from the
# citizen's side and an unreadable one from the bank's.
_NUMERIC_TYPES = frozenset({"aadhaar", "phone", "number"})
_NUMERIC_KEYS = frozenset({
    "aadhaar_number", "guardian_aadhaar", "mobile_number", "pincode",
    "bank_account_number", "annual_income",
})
# The longest any free-text answer may be when the form itself sets no limit.
# Government form boxes are short; a value this long is a paste error, and it
# would be truncated or overflow on the page.
_DEFAULT_MAX_LENGTH = 500

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def _ascii_digits(text: str) -> str:
    """Rewrite every Unicode decimal digit (Devanagari, Bengali, Tamil, …) as
    its ASCII equivalent, leaving everything else untouched."""
    out = []
    for ch in text:
        d = unicodedata.decimal(ch, None)
        out.append(str(d) if d is not None else ch)
    return "".join(out)


def validate_answer(field: dict, raw: Any) -> tuple[Optional[Any], str, str]:
    """Validate and normalise one typed answer.

    Returns (value, error_en, error_hi). On success error strings are empty and
    `value` is the normalised form to store (an ISO date, an int income, the
    canonical spelling of a select option, digits-only for a phone, and so on).
    On failure `value` is None and the two error strings carry the reason in
    each language.
    """
    key = field_key(field)
    ftype = field.get("type", "text")
    text = "" if raw is None else str(raw).strip()

    if text == "":
        if field.get("required"):
            label = field.get("labelEnglish") or key
            label_hi = field.get("labelHindi") or ""
            return (None, f"{label} is required.",
                    f"{label_hi} आवश्यक है।" if label_hi else "यह फ़ील्ड आवश्यक है।")
        # An optional field left blank is a valid answer: skip it.
        return ("", "", "")

    # Numbers typed in an Indian script are read as numbers, not rejected.
    if ftype in _NUMERIC_TYPES or key in _NUMERIC_KEYS:
        text = _ascii_digits(text)

    # "0 98250 11223" is how many people write a mobile number. The shared
    # validator tolerates +91 but not the trunk 0; strip it here so the same
    # citizen is not refused for one habit and accepted for the other.
    if key == "mobile_number" or ftype == "phone":
        digits = validation.normalize_digits(text)
        if len(digits) == 11 and digits.startswith("0"):
            text = digits[1:]

    # Length first, before any keyed validator can accept an overlong value:
    # the form has a box of a known size and the PDF filler cannot grow it.
    max_len = field.get("maxLength") or _DEFAULT_MAX_LENGTH
    if len(text) > max_len:
        return (None, f"Please keep this under {max_len} characters.",
                f"कृपया {max_len} अक्षरों से कम रखें।")

    # No government form value contains angle brackets or control characters.
    # Refusing them keeps a pasted fragment of markup out of the stored profile
    # and off the printed form.
    if "<" in text or ">" in text or any(ord(c) < 32 for c in text):
        return (None, "Please remove the < > or special characters.",
                "कृपया < > या विशेष अक्षर हटाएं।")

    # Select: accept the canonical option, case-insensitively, and store it in
    # the form's own spelling so it prints exactly as the form expects.
    if ftype == "select" and field.get("options"):
        for opt in field["options"]:
            if text.lower() == str(opt).lower():
                return (opt, "", "")
        options = ", ".join(str(o) for o in field["options"])
        return (None, f"Please choose one of: {options}.",
                f"इनमें से चुनें: {options}।")

    if ftype == "email":
        if not _EMAIL_RE.match(text):
            return (None, "Please enter a valid email address.",
                    "कृपया सही ईमेल पता दें।")
        return (text.lower(), "", "")

    # Typed validators (Aadhaar, phone, date, pincode, IFSC, income, name, …).
    validator = (validation._VALIDATORS_BY_KEY.get(key)
                 or validation._VALIDATORS_BY_TYPE.get(ftype))
    if validator:
        result = validator(text, key)
        blocking = [f for f in result.errors if f.code not in validation.ABSENCE_CODES]
        if blocking:
            first = blocking[0]
            return (None, first.message_en,
                    first.message_hi or first.message_en)
        return (_normalise(key, ftype, text), "", "")

    if ftype == "number":
        return _parse_number(key, text)

    return (text, "", "")


def _parse_number(key: str, text: str) -> tuple[Optional[Any], str, str]:
    """A plain number field: whole or decimal, never negative, and a
    percentage stays between 0 and 100."""
    m = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
    if not m:
        return (None, "Please enter a number.", "कृपया संख्या में बताएं।")
    value: Any = float(m.group()) if "." in m.group() else int(m.group())
    if value < 0:
        return (None, "This cannot be a negative number.",
                "यह ऋणात्मक संख्या नहीं हो सकती।")
    if "percent" in key and value > 100:
        return (None, "A percentage cannot be more than 100.",
                "प्रतिशत 100 से अधिक नहीं हो सकता।")
    return (value, "", "")


def _normalise(key: str, ftype: str, text: str) -> Any:
    """Canonical stored form of a validated value."""
    if key in ("date_of_birth", "girl_child_dob") or ftype == "date":
        d = validation.parse_date(text)
        return d.isoformat() if d else text
    if key == "mobile_number" or ftype == "phone":
        digits = validation.normalize_digits(text)
        # validate_mobile tolerates a +91 or leading 0; store the bare 10
        # digits the form box has room for.
        if len(digits) == 12 and digits.startswith("91"):
            digits = digits[2:]
        elif len(digits) == 11 and digits.startswith("0"):
            digits = digits[1:]
        return digits
    if key in ("aadhaar_number", "guardian_aadhaar", "pincode",
               "bank_account_number") or ftype == "aadhaar":
        return validation.normalize_digits(text)
    if key == "annual_income":
        nums = re.findall(r"\d+", text.replace(",", ""))
        return int(nums[0]) if nums else text
    if key == "ifsc_code":
        return text.upper()
    return text


def intake_state(profile: dict, fields: list[dict]) -> dict:
    """Where the citizen stands against a set of fields.

    Splits the fields into those already answered, those still needed (required
    first, then optional), and the transient ones the form will ask for at fill
    time. `requiredComplete` is what gates filling the form; `allComplete` is
    true only once the optional details are in too.
    """
    profile = profile or {}
    known: list[dict] = []
    missing_required: list[dict] = []
    missing_optional: list[dict] = []
    transient: list[dict] = []

    for f in fields:
        key = field_key(f)
        if not key:
            continue
        if key in TRANSIENT_KEYS:
            # Never counted toward completeness; recorded so the fill step knows
            # to ask for it. If it happens to be present already (passed in for a
            # fill), it is still treated as transient.
            transient.append(f)
            continue
        if _is_answered(profile, key):
            known.append({**f, "currentValue": profile[key]})
        elif f.get("required"):
            missing_required.append(f)
        else:
            missing_optional.append(f)

    storable_total = len(known) + len(missing_required) + len(missing_optional)
    next_field = missing_required[0] if missing_required else (
        missing_optional[0] if missing_optional else None)

    return {
        "known": known,
        "missingRequired": missing_required,
        "missingOptional": missing_optional,
        "transient": transient,
        "knownCount": len(known),
        "missingRequiredCount": len(missing_required),
        "missingOptionalCount": len(missing_optional),
        "storableTotal": storable_total,
        # A form that asks for nothing storable (only a transient Aadhaar, say)
        # is complete, and must not read as 0% done.
        "progress": (100.0 if storable_total == 0
                     else round(len(known) / storable_total * 100, 1)),
        "requiredComplete": not missing_required,
        "allComplete": not missing_required and not missing_optional,
        "nextQuestion": question_for(next_field) if next_field else None,
    }
