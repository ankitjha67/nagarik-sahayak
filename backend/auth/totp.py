"""RFC 6238 time-based one-time passwords, for admin multi-factor login.

Implemented directly on hmac so it needs no package. Compatible with Google
Authenticator, Aegis, FreeOTP and every other TOTP app (SHA-1, 30 s, 6 digits).
"""
from __future__ import annotations

import base64
import hmac
import secrets
import struct
import time
from hashlib import sha1
from urllib.parse import quote


def generate_secret() -> str:
    """A 160-bit secret, base32 without padding, as authenticator apps expect."""
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _hotp(secret_b32: str, counter: int, digits: int = 6) -> str:
    padded = secret_b32.upper() + "=" * (-len(secret_b32) % 8)
    key = base64.b32decode(padded)
    digest = hmac.new(key, struct.pack(">Q", counter), sha1).digest()
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(code % (10 ** digits)).zfill(digits)


def totp(secret_b32: str, at: float | None = None, step: int = 30, digits: int = 6) -> str:
    now = time.time() if at is None else at
    return _hotp(secret_b32, int(now // step), digits)


def verify(secret_b32: str, code: str, window: int = 1, at: float | None = None) -> bool:
    """True if `code` is valid now or within ±`window` steps (clock drift)."""
    code = "".join(ch for ch in str(code or "") if ch.isdigit())
    if len(code) != 6:
        return False
    now = time.time() if at is None else at
    for drift in range(-window, window + 1):
        if hmac.compare_digest(totp(secret_b32, at=now + drift * 30), code):
            return True
    return False


def otpauth_uri(secret_b32: str, account: str, issuer: str = "Nagarik Sahayak") -> str:
    """The URI an authenticator app scans (shown as a QR by the client)."""
    label = quote(f"{issuer}:{account}")
    return f"otpauth://totp/{label}?secret={secret_b32}&issuer={quote(issuer)}&algorithm=SHA1&digits=6&period=30"
