"""The single way to read and write a citizen's stored profile.

Before this existed the same "merge fullProfile over profile, tolerating both
JSON strings and dicts" loop appeared in six files. That duplication was already
a latent bug — two of the copies handled malformed JSON differently — and it
made encryption impossible to add without editing every call site.

Routing every access through here buys three things at once:

* **Encryption at rest** happens transparently. Callers never see ciphertext.
* **The Aadhaar non-storage rule is enforced on the way out**, so a new write
  path cannot reintroduce the violation by forgetting to strip it.
* **One definition of what a profile is**, rather than six that drift.
"""
from __future__ import annotations

import json
import logging

from dpdp import aadhaar_policy, crypto

logger = logging.getLogger(__name__)


def _coerce(raw) -> dict:
    """Read a stored profile blob in any of the forms it may take.

    Historic rows hold plain JSON strings, Prisma may hand back a dict, and new
    rows hold ciphertext. All three must read, or a backfill could never run
    incrementally.
    """
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return crypto.decrypt_json(raw)
    except crypto.DecryptionError:
        # Re-raised rather than swallowed: silently returning {} would look
        # like a citizen with no data, and could trigger an erroneous
        # "incomplete application" or, worse, a wrongful refusal.
        raise
    except (ValueError, TypeError):
        logger.warning("Discarding malformed profile blob")
        return {}


def load(user) -> dict:
    """The citizen's complete profile: extended merged over basic.

    fullProfile wins on conflict — it is the record the V2 flow maintains and
    is the more recently written of the two.
    """
    merged: dict = {}
    for raw in (getattr(user, "fullProfile", None), getattr(user, "profile", None)):
        data = _coerce(raw)
        for key, value in data.items():
            if key not in merged or merged[key] in (None, ""):
                merged[key] = value
    return merged


def load_full(user) -> dict:
    """Only the extended profile."""
    return _coerce(getattr(user, "fullProfile", None))


def load_basic(user) -> dict:
    """Only the basic profile."""
    return _coerce(getattr(user, "profile", None))


def prepare_full_profile(profile: dict) -> tuple[object, dict]:
    """Ready an extended profile for storage.

    Returns (value_to_store, storable_plaintext). The Aadhaar is stripped before
    anything else happens, so it can never reach the database even if
    encryption is switched off.
    """
    storable, _withheld = aadhaar_policy.strip_for_storage(profile)
    aadhaar_policy.assert_no_stored_aadhaar(storable, where="User.fullProfile")

    if crypto.is_enabled():
        return crypto.encrypt_json(storable), storable
    # Prisma's Json wrapper is applied by the caller when unencrypted, since
    # only it knows whether the column expects a document or a string.
    return storable, storable


def prepare_basic_profile(profile: dict) -> tuple[str, dict]:
    """Ready a basic profile for storage. Always a string column."""
    storable, _withheld = aadhaar_policy.strip_for_storage(profile)
    aadhaar_policy.assert_no_stored_aadhaar(storable, where="User.profile")

    if crypto.is_enabled():
        return crypto.encrypt_json(storable), storable
    return json.dumps(storable, ensure_ascii=False), storable


def status() -> dict:
    """Storage posture, for the compliance report."""
    return {
        "encryption": crypto.status(),
        "aadhaar_storage": {
            "policy": "Aadhaar numbers are never persisted; only the last four "
                      "digits and a keyed fingerprint are stored.",
            "basis": "Aadhaar (Authentication) Regulations — an entity that is "
                     "not a Requesting Entity must not store the number.",
            "enforced_at": "dpdp/profile_store.py, on every write path",
        },
    }
