"""Retention and erasure — sections 8(6) and 12.

Section 8(6) obliges a Data Fiduciary to erase personal data once the purpose is
no longer served or consent is withdrawn, unless another law requires retention.
Section 12 gives the citizen the right to demand that erasure directly.

Two decisions worth stating, because both cut against the obvious reading:

**Erasure is per-field, not per-row.** Retention periods differ by purpose — a
mobile number supports alerts the citizen still wants long after the Aadhaar
that supported one application should be gone. Deleting whole rows on the
earliest expiry would destroy data the citizen expects to keep; keeping whole
rows until the latest expiry would retain an Aadhaar for years past its purpose.
Neither is defensible, so expiry is evaluated field by field.

**Erasure is never automatic in the request path.** A compliance sweep that
silently deletes an in-progress application because a clock ran over would harm
the citizen more than the retention breach it cured. Expiry is *reported* by the
engine and *executed* by an explicit operation — a scheduled job or the
citizen's own section 12 request.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from dpdp import registry

logger = logging.getLogger(__name__)

# Retained despite erasure: the Act's own carve-out for data another law
# requires. Kept deliberately narrow — it is the obvious place for an
# over-broad exception to quietly defeat the right.
LEGAL_HOLD_FIELDS = frozenset({
    # Needed to authenticate the person and to honour a later grievance or
    # appeal about a decision already taken.
    "phone",
})


def expired_fields(profile: dict, created_at: datetime | None,
                   now: datetime | None = None) -> list[tuple[str, int]]:
    """Fields past their retention period, with how many days overdue."""
    if not created_at or not profile:
        return []
    now = now or datetime.now(timezone.utc)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    age_days = (now - created_at).days

    out = []
    for key, value in profile.items():
        if value in (None, "") or key in LEGAL_HOLD_FIELDS:
            continue
        rec = registry.record_for(key)
        if rec and age_days > rec.retention_days:
            out.append((key, age_days - rec.retention_days))
    return sorted(out, key=lambda x: -x[1])


def fields_for_withdrawn_purposes(profile: dict, consented: set[str]) -> list[str]:
    """Fields whose every purpose has lost consent.

    A field serving several purposes survives while any one of them still has
    consent — erasing it would break a service the citizen still wants.
    """
    out = []
    for key, value in (profile or {}).items():
        if value in (None, "") or key in LEGAL_HOLD_FIELDS:
            continue
        rec = registry.record_for(key)
        if not rec:
            continue
        if rec.basis != registry.LawfulBasis.CONSENT:
            continue          # a s7 legitimate use does not depend on consent
        if not any(p.value in consented for p in rec.purposes):
            out.append(key)
    return sorted(out)


async def erase_fields(user_id: str, fields: list[str], *, reason: str = "") -> dict:
    """Remove specific fields from a citizen's stored profiles.

    Fields are removed rather than blanked, so nothing is left implying the
    citizen declined to answer when in fact the data was erased on request.
    """
    from database import prisma
    from prisma import Json
    import identity_index

    if not fields:
        return {"erased": [], "skipped": []}

    user = await prisma.user.find_unique(where={"id": user_id})
    if not user:
        return {"error": "User not found"}

    def _load(raw):
        if not raw:
            return {}
        try:
            return json.loads(raw) if isinstance(raw, str) else dict(raw)
        except (ValueError, TypeError):
            return {}

    full = _load(user.fullProfile)
    basic = _load(user.profile)

    erased, skipped = [], []
    for f in fields:
        if f in LEGAL_HOLD_FIELDS:
            skipped.append({"field": f, "reason": "retained under legal obligation"})
            continue
        hit = False
        if f in full:
            full.pop(f); hit = True
        if f in basic:
            basic.pop(f); hit = True
        if hit:
            erased.append(f)

    # Identity fingerprints are derived from the profile, so they must be
    # recomputed — leaving a digest of an erased Aadhaar would keep the citizen
    # matchable by a value they asked to have removed.
    data = identity_index.merge_into_update(
        {"fullProfile": Json(full), "profile": json.dumps(basic, ensure_ascii=False)},
        full,
    )
    await prisma.user.update(where={"id": user_id}, data=data)

    logger.info("Erased %d field(s) for %s (%s)", len(erased), user_id, reason or "no reason given")
    return {"erased": erased, "skipped": skipped,
            "remaining_fields": len([v for v in full.values() if v not in (None, "")])}


async def erase_all(user_id: str, *, reason: str = "s12 erasure request") -> dict:
    """Erase everything erasable for one citizen, across all stores.

    Chat logs and generated documents are included: a filled application form
    sitting on disk contains the same Aadhaar as the profile row, and erasing
    only the row would be a hollow compliance.
    """
    from database import prisma
    from config import PDF_DIR, AUDIO_DIR

    result = {"profile_fields": 0, "chat_logs": 0, "artefacts": 0, "errors": []}

    user = await prisma.user.find_unique(where={"id": user_id})
    if not user:
        return {"error": "User not found"}

    profile = {}
    for raw in (user.fullProfile, user.profile):
        if raw:
            try:
                profile.update(json.loads(raw) if isinstance(raw, str) else dict(raw))
            except (ValueError, TypeError):
                pass

    erasable = [k for k in profile if k not in LEGAL_HOLD_FIELDS and not k.startswith("_")]
    if erasable:
        out = await erase_fields(user_id, erasable, reason=reason)
        result["profile_fields"] = len(out.get("erased", []))

    try:
        logs = await prisma.chatlog.find_many(where={"userId": user_id})
        await prisma.chatlog.delete_many(where={"userId": user_id})
        result["chat_logs"] = len(logs)
    except Exception as e:
        result["errors"].append(f"chat logs: {e}")

    # Generated documents, and the ownership rows that point at them.
    try:
        owned = await prisma.artefactowner.find_many(where={"userId": user_id})
        for row in owned:
            for directory, suffix in ((PDF_DIR, ".pdf"), (AUDIO_DIR, ".webm")):
                path = directory / f"{row.artefactId}{suffix}"
                try:
                    if path.exists():
                        path.unlink()
                        result["artefacts"] += 1
                except OSError as e:
                    result["errors"].append(f"{path.name}: {e}")
            try:
                await prisma.artefactowner.delete(where={"id": row.id})
            except Exception:
                pass
    except Exception as e:
        result["errors"].append(f"artefacts: {e}")

    logger.info("Full erasure for %s: %s", user_id, result)
    return result


async def sweep(dry_run: bool = True, limit: int = 500) -> dict:
    """Find, and optionally erase, data held past its retention period.

    Intended to run as a scheduled job. Defaults to a dry run so the first
    thing an operator sees is what *would* be deleted.
    """
    from database import prisma

    users = await prisma.user.find_many()
    report = {"scanned": 0, "users_with_expiry": 0, "fields_expired": 0,
              "erased": 0, "dry_run": dry_run, "details": []}

    for user in users[:limit]:
        report["scanned"] += 1
        profile = {}
        for raw in (user.fullProfile, user.profile):
            if raw:
                try:
                    profile.update(json.loads(raw) if isinstance(raw, str) else dict(raw))
                except (ValueError, TypeError):
                    pass

        expired = expired_fields(profile, getattr(user, "createdAt", None))
        if not expired:
            continue
        report["users_with_expiry"] += 1
        report["fields_expired"] += len(expired)
        report["details"].append({
            "user_id": user.id,
            "fields": [{"field": f, "days_overdue": d} for f, d in expired[:10]],
        })
        if not dry_run:
            out = await erase_fields(user.id, [f for f, _ in expired],
                                     reason="s8(6) retention sweep")
            report["erased"] += len(out.get("erased", []))

    return report
