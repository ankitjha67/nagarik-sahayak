"""Alternative identity documents — Aadhaar Act 2016, s7 proviso.

The proviso to section 7 is explicit: where a person assigned an Aadhaar number
does not have one, or authentication fails, they must be offered an alternative
means of identification. The Supreme Court in *Puttaswamy* was blunter still —
nobody may be denied a benefit for want of Aadhaar.

This matters more here than the statute alone suggests. The people least likely
to hold a working Aadhaar are the elderly, the homeless, migrant workers, and
people whose fingerprints no longer read after decades of manual labour. They
are precisely the population an old-age pension or a BPL housing scheme exists
to serve. An application form that will not proceed without Aadhaar excludes the
intended beneficiary and admits the person who least needs it.

So every scheme in this app accepts any one of the documents below. Aadhaar is
listed first because it is the most widely held and the one most departments
expect, not because it is required.

Format validation is deliberately loose for the state-issued documents. Ration
card and job card formats vary by state and have changed over time; rejecting an
unfamiliar-looking but genuine card would recreate the exclusion this module
exists to prevent. Where a document has a real check — Aadhaar's Verhoeff digit,
PAN's fixed shape — it is applied.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class IdentityDocument:
    key: str                  # profile key holding the number
    name_en: str
    name_hi: str
    pattern: str | None       # None where formats vary too much to check
    hint_en: str
    hint_hi: str
    issuer: str

    def as_dict(self) -> dict:
        return {
            "key": self.key, "name_en": self.name_en, "name_hi": self.name_hi,
            "hint_en": self.hint_en, "hint_hi": self.hint_hi,
            "issuer": self.issuer, "has_format_check": self.pattern is not None,
        }


ACCEPTED_DOCUMENTS: tuple[IdentityDocument, ...] = (
    IdentityDocument(
        "aadhaar_number", "Aadhaar", "आधार",
        r"^\d{12}$",
        "12 digits", "12 अंक", "UIDAI",
    ),
    IdentityDocument(
        "voter_id_number", "Voter ID (EPIC)", "मतदाता पहचान पत्र",
        r"^[A-Z]{3}\d{7}$",
        "3 letters then 7 digits, e.g. ABC1234567",
        "3 अक्षर फिर 7 अंक, जैसे ABC1234567",
        "Election Commission of India",
    ),
    IdentityDocument(
        "ration_card_number", "Ration Card", "राशन कार्ड",
        None,        # format varies by state and has changed over time
        "As printed on your card",
        "जैसा आपके कार्ड पर छपा है",
        "State Food and Civil Supplies Department",
    ),
    IdentityDocument(
        "pan_number", "PAN", "पैन",
        r"^[A-Z]{5}\d{4}[A-Z]$",
        "5 letters, 4 digits, 1 letter, e.g. ABCDE1234F",
        "5 अक्षर, 4 अंक, 1 अक्षर, जैसे ABCDE1234F",
        "Income Tax Department",
    ),
    IdentityDocument(
        "driving_licence_number", "Driving Licence", "ड्राइविंग लाइसेंस",
        None,        # state prefixes and separators vary widely
        "As printed on your licence",
        "जैसा आपके लाइसेंस पर छपा है",
        "State Transport Authority",
    ),
    IdentityDocument(
        "passport_number", "Passport", "पासपोर्ट",
        r"^[A-Z]\d{7}$",
        "1 letter then 7 digits", "1 अक्षर फिर 7 अंक",
        "Ministry of External Affairs",
    ),
    IdentityDocument(
        "job_card_number", "MGNREGA Job Card", "मनरेगा जॉब कार्ड",
        None,
        "As printed on your job card",
        "जैसा आपके जॉब कार्ड पर छपा है",
        "Ministry of Rural Development",
    ),
)

BY_KEY = {d.key: d for d in ACCEPTED_DOCUMENTS}
DOCUMENT_KEYS = tuple(d.key for d in ACCEPTED_DOCUMENTS)


def normalise(value, key: str) -> str:
    """Canonical form for comparison and validation."""
    text = str(value or "").strip().upper()
    if key == "aadhaar_number":
        return re.sub(r"\D", "", text)
    return re.sub(r"[\s\-/]", "", text)


def which_provided(profile: dict) -> list[str]:
    """Identity documents present in the profile.

    Also recognises the stored last-four remnant of an Aadhaar, since the number
    itself is deliberately not persisted — a returning citizen who gave Aadhaar
    once should not be told they have supplied no identity document.
    """
    profile = profile or {}
    found = [k for k in DOCUMENT_KEYS if str(profile.get(k) or "").strip()]
    if "aadhaar_number" not in found and profile.get("aadhaar_number_last4"):
        found.insert(0, "aadhaar_number")
    return found


def has_any(profile: dict) -> bool:
    return bool(which_provided(profile))


def validate(value, key: str) -> tuple[bool, str, str]:
    """Check one document. Returns (ok, message_en, message_hi).

    Documents with no reliable national format are accepted on presence alone;
    the department verifies the physical card, and refusing a genuine one here
    would deny a benefit over a formatting guess.
    """
    doc = BY_KEY.get(key)
    if not doc:
        return False, f"Unknown document type: {key}", "अज्ञात दस्तावेज़ प्रकार"

    cleaned = normalise(value, key)
    if not cleaned:
        return False, f"{doc.name_en} number is empty.", f"{doc.name_hi} संख्या खाली है।"

    if key == "aadhaar_number":
        # Reuse the full Aadhaar rules, including the Verhoeff check.
        from validation import validate_aadhaar
        result = validate_aadhaar(cleaned)
        if result.is_blocking:
            err = result.errors[0]
            return False, err.message_en, err.message_hi
        return True, "", ""

    if doc.pattern and not re.fullmatch(doc.pattern, cleaned):
        return (False,
                f"{doc.name_en} should be {doc.hint_en}.",
                f"{doc.name_hi} {doc.hint_hi} होना चाहिए।")

    return True, "", ""


def validate_profile_identity(profile: dict) -> tuple[bool, str, str]:
    """Does this profile carry at least one usable identity document?

    Returns (ok, message_en, message_hi). A malformed document is reported
    against that document; supplying none at all is reported as a choice among
    the accepted list, so the citizen learns what else would work rather than
    being told only that Aadhaar is missing.
    """
    provided = which_provided(profile)
    if not provided:
        names_en = ", ".join(d.name_en for d in ACCEPTED_DOCUMENTS)
        names_hi = ", ".join(d.name_hi for d in ACCEPTED_DOCUMENTS)
        return (False,
                f"Provide any one identity document: {names_en}.",
                f"इनमें से कोई एक पहचान दस्तावेज़ दें: {names_hi}।")

    # Any one valid document is enough. Report an error only if every supplied
    # document is malformed — a citizen who gave a good voter ID and mistyped
    # their PAN should not be blocked.
    errors = []
    for key in provided:
        value = profile.get(key)
        if not value:
            continue        # the last-four remnant case
        ok, en, hi = validate(value, key)
        if ok:
            return True, "", ""
        errors.append((en, hi))

    if not errors:
        return True, "", ""
    return False, errors[0][0], errors[0][1]


def options() -> list[dict]:
    """The accepted documents, for the UI and for the section 5 notice."""
    return [d.as_dict() for d in ACCEPTED_DOCUMENTS]
