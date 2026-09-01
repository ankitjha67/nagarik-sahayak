"""Verification routes — validate, check eligibility, and screen for abuse."""
import logging

from fastapi import HTTPException

from routes import api_router
from data.gov_forms import get_by_name, get_catalog
from services import application_guard

logger = logging.getLogger(__name__)


@api_router.post("/verify/fields")
async def verify_fields(req: dict):
    """Validate submitted field values without deciding eligibility.

    Body: {"profile": {...}, "scheme_name": "..." (optional)}

    Used for inline form feedback, so a citizen fixes a mistyped Aadhaar while
    filling the form rather than after submission.
    """
    from validation import validate_profile

    profile = req.get("profile") or {}
    if not isinstance(profile, dict):
        raise HTTPException(status_code=400, detail="profile must be an object")

    fields = []
    scheme_name = req.get("scheme_name")
    if scheme_name:
        entry = get_by_name(scheme_name)
        if entry:
            fields = entry.get("extractedFields", [])

    return validate_profile(profile, fields).as_dict()


@api_router.post("/verify/eligibility")
async def verify_eligibility(req: dict):
    """Evaluate a profile against one scheme, or all catalog schemes.

    Body: {"profile": {...}, "scheme_name": "..." (optional)}
    """
    from eligibility_engine import evaluate_all, evaluate_scheme

    profile = req.get("profile") or {}
    if not isinstance(profile, dict):
        raise HTTPException(status_code=400, detail="profile must be an object")

    scheme_name = req.get("scheme_name")
    if scheme_name:
        entry = get_by_name(scheme_name)
        if not entry:
            raise HTTPException(status_code=404, detail=f"'{scheme_name}' not in catalog")
        return evaluate_scheme(profile, entry).as_dict()

    results = [r.as_dict() for r in evaluate_all(profile)]
    return {
        "results": results,
        "eligible_count": sum(1 for r in results if r["eligible"]),
        "total": len(results),
    }


@api_router.post("/verify/application")
async def verify_application(req: dict):
    """Full gate: validation + eligibility + abuse screening for one scheme.

    Body: {"profile": {...}, "scheme_name": "...", "user_id": "..." (optional)}

    Omitting user_id skips cross-applicant checks, which is the right behaviour
    for an anonymous pre-check: a citizen can see whether they qualify before
    creating an account.
    """
    profile = req.get("profile") or {}
    scheme_name = (req.get("scheme_name") or "").strip()
    if not isinstance(profile, dict):
        raise HTTPException(status_code=400, detail="profile must be an object")
    if not scheme_name:
        raise HTTPException(status_code=400, detail="scheme_name is required")

    entry = get_by_name(scheme_name)
    if not entry:
        raise HTTPException(status_code=404, detail=f"'{scheme_name}' not in catalog")

    user_id = req.get("user_id") or ""
    result = await application_guard.evaluate_application(
        profile=profile, scheme=entry, user_id=user_id,
        check_fraud=bool(user_id),
    )
    return result.as_dict()


@api_router.post("/verify/screen-all")
async def screen_all_schemes(req: dict):
    """Run the full gate against every catalog scheme.

    Answers the question citizens actually have — "what am I entitled to?" —
    rather than making them guess a scheme name first.
    """
    profile = req.get("profile") or {}
    if not isinstance(profile, dict):
        raise HTTPException(status_code=400, detail="profile must be an object")
    user_id = req.get("user_id") or ""

    approved, blocked, incomplete = [], [], []
    for entry in get_catalog():
        result = await application_guard.evaluate_application(
            profile=profile, scheme=entry, user_id=user_id,
            check_fraud=bool(user_id),
        )
        summary = {
            "scheme": result.scheme,
            "outcome": result.outcome.value,
            "benefit": entry.get("eligibilityCriteria", {}).get("benefit", ""),
            "reasons_en": result.reasons_en,
            "reasons_hi": result.reasons_hi,
            "risk_score": result.risk.get("risk_score", 0),
        }
        if result.may_issue_form:
            approved.append(summary)
        elif result.outcome.value == "incomplete":
            incomplete.append(summary)
        else:
            blocked.append(summary)

    return {
        "eligible": approved,
        "not_eligible": blocked,
        "needs_more_info": incomplete,
        "eligible_count": len(approved),
        "total_screened": len(get_catalog()),
    }
