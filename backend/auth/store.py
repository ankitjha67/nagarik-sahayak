"""Where sessions, one-time codes, operator consents and the audit chain live.

Two implementations behind one interface: Mongo (through the Motor client the
app already holds for OTP sessions) in a running service, and memory in unit
tests or when no database is configured. Nothing here knows about HTTP.

Every record is a plain dict so the two stores stay interchangeable and the
Mongo one needs no schema migration.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Optional


class SessionStore:
    """The operations the auth layer needs. Subclasses implement all of them."""

    # sessions -----------------------------------------------------------
    async def session_create(self, record: dict) -> None: ...
    async def session_get(self, sid: str) -> Optional[dict]: ...
    async def session_find_by_refresh(self, refresh_hash: str) -> Optional[dict]: ...
    async def session_find_by_prior_refresh(self, refresh_hash: str) -> Optional[dict]: ...
    async def session_update(self, sid: str, fields: dict, push_prior: Optional[str] = None) -> None: ...
    async def session_revoke_user(self, user_id: str) -> int: ...

    # one-time codes -----------------------------------------------------
    async def otp_put(self, phone: str, record: dict) -> None: ...
    async def otp_get(self, phone: str) -> Optional[dict]: ...
    async def otp_update(self, phone: str, fields: dict) -> None: ...
    async def otp_delete(self, phone: str) -> None: ...

    # operator consents --------------------------------------------------
    async def consent_put(self, record: dict) -> None: ...
    async def consent_get(self, operator_id: str, citizen_id: str) -> Optional[dict]: ...

    # mfa secrets --------------------------------------------------------
    async def mfa_get(self, user_id: str) -> Optional[dict]: ...
    async def mfa_put(self, user_id: str, record: dict) -> None: ...

    # audit chain --------------------------------------------------------
    async def audit_last(self) -> Optional[dict]: ...
    async def audit_append(self, record: dict) -> None: ...
    async def audit_tail(self, limit: int = 100) -> list[dict]: ...


class MemorySessionStore(SessionStore):
    """Process-local. Used by tests and by a service started without Mongo."""

    def __init__(self) -> None:
        self.sessions: dict[str, dict] = {}
        self.otps: dict[str, dict] = {}
        self.consents: dict[tuple[str, str], dict] = {}
        self.mfa: dict[str, dict] = {}
        self.audit: list[dict] = []
        self._lock = asyncio.Lock()

    async def session_create(self, record):
        self.sessions[record["sid"]] = dict(record)

    async def session_get(self, sid):
        rec = self.sessions.get(sid)
        return dict(rec) if rec else None

    async def session_find_by_refresh(self, refresh_hash):
        for rec in self.sessions.values():
            if rec.get("refresh_hash") == refresh_hash:
                return dict(rec)
        return None

    async def session_find_by_prior_refresh(self, refresh_hash):
        for rec in self.sessions.values():
            if refresh_hash in rec.get("prior_hashes", []):
                return dict(rec)
        return None

    async def session_update(self, sid, fields, push_prior=None):
        rec = self.sessions.get(sid)
        if rec is None:
            return
        rec.update(fields)
        if push_prior:
            rec.setdefault("prior_hashes", []).append(push_prior)

    async def session_revoke_user(self, user_id):
        n = 0
        for rec in self.sessions.values():
            if rec.get("user_id") == user_id and not rec.get("revoked"):
                rec["revoked"] = True
                n += 1
        return n

    async def otp_put(self, phone, record):
        self.otps[phone] = dict(record)

    async def otp_get(self, phone):
        rec = self.otps.get(phone)
        return dict(rec) if rec else None

    async def otp_update(self, phone, fields):
        if phone in self.otps:
            self.otps[phone].update(fields)

    async def otp_delete(self, phone):
        self.otps.pop(phone, None)

    async def consent_put(self, record):
        self.consents[(record["operator_id"], record["citizen_id"])] = dict(record)

    async def consent_get(self, operator_id, citizen_id):
        rec = self.consents.get((operator_id, citizen_id))
        return dict(rec) if rec else None

    async def mfa_get(self, user_id):
        rec = self.mfa.get(user_id)
        return dict(rec) if rec else None

    async def mfa_put(self, user_id, record):
        self.mfa[user_id] = dict(record)

    async def audit_last(self):
        return dict(self.audit[-1]) if self.audit else None

    async def audit_append(self, record):
        async with self._lock:
            self.audit.append(dict(record))

    async def audit_tail(self, limit=100):
        return [dict(r) for r in self.audit[-limit:]]


class MotorSessionStore(SessionStore):
    """Mongo through Motor. Collections: auth_sessions, otp_sessions,
    operator_consents, auth_mfa, auth_audit."""

    def __init__(self, db: Any) -> None:
        self.db = db
        self._indexed = False

    async def _ensure_indexes(self) -> None:
        if self._indexed:
            return
        self._indexed = True
        try:
            await self.db.auth_sessions.create_index("sid", unique=True)
            await self.db.auth_sessions.create_index("refresh_hash")
            await self.db.auth_sessions.create_index("prior_hashes")
            await self.db.auth_sessions.create_index("user_id")
            await self.db.otp_sessions.create_index("phone", unique=True)
            await self.db.operator_consents.create_index([("operator_id", 1), ("citizen_id", 1)], unique=True)
            await self.db.auth_mfa.create_index("user_id", unique=True)
            await self.db.auth_audit.create_index("seq", unique=True)
        except Exception:  # noqa: BLE001 - indexes are an optimisation, never a blocker
            pass

    async def session_create(self, record):
        await self._ensure_indexes()
        await self.db.auth_sessions.insert_one(dict(record))

    async def session_get(self, sid):
        return await self.db.auth_sessions.find_one({"sid": sid}, {"_id": 0})

    async def session_find_by_refresh(self, refresh_hash):
        return await self.db.auth_sessions.find_one({"refresh_hash": refresh_hash}, {"_id": 0})

    async def session_find_by_prior_refresh(self, refresh_hash):
        return await self.db.auth_sessions.find_one({"prior_hashes": refresh_hash}, {"_id": 0})

    async def session_update(self, sid, fields, push_prior=None):
        update: dict = {"$set": dict(fields)}
        if push_prior:
            update["$push"] = {"prior_hashes": push_prior}
        await self.db.auth_sessions.update_one({"sid": sid}, update)

    async def session_revoke_user(self, user_id):
        res = await self.db.auth_sessions.update_many(
            {"user_id": user_id, "revoked": {"$ne": True}}, {"$set": {"revoked": True}})
        return res.modified_count

    async def otp_put(self, phone, record):
        await self._ensure_indexes()
        await self.db.otp_sessions.replace_one({"phone": phone}, dict(record), upsert=True)

    async def otp_get(self, phone):
        return await self.db.otp_sessions.find_one({"phone": phone}, {"_id": 0})

    async def otp_update(self, phone, fields):
        await self.db.otp_sessions.update_one({"phone": phone}, {"$set": dict(fields)})

    async def otp_delete(self, phone):
        await self.db.otp_sessions.delete_one({"phone": phone})

    async def consent_put(self, record):
        await self._ensure_indexes()
        await self.db.operator_consents.replace_one(
            {"operator_id": record["operator_id"], "citizen_id": record["citizen_id"]},
            dict(record), upsert=True)

    async def consent_get(self, operator_id, citizen_id):
        return await self.db.operator_consents.find_one(
            {"operator_id": operator_id, "citizen_id": citizen_id}, {"_id": 0})

    async def mfa_get(self, user_id):
        return await self.db.auth_mfa.find_one({"user_id": user_id}, {"_id": 0})

    async def mfa_put(self, user_id, record):
        await self._ensure_indexes()
        await self.db.auth_mfa.replace_one({"user_id": user_id}, dict(record), upsert=True)

    async def audit_last(self):
        cur = self.db.auth_audit.find({}, {"_id": 0}).sort("seq", -1).limit(1)
        rows = await cur.to_list(length=1)
        return rows[0] if rows else None

    async def audit_append(self, record):
        await self._ensure_indexes()
        await self.db.auth_audit.insert_one(dict(record))

    async def audit_tail(self, limit=100):
        cur = self.db.auth_audit.find({}, {"_id": 0}).sort("seq", -1).limit(limit)
        rows = await cur.to_list(length=limit)
        return list(reversed(rows))


_store: Optional[SessionStore] = None


def get_store() -> SessionStore:
    """The configured store: Mongo when the app has a Motor client, else memory."""
    global _store
    if _store is None:
        try:
            from database import motor_db
        except Exception:  # noqa: BLE001
            motor_db = None
        _store = MotorSessionStore(motor_db) if motor_db is not None else MemorySessionStore()
    return _store


def set_store(store: Optional[SessionStore]) -> None:
    """Swap the store (tests pass a MemorySessionStore; None resets)."""
    global _store
    _store = store


def now() -> float:
    return time.time()
