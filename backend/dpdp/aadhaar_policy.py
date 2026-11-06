"""Aadhaar handling policy — Aadhaar Act 2016 and the UIDAI regulations.

Two obligations drive everything in this module, and both carry criminal
liability rather than a penalty, which is why Aadhaar is handled differently
from every other field in the application.

**Non-storage.** Under the Authentication Regulations, an entity that is not a
Requesting Entity or KUA must not store the Aadhaar number at all. This
application is not one, so it must not keep the number — even though the
government forms it fills genuinely ask for it.

The resolution is to treat Aadhaar as *transient*: accepted in a request, used
in memory to fill a form the citizen is about to download, and then discarded.
What persists is only the last four digits — enough for the citizen to recognise
which number they gave — and the keyed fingerprint the fraud engine needs, which
is one-way and not an Aadhaar number.

**No public display.** Section 29(4) forbids publishing or displaying an Aadhaar
number. UIDAI permits masked display: first eight digits replaced, last four
visible. So masking is applied at the boundary here rather than left to each
call site, because a single missed call site is a criminal exposure and "we
masked it in most places" is not a defence.

The cost of this design is real and worth stating: a citizen who returns
tomorrow must re-enter their Aadhaar, because the app genuinely does not have
it. That is the intended trade.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Profile keys holding an Aadhaar number in any form.
AADHAAR_KEYS = ("aadhaar_number", "guardian_aadhaar")

# What replaces the number in storage: the last four digits, so the citizen can
# confirm which Aadhaar they used without the app holding the identifier.
LAST4_SUFFIX = "_last4"


def digits_of(value) -> str:
    return re.sub(r"\D", "", str(value or ""))


def mask(value) -> str:
    """UIDAI-permitted masked form: XXXX XXXX 1234.

    Anything that is not a 12-digit number is returned fully masked rather than
    passed through — a malformed value may still be someone's identifier, and
    echoing it back would defeat the point.
    """
    digits = digits_of(value)
    if len(digits) == 12:
        return f"XXXX XXXX {digits[-4:]}"
    if not digits:
        return ""
    return "X" * len(digits)


def last4(value) -> str:
    digits = digits_of(value)
    return digits[-4:] if len(digits) == 12 else ""


def strip_for_storage(profile: dict) -> tuple[dict, dict]:
    """Split a profile into what may be stored and the Aadhaar held back.

    Returns (storable, withheld). `storable` carries `<key>_last4` in place of
    each Aadhaar; `withheld` carries the full numbers for immediate in-memory
    use by the caller, and must not be persisted.
    """
    storable = dict(profile or {})
    withheld: dict[str, str] = {}

    for key in AADHAAR_KEYS:
        value = storable.pop(key, None)
        if value in (None, ""):
            continue
        digits = digits_of(value)
        withheld[key] = digits
        tail = last4(digits)
        if tail:
            storable[f"{key}{LAST4_SUFFIX}"] = tail
        else:
            # Malformed input: keep nothing rather than storing a partial
            # identifier that is neither useful nor safe.
            logger.warning("Discarded malformed value for %s (not 12 digits)", key)

    return storable, withheld


def contains_full_aadhaar(profile: dict) -> list[str]:
    """Keys holding a full Aadhaar. Non-empty means a storage violation."""
    return [k for k in AADHAAR_KEYS
            if len(digits_of((profile or {}).get(k))) == 12]


def redact_for_display(profile: dict) -> dict:
    """Copy of a profile safe to render, log or return in a response."""
    out = dict(profile or {})
    for key in AADHAAR_KEYS:
        if out.get(key) not in (None, ""):
            out[key] = mask(out[key])
    return out


def merge_for_form_fill(stored: dict, supplied: dict | None) -> dict:
    """Reassemble a complete profile for filling one form, in memory only.

    `supplied` is the Aadhaar the citizen provides with this specific request.
    Where they do not supply it, the form is filled with the masked form built
    from the stored last four digits: the document remains useful and the
    citizen writes the number in by hand, which is what the non-storage
    obligation costs.
    """
    merged = dict(stored or {})
    supplied = supplied or {}

    for key in AADHAAR_KEYS:
        provided = digits_of(supplied.get(key))
        if len(provided) == 12:
            merged[key] = provided
            continue
        tail = (stored or {}).get(f"{key}{LAST4_SUFFIX}")
        if tail:
            merged[key] = f"XXXX XXXX {tail}"
    return merged


def assert_no_stored_aadhaar(profile: dict, *, where: str = "") -> None:
    """Raise if a full Aadhaar is about to be persisted.

    A hard failure rather than a warning: this is the boundary the Act draws,
    and a silently-logged violation would be discovered only in an audit.
    """
    offending = contains_full_aadhaar(profile)
    if offending:
        raise AadhaarStorageViolation(
            f"Refusing to store a full Aadhaar number in {where or 'the database'}: "
            f"{', '.join(offending)}. Under the Aadhaar (Authentication) "
            f"Regulations an entity that is not a Requesting Entity must not "
            f"store the Aadhaar number. Use strip_for_storage() first."
        )


class AadhaarStorageViolation(RuntimeError):
    """Attempt to persist a full Aadhaar number."""
