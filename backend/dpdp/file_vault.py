"""Encryption at rest for generated documents.

Profiles are encrypted in the database, but the documents produced from them sit
on disk in the clear — and a filled application form carries the same name, bank
account, income and address as the row it came from. Encrypting the database and
leaving the PDFs beside it protects the harder target and ignores the easier one.

Uses the same key and cipher as `dpdp/crypto.py` (AES-256-GCM, fresh nonce per
file) so there is one secret to manage rather than two, and one rotation to
perform.

Two shapes worth explaining:

**The header is binary, not the text envelope used for profile blobs.** A PDF is
bytes; wrapping it in base64 would inflate every document by a third for no
benefit. The magic prefix makes an encrypted file identifiable without decrypting
it, which is what lets a migration run incrementally.

**Reads tolerate plaintext.** Documents generated before this existed must keep
working, and a deployment that has not yet run the migration must not start
serving errors. `is_encrypted` distinguishes them, so the migration knows what
is left to do.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from dpdp import crypto

logger = logging.getLogger(__name__)

# Identifies an encrypted file without reading past the header.
MAGIC = b"NSENC1\n"
_NONCE_BYTES = 12


def is_encrypted(path: str | Path) -> bool:
    """True if the file on disk is one of ours and encrypted."""
    try:
        with open(path, "rb") as fh:
            return fh.read(len(MAGIC)) == MAGIC
    except OSError:
        return False


def encrypt_bytes(data: bytes) -> bytes:
    """Encrypt a document. Returns the input unchanged if no key is configured."""
    if not data or not crypto.is_enabled():
        return data
    if data.startswith(MAGIC):
        return data                     # never double-encrypt

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    keys = crypto._load_keys()
    nonce = os.urandom(_NONCE_BYTES)
    ct = AESGCM(keys[0]).encrypt(nonce, data, None)
    return MAGIC + nonce + ct


def decrypt_bytes(data: bytes) -> bytes:
    """Decrypt a document. Plaintext passes through so legacy files still serve."""
    if not data or not data.startswith(MAGIC):
        return data

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    body = data[len(MAGIC):]
    nonce, ct = body[:_NONCE_BYTES], body[_NONCE_BYTES:]

    for key in crypto._load_keys():
        try:
            return AESGCM(key).decrypt(nonce, ct, None)
        except Exception:
            continue

    raise crypto.DecryptionError(
        "Could not decrypt a stored document with any configured key. Either "
        "DATA_ENCRYPTION_KEY has changed without running "
        "scripts/encrypt_files_at_rest.py, or the file has been tampered with."
    )


def write(path: str | Path, data: bytes) -> None:
    """Write a document, encrypted if a key is configured."""
    Path(path).write_bytes(encrypt_bytes(data))


def read(path: str | Path) -> bytes:
    """Read a document, decrypting if needed. Raises if it cannot be decrypted."""
    return decrypt_bytes(Path(path).read_bytes())


def encrypt_in_place(path: str | Path) -> bool:
    """Encrypt an existing plaintext file. True if it was converted.

    Writes to a temporary file and renames, so an interrupted run cannot leave a
    half-written document that is neither readable nor recoverable.
    """
    path = Path(path)
    if not crypto.is_enabled() or not path.exists() or is_encrypted(path):
        return False

    tmp = path.with_suffix(path.suffix + ".enc-tmp")
    try:
        tmp.write_bytes(encrypt_bytes(path.read_bytes()))
        os.replace(tmp, path)
        return True
    except OSError as e:
        logger.error(f"Could not encrypt {path.name}: {e}")
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        return False


def status(directories: list[Path] | None = None) -> dict:
    """How much of the document store is actually encrypted."""
    from config import AUDIO_DIR, PDF_DIR

    directories = directories or [PDF_DIR, AUDIO_DIR]
    encrypted = plaintext = 0
    for directory in directories:
        try:
            for entry in Path(directory).iterdir():
                if not entry.is_file():
                    continue
                if is_encrypted(entry):
                    encrypted += 1
                else:
                    plaintext += 1
        except OSError:
            continue

    total = encrypted + plaintext
    return {
        "enabled": crypto.is_enabled(),
        "algorithm": "AES-256-GCM" if crypto.is_enabled() else None,
        "files_encrypted": encrypted,
        "files_plaintext": plaintext,
        "total_files": total,
        "fully_encrypted": crypto.is_enabled() and plaintext == 0,
        "warning": None if (crypto.is_enabled() and plaintext == 0) else (
            "Generated documents are stored unencrypted. Set "
            "DATA_ENCRYPTION_KEY and run scripts/encrypt_files_at_rest.py."
            if not crypto.is_enabled() else
            f"{plaintext} document(s) predate encryption. Run "
            f"scripts/encrypt_files_at_rest.py to convert them."
        ),
    }
