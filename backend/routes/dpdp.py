"""DPDP Act routes — citizen rights, consent, and compliance reporting.

Split by audience, because the two have opposite access rules:

* Citizen-facing (consent, my-data, erasure, grievance) is authenticated as the
  data principal and never admin-gated. Making a person ask an administrator to
  exercise a statutory right would defeat it.
* Compliance reporting is admin-gated: it names fields and rows at risk across
  the whole estate, which is operational security information.
"""
import logging

from fastapi import HTTPException, Request

from routes import api_router
from config import ADMIN_SECRET
from dpdp import consent as consent_service
from dpdp import engine, registry, retention
from dpdp.registry import Purpose

logger = logging.getLogger(__name__)


def _require_admin(request: Request) -> None:
    if not ADMIN_SECRET or request.headers.get("X-Admin-Secret", "") != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Admin credentials required")


def _require_self(request: Request, user_id: str) -> None:
    """A citizen may act only on their own data.

    Without this, every rights endpoint becomes a way to read or erase another
    person's record simply by changing the id in the path.
    """
    caller = request.headers.get("X-User-Id", "").strip()
    if not caller:
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    if caller != user_id:
        raise HTTPException(status_code=403, detail="You may only access your own data.")


# ── Section 5: notice ────────────────────────────────────────────────────

@api_router.get("/dpdp/notice")
async def privacy_notice():
    """The section 5 notice: what is collected, why, and how to exercise rights.

    Public and unauthenticated — a person is entitled to read this *before*
    deciding whether to hand over anything.
    """
    return {
        "notice_version": consent_service.NOTICE_VERSION,
        "data_fiduciary": "Nagarik Sahayak",
        "purposes": registry.notice_summary(),
        "summary_en": (
            "We collect the details government schemes require, use them to "
            "check what you qualify for and to fill your application forms, and "
            "keep them only while your application can still be processed or "
            "contested. You can withdraw consent, see what we hold, correct it, "
            "or have it erased at any time."
        ),
        "summary_hi": (
            "हम वही विवरण एकत्र करते हैं जो सरकारी योजनाओं हेतु आवश्यक हैं, उनका "
            "उपयोग आपकी पात्रता जाँचने और आवेदन फॉर्म भरने के लिए करते हैं, और उन्हें "
            "केवल तब तक रखते हैं जब तक आपका आवेदन संसाधित या चुनौती दिया जा सके। "
            "आप कभी भी सहमति वापस ले सकते हैं, अपना डेटा देख सकते हैं, सुधार सकते हैं, "
            "या मिटवा सकते हैं।"
        ),
        "shared_with": consent_service._disclosure_register(),
        "your_rights": consent_service._rights_summary(),
        "grievance": {
            "how": "POST /api/dpdp/request with request_type=grievance",
            "escalation": "If unresolved, you may complain to the Data "
                          "Protection Board of India.",
        },
    }


# ── Section 6: consent ───────────────────────────────────────────────────

@api_router.get("/dpdp/consent/{user_id}")
async def get_consent(user_id: str, request: Request):
    _require_self(request, user_id)
    return await consent_service.consent_status(user_id)


@api_router.post("/dpdp/consent/{user_id}")
async def grant_consent(user_id: str, request: Request, req: dict):
    """Record consent for named purposes (s6).

    Body: {"purposes": [...], "language": "hi", "parental_consent": false}
    """
    _require_self(request, user_id)
    purposes = req.get("purposes") or []
    if not purposes:
        raise HTTPException(status_code=400, detail="At least one purpose is required")
    try:
        return await consent_service.grant(
            user_id, purposes,
            language=req.get("language", "hi"),
            parental=bool(req.get("parental_consent", False)),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Consent grant failed: {e}")
        raise HTTPException(status_code=503, detail=str(e))


@api_router.post("/dpdp/consent/{user_id}/withdraw")
async def withdraw_consent(user_id: str, request: Request, req: dict | None = None):
    """Withdraw consent (s6(4)) — no reason required, all purposes by default."""
    _require_self(request, user_id)
    try:
        return await consent_service.withdraw(user_id, (req or {}).get("purposes"))
    except Exception as e:
        logger.error(f"Consent withdrawal failed: {e}")
        raise HTTPException(status_code=503, detail=str(e))


# ── Sections 11-14: rights ───────────────────────────────────────────────

@api_router.get("/dpdp/my-data/{user_id}")
async def my_data(user_id: str, request: Request):
    """Section 11: summary of data held, processing, and recipients."""
    _require_self(request, user_id)
    try:
        summary = await consent_service.access_summary(user_id)
        await consent_service.log_request(user_id, consent_service.RequestType.ACCESS)
        return summary
    except Exception as e:
        logger.error(f"Access request failed: {e}")
        raise HTTPException(status_code=503, detail=str(e))


@api_router.post("/dpdp/request/{user_id}")
async def rights_request(user_id: str, request: Request, req: dict):
    """Lodge a correction, grievance or nomination request (s12–s14)."""
    _require_self(request, user_id)
    rt = (req.get("request_type") or "").strip()
    allowed = {consent_service.RequestType.CORRECTION,
               consent_service.RequestType.GRIEVANCE,
               consent_service.RequestType.NOMINATION}
    if rt not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"request_type must be one of: {', '.join(sorted(allowed))}")
    try:
        out = await consent_service.log_request(user_id, rt, req.get("details"))
        out["message_en"] = "Your request has been recorded and will be actioned."
        out["message_hi"] = "आपका अनुरोध दर्ज कर लिया गया है और उस पर कार्रवाई की जाएगी।"
        return out
    except Exception as e:
        logger.error(f"Rights request failed: {e}")
        raise HTTPException(status_code=503, detail=str(e))


@api_router.post("/dpdp/erase/{user_id}")
async def erase(user_id: str, request: Request, req: dict | None = None):
    """Section 12 erasure.

    Body: {"fields": [...]} to erase specific fields, or {"all": true}.
    Erasing everything is deliberately explicit — it is irreversible, and a
    citizen who meant to remove one wrong value should not lose their whole
    record to a default.
    """
    _require_self(request, user_id)
    req = req or {}
    try:
        if req.get("all"):
            result = await retention.erase_all(user_id)
        else:
            fields = req.get("fields") or []
            if not fields:
                raise HTTPException(
                    status_code=400,
                    detail="Provide 'fields' to erase, or 'all': true to erase everything.")
            result = await retention.erase_fields(
                user_id, fields, reason="s12 erasure request")
        await consent_service.log_request(
            user_id, consent_service.RequestType.ERASURE, {"scope": "all" if req.get("all") else "fields"})
        result["message_hi"] = "आपका डेटा मिटा दिया गया है।"
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erasure failed: {e}")
        raise HTTPException(status_code=503, detail=str(e))


# ── Compliance reporting (admin) ─────────────────────────────────────────

@api_router.get("/dpdp/compliance/registry")
async def compliance_registry(request: Request):
    """The record of processing — every declared field and its basis."""
    _require_admin(request)
    return {
        "notice_version": consent_service.NOTICE_VERSION,
        "field_count": len(registry.REGISTRY),
        "decisional_fields": [r.field for r in registry.decisional_fields()],
        "child_data_fields": [r.field for r in registry.child_data_fields()],
        "fields": [r.as_dict() for r in registry.REGISTRY],
    }


@api_router.get("/dpdp/compliance/source-scan")
async def compliance_source_scan(request: Request):
    """Scan the running codebase for paths that would disclose personal data."""
    _require_admin(request)
    from pathlib import Path
    report = engine.scan_source(Path(__file__).resolve().parent.parent)
    return report.as_dict()


@api_router.get("/dpdp/compliance/row/{user_id}")
async def compliance_row(user_id: str, request: Request):
    """Check one citizen's stored row against every applicable obligation."""
    _require_admin(request)
    import json
    from database import prisma

    user = await prisma.user.find_unique(where={"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    profile = {}
    for raw in (user.fullProfile, user.profile):
        if raw:
            try:
                profile.update(json.loads(raw) if isinstance(raw, str) else dict(raw))
            except (ValueError, TypeError):
                pass

    report = engine.check_row(
        profile, row_id=user_id, created_at=getattr(user, "createdAt", None),
        consented_purposes=await consent_service.consented_purposes(user_id),
        has_parental_consent=await consent_service.has_parental_consent(user_id),
    )
    return report.as_dict()


@api_router.get("/dpdp/compliance/audit")
async def compliance_audit(request: Request, limit: int = 200):
    """Estate-wide compliance position: every row, plus the source scan."""
    _require_admin(request)
    import json
    from pathlib import Path
    from database import prisma

    reports = [engine.scan_source(Path(__file__).resolve().parent.parent)]
    rows_checked = non_compliant = 0

    try:
        users = await prisma.user.find_many()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Could not read users: {e}")

    for user in users[:limit]:
        profile = {}
        for raw in (user.fullProfile, user.profile):
            if raw:
                try:
                    profile.update(json.loads(raw) if isinstance(raw, str) else dict(raw))
                except (ValueError, TypeError):
                    pass
        if not profile:
            continue
        rows_checked += 1
        r = engine.check_row(
            profile, row_id=user.id, created_at=getattr(user, "createdAt", None),
            consented_purposes=await consent_service.consented_purposes(user.id),
            has_parental_consent=await consent_service.has_parental_consent(user.id),
        )
        if not r.compliant:
            non_compliant += 1
            reports.append(r)

    combined = engine.merge(*reports)
    out = combined.as_dict()
    out["rows_checked"] = rows_checked
    out["rows_non_compliant"] = non_compliant
    return out


@api_router.post("/dpdp/compliance/retention-sweep")
async def retention_sweep(request: Request, req: dict | None = None):
    """Report, and optionally erase, data past its retention period (s8(6)).

    Defaults to a dry run: the first thing an operator should see is what would
    be deleted, not a confirmation that it already was.
    """
    _require_admin(request)
    dry_run = bool((req or {}).get("dry_run", True))
    try:
        return await retention.sweep(dry_run=dry_run)
    except Exception as e:
        logger.error(f"Retention sweep failed: {e}")
        raise HTTPException(status_code=503, detail=str(e))
