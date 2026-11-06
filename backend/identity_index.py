"""Indexed, hashed identity fingerprints for cross-applicant fraud checks.

The fraud engine needs to answer one question about identifiers: *do two
applicants share this Aadhaar / bank account / mobile number?* It never needs to
read the value back.

That distinction drives the whole design here. Equality on a keyed hash answers
the question, so identifiers are indexed as HMAC digests rather than as a second
plaintext copy of everyone's Aadhaar sitting in a queryable column. The database
gains the fraud signal without gaining a breach target: an attacker with read
access to the User table gets digests, not identity numbers.

Why HMAC with a secret salt rather than a bare SHA-256: the Aadhaar space is
only 10^12, which is trivially enumerable on commodity hardware. An unsalted
digest is therefore reversible in practice and would offer no protection at all.

Operational consequence worth knowing: IDENTITY_HASH_SALT is a long-lived
secret. Changing it invalidates every stored fingerprint, and shared-identifier
detection silently stops matching until the backfill is re-run. `scripts/
backfill_identity_index.py` exists for exactly that recovery, and for populating
users who registered before this index existed.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os

logger = logging.getLogger(__name__)

# Fields fingerprinted for cross-applicant comparison, mapped to the User column
# that stores each digest.
INDEXED_IDENTIFIERS = {
    "aadhaar_number": "aadhaarFp",
    "bank_account_number": "bankAccountFp",
    "mobile_number": "mobileFp",
    "ration_card_number": "rationCardFp",
}

_MISSING_SALT_WARNED = False


def _salt() -> bytes:
    """The HMAC key. Falls back to a constant only so development works."""
    global _MISSING_SALT_WARNED
    salt = os.environ.get("IDENTITY_HASH_SALT", "")
    if not salt:
        if not _MISSING_SALT_WARNED:
            logger.warning(
                "IDENTITY_HASH_SALT is not set — identity fingerprints are using "
                "a default key and are NOT protected against enumeration. Set a "
                "long random value in production."
            )
            _MISSING_SALT_WARNED = True
        salt = "nagarik-sahayak-dev-salt-do-not-use-in-production"
    return salt.encode("utf-8")


def _canonical(value, field: str) -> str:
    """Normalise before hashing so trivial formatting differences still match.

    "2345 6789 0124" and "234567890124" are the same Aadhaar and must produce
    the same fingerprint, or a fraudster evades detection with a space.
    """
    text = str(value or "").strip()
    if not text:
        return ""
    if field == "ration_card_number":
        # Alphanumeric, case-insensitive — ration card formats vary by state.
        return "".join(ch for ch in text if ch.isalnum()).lower()
    digits = "".join(ch for ch in text if ch.isdigit())
    if field == "mobile_number":
        if digits.startswith("91") and len(digits) == 12:
            digits = digits[2:]      # tolerate a +91 prefix
    return digits


def fingerprint(value, field: str) -> str:
    """Keyed digest of one identifier, or "" when there is nothing to hash."""
    canonical = _canonical(value, field)
    if not canonical:
        return ""
    # Field name is part of the message so the same digits used as, say, both a
    # mobile number and an account number do not collide across columns.
    message = f"{field}:{canonical}".encode("utf-8")
    return hmac.new(_salt(), message, hashlib.sha256).hexdigest()


def fingerprints_for(profile: dict) -> dict:
    """Map of User column -> digest for every indexed identifier in `profile`.

    Absent identifiers yield "" so a cleared field also clears its fingerprint;
    leaving a stale digest behind would keep matching a number the citizen has
    since removed.
    """
    profile = profile or {}
    return {
        column: fingerprint(profile.get(field), field)
        for field, column in INDEXED_IDENTIFIERS.items()
    }


def merge_into_update(data: dict, profile: dict) -> dict:
    """Add fingerprint columns to a Prisma user-update payload.

    Call this from every write path that changes a profile, so the index cannot
    drift out of step with the data it describes.
    """
    return {**data, **fingerprints_for(profile)}


async def count_sharing(prisma, column: str, digest: str, exclude_user_id: str = "") -> int:
    """How many *other* users carry this fingerprint.

    Returns 0 for an empty digest: "nobody supplied this identifier" must never
    be read as "everybody shares it".
    """
    if not digest:
        return 0
    try:
        where = {column: digest}
        if exclude_user_id:
            where["id"] = {"not": exclude_user_id}
        return await prisma.user.count(where=where)
    except Exception as e:
        # A counting failure must not block a citizen's application; losing a
        # fraud signal is the lesser harm.
        logger.warning(f"Shared-identifier count failed for {column}: {e}")
        return 0
