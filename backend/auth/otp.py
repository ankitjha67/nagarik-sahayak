"""One-time codes: hashed at rest, single-use, attempt-limited.

The code is six random digits from the OS entropy source. What is stored is
a salted SHA-256 of it, so a database read yields nothing usable. Five wrong
attempts lock the number for fifteen minutes; a correct code is consumed on
first use; an expired code is refused. Comparison is constant-time.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass
from typing import Optional

from auth import settings
from auth.store import SessionStore, get_store


class OtpError(Exception):
    def __init__(self, reason: str, status: int = 401, retry_after: int = 0):
        super().__init__(reason)
        self.reason = reason
        self.status = status
        self.retry_after = retry_after


@dataclass
class Issued:
    code: str            # only returned so the caller can hand it to the SMS provider
    mocked: bool
    expires_in: int


def _digest(salt: str, phone: str, code: str) -> str:
    return hashlib.sha256(f"{salt}:{phone}:{code}".encode()).hexdigest()


def _generate() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


async def issue(phone: str, store: Optional[SessionStore] = None) -> Issued:
    store = store or get_store()
    existing = await store.otp_get(phone)
    now = time.time()
    if existing and existing.get("locked_until", 0) > now:
        raise OtpError("Too many attempts. Try again later.", 429,
                       int(existing["locked_until"] - now))
    mock = settings.otp_mock_code()
    code = mock or _generate()
    salt = secrets.token_hex(8)
    await store.otp_put(phone, {
        "phone": phone, "salt": salt, "digest": _digest(salt, phone, code),
        "created_at": now, "expires_at": now + settings.otp_ttl_seconds(),
        "attempts": 0, "locked_until": 0,
    })
    return Issued(code=code, mocked=bool(mock), expires_in=settings.otp_ttl_seconds())


async def verify(phone: str, code: str, store: Optional[SessionStore] = None) -> None:
    """Consume the code or raise OtpError with a status the route can return."""
    store = store or get_store()
    rec = await store.otp_get(phone)
    now = time.time()
    if not rec:
        raise OtpError("No code was requested for this number. Request one first.", 401)
    if rec.get("locked_until", 0) > now:
        raise OtpError("Too many attempts. Try again later.", 429, int(rec["locked_until"] - now))
    if rec.get("expires_at", 0) <= now:
        await store.otp_delete(phone)
        raise OtpError("The code has expired. Request a new one.", 401)

    code = "".join(ch for ch in str(code or "") if ch.isdigit())
    ok = hmac.compare_digest(_digest(rec["salt"], phone, code), rec["digest"])
    if not ok:
        attempts = int(rec.get("attempts", 0)) + 1
        fields: dict = {"attempts": attempts}
        if attempts >= settings.otp_max_attempts():
            fields["locked_until"] = now + settings.otp_lock_seconds()
            await store.otp_update(phone, fields)
            raise OtpError("Too many wrong codes. This number is locked for a while.", 429,
                           settings.otp_lock_seconds())
        await store.otp_update(phone, fields)
        left = settings.otp_max_attempts() - attempts
        raise OtpError(f"Wrong code. {left} attempt{'s' if left != 1 else ''} left.", 401)

    # Single use.
    await store.otp_delete(phone)
