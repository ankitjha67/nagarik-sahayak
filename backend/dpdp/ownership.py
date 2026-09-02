"""Ownership checks for citizen-generated artefacts.

Before this existed, /api/pdf/{id} served any filled application form to anyone
holding the identifier — Aadhaar, bank account and declared income included —
with no check that the requester was the applicant. The identifiers are UUID4s,
so the exposure was not trivially enumerable, but "hard to guess" is not an
access control, and section 8(4) requires reasonable security safeguards rather
than obscurity.

Ownership is recorded when an artefact is produced and checked when it is
served. The record is a small side table rather than a field on Application,
because artefacts are also generated outside the application flow (eligibility
reports, uploaded PDFs, voice notes) and all of them need the same guarantee.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class ArtefactKind:
    PDF = "pdf"
    AUDIO = "audio"


async def record_owner(artefact_id: str, user_id: str, kind: str = ArtefactKind.PDF) -> None:
    """Note who an artefact belongs to. Best-effort: never blocks generation.

    If this write fails the artefact still exists but has no owner, and
    `is_owner` will then refuse it to everyone — failing closed, which is the
    right direction for a document containing an Aadhaar.
    """
    if not artefact_id or not user_id:
        return
    try:
        from database import prisma
        await prisma.artefactowner.create(data={
            "artefactId": artefact_id, "userId": user_id, "kind": kind,
        })
    except Exception as e:
        logger.warning(f"Could not record ownership of {kind} {artefact_id}: {e}")


async def is_owner(artefact_id: str, user_id: str) -> bool:
    """True if `user_id` owns this artefact."""
    if not artefact_id or not user_id:
        return False
    try:
        from database import prisma
        row = await prisma.artefactowner.find_first(
            where={"artefactId": artefact_id, "userId": user_id})
        return row is not None
    except Exception as e:
        logger.error(f"Ownership check failed for {artefact_id}: {e}")
        return False


async def owner_of(artefact_id: str) -> str | None:
    try:
        from database import prisma
        row = await prisma.artefactowner.find_first(
            where={"artefactId": artefact_id})
        return row.userId if row else None
    except Exception:
        return None


async def assert_access(artefact_id: str, user_id: str, kind: str = ArtefactKind.PDF):
    """Raise 403/404 unless `user_id` may read this artefact.

    An unowned artefact returns 404 rather than 403. Distinguishing "exists but
    is not yours" from "does not exist" would confirm the existence of another
    citizen's document to anyone probing identifiers.
    """
    from fastapi import HTTPException

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Sign in to download this document.",
        )

    owner = await owner_of(artefact_id)
    if owner is None:
        # Either unknown, or predating the ownership table. Both fail closed:
        # a legacy document containing an Aadhaar must not stay world-readable
        # merely because it was created before this check existed.
        raise HTTPException(status_code=404, detail="Document not found.")
    if owner != user_id:
        logger.warning(
            "Blocked cross-user access: user %s requested %s %s owned by another user",
            user_id, kind, artefact_id,
        )
        raise HTTPException(status_code=404, detail="Document not found.")
