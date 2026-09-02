"""Reviewer queue routes — work the pile of applications flagged for checking.

All endpoints except the citizen-facing status check are admin-gated: this data
describes suspicion about named people, and must not be browsable by applicants.
"""
import logging

from fastapi import HTTPException, Request

from routes import api_router
from config import ADMIN_SECRET
from services import review_queue
from services.review_queue import CaseStatus, TransitionError

logger = logging.getLogger(__name__)


def _require_reviewer(request: Request) -> str:
    """Gate on the admin secret and return the reviewer's identity.

    X-Reviewer-Id is recorded against every decision, so an approval or refusal
    can always be traced to a person rather than to "the system".
    """
    if not ADMIN_SECRET or request.headers.get("X-Admin-Secret", "") != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Reviewer credentials required")
    reviewer_id = request.headers.get("X-Reviewer-Id", "").strip()
    if not reviewer_id:
        raise HTTPException(
            status_code=400,
            detail="X-Reviewer-Id header is required so decisions are attributable",
        )
    return reviewer_id


@api_router.get("/review/queue")
async def review_queue_list(
    request: Request, status: str = "pending", limit: int = 50, offset: int = 0,
):
    """List flagged applications, highest risk and longest waiting first."""
    _require_reviewer(request)
    if status and status not in {s.value for s in CaseStatus}:
        raise HTTPException(status_code=400, detail=f"Unknown status '{status}'")
    try:
        return await review_queue.list_cases(status=status, limit=limit, offset=offset)
    except Exception as e:
        logger.error(f"Review queue listing failed: {e}")
        raise HTTPException(status_code=503, detail=str(e))


@api_router.get("/review/case/{case_id}")
async def review_case_detail(case_id: str, request: Request):
    """Full detail for one case, including every risk signal that raised it."""
    _require_reviewer(request)
    try:
        case = await review_queue.get_case(case_id)
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
    if not case:
        raise HTTPException(status_code=404, detail="Review case not found")
    return case


@api_router.post("/review/case/{case_id}/decide")
async def review_case_decide(case_id: str, request: Request, req: dict):
    """Approve or reject a flagged application.

    Body: {"decision": "approved" | "rejected", "note": "..."}
    A rejection must carry a note — a citizen refused on suspicion needs
    something to appeal against.
    """
    reviewer_id = _require_reviewer(request)
    decision = (req.get("decision") or "").strip()
    if decision not in (CaseStatus.APPROVED.value, CaseStatus.REJECTED.value):
        raise HTTPException(
            status_code=400,
            detail="decision must be 'approved' or 'rejected'",
        )
    try:
        return await review_queue.decide(
            case_id, decision, reviewer_id, req.get("note", ""),
        )
    except TransitionError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"Review decision failed for {case_id}: {e}")
        raise HTTPException(status_code=503, detail=str(e))


@api_router.post("/review/case/{case_id}/reopen")
async def review_case_reopen(case_id: str, request: Request, req: dict | None = None):
    """Return a decided case to the queue, recording why."""
    reviewer_id = _require_reviewer(request)
    try:
        return await review_queue.reopen(
            case_id, reviewer_id, (req or {}).get("note", ""),
        )
    except TransitionError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@api_router.get("/review/my-cases/{user_id}")
async def my_review_cases(user_id: str):
    """A citizen's own cases, so the app can say a check is under way.

    Not admin-gated — people are entitled to know their application is being
    verified. Only status and timing are returned: the underlying risk signals
    stay internal, since disclosing them would tell a genuine fraudster exactly
    which behaviour to change.
    """
    try:
        cases = await review_queue.cases_for_user(user_id)
    except Exception as e:
        logger.error(f"Citizen case lookup failed: {e}")
        return {"cases": [], "count": 0}

    return {
        "cases": [{
            "scheme": c["schemeName"],
            "status": c["status"],
            "submitted_at": c["createdAt"],
            "reviewed_at": c["reviewedAt"],
            # A refusal reason is shown; an approval needs no explanation.
            "note": c["reviewerNote"] if c["status"] == CaseStatus.REJECTED.value else "",
            "message_en": {
                "pending": "Your application is being verified.",
                "approved": "Verification complete — your application may proceed.",
                "rejected": "Your application could not be verified.",
            }.get(c["status"], ""),
            "message_hi": {
                "pending": "आपके आवेदन का सत्यापन किया जा रहा है।",
                "approved": "सत्यापन पूर्ण — आपका आवेदन आगे बढ़ सकता है।",
                "rejected": "आपके आवेदन का सत्यापन नहीं हो सका।",
            }.get(c["status"], ""),
        } for c in cases],
        "count": len(cases),
    }
