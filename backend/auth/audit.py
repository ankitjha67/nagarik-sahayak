"""A hash-chained record of authentication events.

Each entry carries the hash of the one before it, so a record cannot be
altered or removed without breaking every hash that follows. `verify_chain`
walks the tail and reports the first break. Events: otp_issued,
otp_failed, login, login_mfa_failed, refresh, refresh_reuse, logout, denied,
consent_recorded, mfa_enrolled.

Written in the request path but never allowed to fail it: an audit store
that is down is logged, not surfaced to the citizen.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Optional

from auth.store import SessionStore, get_store

logger = logging.getLogger(__name__)

GENESIS = "0" * 64


def _hash(prev: str, body: dict) -> str:
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256((prev + canonical).encode()).hexdigest()


async def record(event: str, actor: str = "", subject: str = "", ip: str = "",
                 detail: Optional[dict] = None, store: Optional[SessionStore] = None) -> Optional[dict]:
    store = store or get_store()
    try:
        last = await store.audit_last()
        prev = last["hash"] if last else GENESIS
        seq = (last["seq"] + 1) if last else 1
        body = {"seq": seq, "ts": round(time.time(), 3), "event": event, "actor": actor,
                "subject": subject, "ip": ip, "detail": detail or {}}
        entry = {**body, "prev_hash": prev, "hash": _hash(prev, body)}
        await store.audit_append(entry)
        return entry
    except Exception as e:  # noqa: BLE001
        logger.error("auth audit write failed: %s", e)
        return None


async def verify_chain(limit: int = 1000, store: Optional[SessionStore] = None) -> dict:
    """Recompute the tail of the chain; report the first broken link, if any."""
    store = store or get_store()
    rows = await store.audit_tail(limit)
    prev = rows[0]["prev_hash"] if rows else GENESIS
    for row in rows:
        body = {k: row[k] for k in ("seq", "ts", "event", "actor", "subject", "ip", "detail")}
        if row.get("prev_hash") != prev or _hash(prev, body) != row.get("hash"):
            return {"ok": False, "checked": len(rows), "broken_at_seq": row.get("seq")}
        prev = row["hash"]
    return {"ok": True, "checked": len(rows), "broken_at_seq": None}
