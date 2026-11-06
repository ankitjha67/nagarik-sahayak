"""Access tokens, refresh rotation and session revocation.

Access token: a signed JWT (HS256) carrying the user id, role and session id,
valid for at most 60 minutes. It is checked without a database round-trip
except for one cheap, briefly cached lookup that confirms the session has not
been revoked, so a logout or a theft response takes effect within seconds
rather than at expiry.

Refresh token: 48 random bytes, handed to the client once and stored only as
a SHA-256 hash. Every refresh issues a new one and retires the old hash into
the session's history. A refresh with a retired hash can only mean the token
was copied, so the whole session is revoked and the legitimate client is
asked to sign in again.
"""
from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass
from typing import Optional

import jwt

from auth import settings
from auth.store import SessionStore, get_store

ALGORITHM = "HS256"


class TokenError(Exception):
    """A token that must not be honoured, with a reason safe to show."""

    def __init__(self, reason: str, status: int = 401):
        super().__init__(reason)
        self.reason = reason
        self.status = status


@dataclass(frozen=True)
class Claims:
    user_id: str
    role: str
    sid: str
    phone: str = ""


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _new_refresh() -> str:
    return secrets.token_urlsafe(48)


def issue_access(claims: Claims, ttl: Optional[int] = None) -> str:
    now = int(time.time())
    payload = {
        "sub": claims.user_id,
        "role": claims.role,
        "sid": claims.sid,
        "iat": now,
        "exp": now + (ttl or settings.access_ttl_seconds()),
        "jti": secrets.token_hex(8),
        "iss": "nagarik-sahayak",
    }
    return jwt.encode(payload, settings.jwt_secret(), algorithm=ALGORITHM)


def decode_access(token: str) -> Claims:
    try:
        data = jwt.decode(
            token, settings.jwt_secret(), algorithms=[ALGORITHM],
            issuer="nagarik-sahayak",
            options={"require": ["exp", "sub", "sid", "iat"]},
        )
    except jwt.ExpiredSignatureError:
        raise TokenError("Session expired. Please sign in again.")
    except jwt.InvalidTokenError:
        raise TokenError("Invalid token.")
    return Claims(user_id=str(data["sub"]), role=str(data.get("role", "citizen")),
                  sid=str(data["sid"]), phone="")


# A short cache of "is this session still active?" so the hot path does not
# hit the database on every request. Revocation lands within this many seconds.
_ACTIVE_TTL = 10.0
_active_cache: dict[str, tuple[float, bool]] = {}


def _cache_set(sid: str, active: bool) -> None:
    if len(_active_cache) > 10000:
        _active_cache.clear()
    _active_cache[sid] = (time.time() + _ACTIVE_TTL, active)


def forget_session(sid: str) -> None:
    _active_cache.pop(sid, None)


async def session_active(sid: str, store: Optional[SessionStore] = None) -> bool:
    hit = _active_cache.get(sid)
    if hit and hit[0] > time.time():
        return hit[1]
    store = store or get_store()
    rec = await store.session_get(sid)
    active = bool(rec) and not rec.get("revoked") and rec.get("expires_at", 0) > time.time()
    _cache_set(sid, active)
    return active


async def create_session(user_id: str, role: str, phone: str = "",
                         user_agent: str = "", ip: str = "",
                         store: Optional[SessionStore] = None) -> dict:
    """Start a session: returns access, refresh and the session id."""
    store = store or get_store()
    sid = secrets.token_hex(16)
    refresh = _new_refresh()
    now = time.time()
    await store.session_create({
        "sid": sid, "user_id": user_id, "role": role, "phone_last4": phone[-4:],
        "refresh_hash": hash_token(refresh), "prior_hashes": [],
        "created_at": now, "last_seen": now, "expires_at": now + settings.refresh_ttl_seconds(),
        "revoked": False, "user_agent": user_agent[:200], "ip": ip,
    })
    _cache_set(sid, True)
    access = issue_access(Claims(user_id=user_id, role=role, sid=sid, phone=phone))
    return {"access_token": access, "refresh_token": refresh, "sid": sid,
            "token_type": "bearer", "expires_in": settings.access_ttl_seconds(), "role": role}


async def refresh_session(refresh_token: str, store: Optional[SessionStore] = None) -> dict:
    """Rotate the refresh token and issue a new access token.

    Reuse of a retired refresh token revokes the session: the only way an old
    token comes back is if it was copied.
    """
    store = store or get_store()
    h = hash_token(refresh_token or "")
    rec = await store.session_find_by_refresh(h)
    if rec is None:
        stolen = await store.session_find_by_prior_refresh(h)
        if stolen:
            await store.session_update(stolen["sid"], {"revoked": True, "revoked_reason": "refresh_reuse"})
            forget_session(stolen["sid"])
            raise TokenError("This session was revoked for your safety. Please sign in again.")
        raise TokenError("Invalid refresh token.")
    if rec.get("revoked"):
        raise TokenError("Session revoked. Please sign in again.")
    if rec.get("expires_at", 0) <= time.time():
        raise TokenError("Session expired. Please sign in again.")

    new_refresh = _new_refresh()
    await store.session_update(rec["sid"], {
        "refresh_hash": hash_token(new_refresh), "last_seen": time.time(),
    }, push_prior=h)
    access = issue_access(Claims(user_id=rec["user_id"], role=rec.get("role", "citizen"), sid=rec["sid"]))
    return {"access_token": access, "refresh_token": new_refresh, "sid": rec["sid"],
            "token_type": "bearer", "expires_in": settings.access_ttl_seconds(),
            "role": rec.get("role", "citizen")}


async def revoke_session(sid: str, reason: str = "logout", store: Optional[SessionStore] = None) -> None:
    store = store or get_store()
    await store.session_update(sid, {"revoked": True, "revoked_reason": reason})
    forget_session(sid)


async def revoke_all(user_id: str, store: Optional[SessionStore] = None) -> int:
    store = store or get_store()
    n = await store.session_revoke_user(user_id)
    _active_cache.clear()
    return n
