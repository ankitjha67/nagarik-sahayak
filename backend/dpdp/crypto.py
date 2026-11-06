"""Encryption at rest for stored personal data.

Closes the remaining limb of SPDI Rule 8 and DPDP s8(4): reasonable security
practices proportionate to the data held. Everything else built so far protects
data in motion and in use — ownership checks, redaction, masking. None of it
helps if someone obtains a copy of the database, which is the likeliest way a
breach of this system would actually happen.

Design notes worth stating, because each one is a decision that could sensibly
have gone another way:

**AES-256-GCM, not CBC or a raw stream cipher.** GCM is authenticated: a
tampered ciphertext fails to decrypt rather than silently yielding altered
plaintext. For a record that decides someone's benefit eligibility, undetected
modification is as harmful as disclosure.

**A fresh random nonce per encryption, never reused.** GCM fails
catastrophically on nonce reuse — it leaks the XOR of plaintexts and the
authentication key. The nonce is stored alongside the ciphertext, which is safe
and standard; what must never repeat is the (key, nonce) pair.

**Versioned envelope.** Ciphertext carries a version tag so the key can be
rotated without a flag-day migration: new writes use the current key, old reads
fall back to previous keys until the backfill completes.

**Passthrough when unconfigured.** Without a key the module stores plaintext and
says so loudly in the compliance report, rather than refusing to start. A
developer running locally should not be blocked, but a production deployment
must not be able to believe it is encrypted when it is not.

The operational risk is blunt and worth repeating wherever this is deployed:
**lose DATA_ENCRYPTION_KEY and the data is gone.** There is no recovery path,
because a recovery path would be a second way in.
"""
from __future__ import annotations

import base64
import json
import logging
import os

logger = logging.getLogger(__name__)

ENVELOPE_PREFIX = "enc:v1:"
_NONCE_BYTES = 12          # 96 bits, the size AES-GCM is specified for
_KEY_BYTES = 32            # AES-256

_warned_missing_key = False


def _load_keys() -> list[bytes]:
    """Current key first, then any previous keys still needed for reads.

    DATA_ENCRYPTION_KEY holds the active key; DATA_ENCRYPTION_KEY_OLD may hold
    a comma-separated list of superseded keys so a rotation can proceed while
    old ciphertext is still being re-encrypted.
    """
    keys: list[bytes] = []
    for raw in [os.environ.get("DATA_ENCRYPTION_KEY", "")] + [
        k.strip() for k in os.environ.get("DATA_ENCRYPTION_KEY_OLD", "").split(",")
    ]:
        if not raw:
            continue
        try:
            key = base64.urlsafe_b64decode(raw)
        except Exception:
            logger.error("DATA_ENCRYPTION_KEY is not valid base64; ignoring it")
            continue
        if len(key) != _KEY_BYTES:
            logger.error(
                "Encryption key must be %d bytes (got %d); ignoring it",
                _KEY_BYTES, len(key))
            continue
        keys.append(key)
    return keys


def is_enabled() -> bool:
    """Whether encryption at rest is actually configured."""
    global _warned_missing_key
    keys = _load_keys()
    if not keys and not _warned_missing_key:
        logger.warning(
            "DATA_ENCRYPTION_KEY is not set — personal data is being stored "
            "unencrypted. Set a 32-byte base64 key in production; see "
            "dpdp/crypto.py generate_key()."
        )
        _warned_missing_key = True
    return bool(keys) and _backend_available()


def _backend_available() -> bool:
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa: F401
        return True
    except ImportError:
        logger.error("cryptography is not installed — cannot encrypt at rest")
        return False


def generate_key() -> str:
    """A fresh base64 key, for operators setting this up the first time."""
    return base64.urlsafe_b64encode(os.urandom(_KEY_BYTES)).decode()


def encrypt(plaintext: str) -> str:
    """Encrypt a string. Returns it unchanged if encryption is not configured."""
    if plaintext in (None, ""):
        return plaintext
    if is_encrypted(plaintext):
        return plaintext          # never double-encrypt
    keys = _load_keys()
    if not keys or not _backend_available():
        return plaintext

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    nonce = os.urandom(_NONCE_BYTES)
    ct = AESGCM(keys[0]).encrypt(nonce, plaintext.encode("utf-8"), None)
    return (ENVELOPE_PREFIX
            + base64.urlsafe_b64encode(nonce).decode() + ":"
            + base64.urlsafe_b64encode(ct).decode())


def decrypt(value: str) -> str:
    """Decrypt a value. Plaintext passes through, so mixed data still reads.

    That tolerance is what lets a backfill run gradually instead of requiring
    every row to be converted before the app can start.
    """
    if not value or not is_encrypted(value):
        return value

    try:
        _, _, rest = value.partition(ENVELOPE_PREFIX)
        nonce_b64, _, ct_b64 = rest.partition(":")
        nonce = base64.urlsafe_b64decode(nonce_b64)
        ct = base64.urlsafe_b64decode(ct_b64)
    except Exception as e:
        logger.error(f"Malformed ciphertext envelope: {e}")
        raise DecryptionError("Stored value is not a valid ciphertext envelope")

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    # Try each known key so a rotation in progress still reads old rows.
    for key in _load_keys():
        try:
            return AESGCM(key).decrypt(nonce, ct, None).decode("utf-8")
        except Exception:
            continue

    # Every key failed: either the data was tampered with, or the key that
    # wrote it is gone. Both need a human, so this raises rather than
    # returning something plausible.
    raise DecryptionError(
        "Could not decrypt stored personal data with any configured key. "
        "Either DATA_ENCRYPTION_KEY has changed without a backfill, or the "
        "record has been tampered with."
    )


def is_encrypted(value) -> bool:
    return isinstance(value, str) and value.startswith(ENVELOPE_PREFIX)


def encrypt_json(obj) -> str:
    """Serialise and encrypt a structure for storage."""
    return encrypt(json.dumps(obj, ensure_ascii=False, default=str))


def decrypt_json(value):
    """Decrypt and parse. Accepts plaintext JSON and dicts unchanged."""
    if value in (None, ""):
        return {}
    if isinstance(value, dict):
        return value
    text = decrypt(value) if is_encrypted(value) else value
    if isinstance(text, dict):
        return text
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return {}


def status() -> dict:
    """Encryption posture, for the compliance report."""
    keys = _load_keys()
    return {
        "enabled": is_enabled(),
        "algorithm": "AES-256-GCM" if keys else None,
        "keys_configured": len(keys),
        "rotation_supported": len(keys) > 1,
        "backend_available": _backend_available(),
        "warning": None if is_enabled() else
                   "Personal data is stored unencrypted. Set "
                   "DATA_ENCRYPTION_KEY (32-byte base64) to satisfy SPDI "
                   "Rule 8 and DPDP s8(4).",
        "key_loss_warning": "There is no recovery if DATA_ENCRYPTION_KEY is "
                            "lost. Back it up in a secret manager, never in "
                            "the repository.",
    }


class DecryptionError(RuntimeError):
    """Stored data could not be decrypted with any configured key."""
