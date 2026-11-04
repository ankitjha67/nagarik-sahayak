"""Form intake — collect every detail a chosen form needs, one question at a time.

The static profiler (`services/profiler.py`) only ever learns four things: name,
age, income, State. Real government forms ask for a great deal more — a
scholarship wants the course and institution, a pension wants the bank account
and IFSC, a girl-child scheme wants the child's date of birth. Those details
differ form to form and are not known in advance.

This module is the brain that closes that gap. Given the forms a citizen has
chosen and whatever is already stored about them, it works out:

  * which of the form's fields are already answered,
  * which are still missing (required *and* optional — "store all new details",
    not just the mandatory ones),
  * what the next question is, localised, with its type and any options, and
  * whether a typed answer is valid, returning the normalised value to store.

Two rules are baked in so the layers above cannot get them wrong:

* **Transient fields are never stored.** The Aadhaar number is stripped before
  storage everywhere else in the system (`dpdp/profile_store`), so a naive
  "ask for every missing field and save it" loop would ask for the Aadhaar on
  every turn forever — it is supplied, stripped, found missing again, asked
  again. Transient fields are collected only at the moment of filling and used
  once; they are not part of profile completeness.

* **Absence is not invalidity.** A field the citizen has not reached yet is
  missing, not wrong. Only an answer that is actually malformed is rejected,
  with a message in the citizen's language.

The module is pure and needs no database, network or model, so it is cheap to
test and safe to call from a request handler.
"""
from __future__ import annotations

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
    first time it is seen — so choosing two schemes that both want a mobile
    number asks for it once, not twice.
    """
    seen: set[str] = set()
    fields: list[dict] = []
    for scheme in schemes:
        for f in scheme.get("extractedFields", []) or []:
            key = field_key(f)
            if not key or key in seen:
                continue
            seen.add(key)
            fields.append(f)
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

    # Select: accept the canonical option, case-insensitively, and store it in
    # the form's own spelling so it prints exactly as the form expects.
    if ftype == "select" and field.get("options"):
        for opt in field["options"]:
            if text.lower() == str(opt).lower():
                return (opt, "", "")
        options = ", ".join(str(o) for o in field["options"])
        return (None, f"Please choose one of: {options}.",
                f"इनमें से चुनें: {options}।")

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

    # Free text / number with no dedicated validator.
    if ftype == "number":
        import re
        nums = re.findall(r"-?\d+", text.replace(",", ""))
        if not nums:
            return (None, "Please enter a number.", "कृपया संख्या में बताएं।")
        return (int(nums[0]), "", "")

    max_len = field.get("maxLength")
    if max_len and len(text) > max_len:
        return (None, f"Please keep this under {max_len} characters.",
                f"कृपया {max_len} अक्षरों से कम रखें।")
    return (text, "", "")


def _normalise(key: str, ftype: str, text: str) -> Any:
    """Canonical stored form of a validated value."""
    if key in ("date_of_birth", "girl_child_dob") or ftype == "date":
        d = validation.parse_date(text)
        return d.isoformat() if d else text
    if key in ("aadhaar_number", "guardian_aadhaar", "mobile_number", "pincode") \
            or ftype in ("aadhaar", "phone"):
        return validation.normalize_digits(text)
    if key == "annual_income":
        import re
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
        "progress": round(len(known) / max(storable_total, 1) * 100, 1),
        "requiredComplete": not missing_required,
        "allComplete": not missing_required and not missing_optional,
        "nextQuestion": question_for(next_field) if next_field else None,
    }
