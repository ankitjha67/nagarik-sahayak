"""KYC routes — offer every identity option, and be honest about each.

Two rules hold across this file.

*Nothing here refuses an application.* Every endpoint returns evidence and a
recommendation; the decision belongs to the eligibility engine and a human
reviewer. A 4xx from these routes means the request could not be processed (a
mistyped share code, a file that is not a ZIP), never that the citizen is
ineligible.

*Nothing here reports an unperformed check as performed.* A method that needs
credentials this deployment does not hold returns 503 naming what is missing,
rather than a fabricated success or a silent fallback to a weaker check.
"""
import base64
import binascii
import logging

from fastapi import HTTPException, Request

from routes import api_router
from kyc import aadhaar_offline, methods as kyc_methods, service as kyc_service

logger = logging.getLogger(__name__)

# Matches the parser's own cap, applied before base64 decoding so an oversized
# upload is rejected without being materialised.
MAX_UPLOAD_B64 = int(aadhaar_offline.MAX_ZIP_BYTES * 4 / 3) + 1024


def _caller(request: Request) -> str:
    caller = request.headers.get("X-User-Id", "").strip()
    if not caller:
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    return caller


def _require_self(request: Request, user_id: str) -> None:
    if _caller(request) != user_id:
        raise HTTPException(status_code=403, detail="You may only access your own data.")


def _profile(req: dict) -> dict:
    profile = req.get("profile") or {}
    if not isinstance(profile, dict):
        raise HTTPException(status_code=400, detail="profile must be an object")
    return profile


def _unavailable(exc: RuntimeError):
    return HTTPException(status_code=503, detail=str(exc))


# ── Discovery ────────────────────────────────────────────────────────────

@api_router.get("/kyc/methods")
async def list_methods(only_available: bool = False):
    """Every identity option, each marked with whether it actually works here.

    Unavailable methods are listed and labelled rather than hidden. A citizen
    told by a leaflet to "verify with DigiLocker" deserves to be told it is not
    switched on, instead of hunting for a button that does not exist.
    """
    opts = kyc_methods.options(include_unavailable=not only_available)
    usable = [o for o in opts if o["usable"]]
    return {
        "methods": opts,
        "count": len(opts),
        "availableCount": len(usable),
        "bestAvailableAssurance": int(kyc_methods.best_available_assurance()),
        # Stated as data so the UI cannot accidentally present a KYC step as a
        # precondition for applying.
        "kycIsOptional": True,
        "note": ("No scheme application requires any of these. They raise the "
                 "confidence in your identity, which speeds a claim up; the "
                 "Aadhaar Act s7 proviso means a benefit cannot be refused for "
                 "want of authentication."),
        "noteHindi": ("किसी भी योजना के आवेदन हेतु इनमें से कोई अनिवार्य नहीं है। ये "
                      "आपकी पहचान पर विश्वास बढ़ाते हैं, जिससे दावा शीघ्र निपटता है; "
                      "आधार अधिनियम की धारा 7 के परंतुक के अनुसार प्रमाणीकरण न होने "
                      "पर लाभ से वंचित नहीं किया जा सकता।"),
    }


@api_router.get("/kyc/methods/{key}")
async def method_detail(key: str):
    method = kyc_methods.get(key)
    if method is None:
        raise HTTPException(status_code=404, detail=f"Unknown KYC method '{key}'")
    return method.as_dict()


# ── Aadhaar offline e-KYC ────────────────────────────────────────────────

@api_router.post("/kyc/aadhaar/offline-xml")
async def aadhaar_offline_xml(request: Request, req: dict):
    """Verify an Aadhaar Offline e-KYC ZIP.

    Body: {"profile": {...}, "fileBase64": "...", "shareCode": "ABCD"}

    The uploaded file is parsed in memory and discarded. Only the demographic
    fields and the last four Aadhaar digits are returned; the full number is
    not present in UIDAI's file and is never reconstructed.
    """
    _caller(request)
    profile = _profile(req)
    encoded = req.get("fileBase64") or ""
    if not encoded:
        raise HTTPException(status_code=400, detail="fileBase64 is required")
    if len(encoded) > MAX_UPLOAD_B64:
        raise HTTPException(
            status_code=413,
            detail="That file is far larger than an Aadhaar e-KYC download.")
    try:
        blob = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="fileBase64 is not valid base64")

    try:
        outcome = kyc_service.verify_offline_xml(
            profile, blob, str(req.get("shareCode") or ""))
    except aadhaar_offline.OfflineKycError as exc:
        # 400 with a bilingual, actionable message. The citizen mistyped a share
        # code or uploaded the wrong file; both are fixable by them.
        raise HTTPException(status_code=400, detail=exc.as_dict())
    except RuntimeError as exc:
        raise _unavailable(exc)
    return outcome.as_dict()


@api_router.post("/kyc/aadhaar/secure-qr")
async def aadhaar_secure_qr(request: Request, req: dict):
    """Verify the Secure QR code from an e-Aadhaar letter or PVC card.

    Body: {"profile": {...}, "qr": "<digits scanned from the QR>"}
    """
    _caller(request)
    profile = _profile(req)
    qr = req.get("qr") or req.get("qrValue") or ""
    if not qr:
        raise HTTPException(status_code=400, detail="qr is required")
    try:
        outcome = kyc_service.verify_secure_qr(profile, str(qr))
    except aadhaar_offline.OfflineKycError as exc:
        raise HTTPException(status_code=400, detail=exc.as_dict())
    except RuntimeError as exc:
        raise _unavailable(exc)
    return outcome.as_dict()


# ── Human routes ─────────────────────────────────────────────────────────

@api_router.post("/kyc/attestation")
async def attestation(request: Request, req: dict):
    """Record that an operator or officer saw the applicant and their documents.

    Body: {"profile": {...}, "method": "csc_assisted"|"officer_attestation",
           "attestorName": "...", "attestorRole": "...", "attestorId": "...",
           "documentsSeen": ["..."]}

    The attestor's identity is required. An anonymous attestation cannot be
    audited, and the ability to trace repeat attestations to one operator is
    what lets abuse be caught without ever penalising an individual citizen for
    the operator's conduct.
    """
    _caller(request)
    method = str(req.get("method") or "csc_assisted")
    if method not in ("csc_assisted", "officer_attestation"):
        raise HTTPException(status_code=400,
                            detail="method must be csc_assisted or officer_attestation")
    try:
        outcome = kyc_service.record_attestation(
            _profile(req), method=method,
            attestor_name=str(req.get("attestorName") or ""),
            attestor_role=str(req.get("attestorRole") or ""),
            attestor_id=str(req.get("attestorId") or ""),
            documents_seen=req.get("documentsSeen") or [])
    except RuntimeError as exc:
        raise _unavailable(exc)
    return outcome.as_dict()


@api_router.post("/kyc/self-declaration")
async def self_declaration(request: Request, req: dict):
    """Record identity details as self-declared, with format checks only.

    Always available. It is what lets someone with none of the digital
    prerequisites start an application at all.
    """
    _caller(request)
    return kyc_service.record_self_declaration(_profile(req)).as_dict()


# ── Status ───────────────────────────────────────────────────────────────

@api_router.post("/kyc/status")
async def kyc_status(request: Request, req: dict):
    """Summarise a set of verification outcomes into one state for the citizen.

    Body: {"outcomes": [<as returned by the verify endpoints>]}

    Stateless by design: the caller holds the outcomes. Persisting a verification
    history would create a second store of identity evidence to protect, and the
    reviewer console already records what it needs against the case.
    """
    _caller(request)
    raw = req.get("outcomes") or []
    if not isinstance(raw, list):
        raise HTTPException(status_code=400, detail="outcomes must be a list")
    outcomes = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            level = kyc_methods.Assurance(int(item.get("assurance", 0)))
        except ValueError:
            level = kyc_methods.Assurance.NONE
        outcomes.append(kyc_service.VerificationOutcome(
            method=str(item.get("method") or ""),
            succeeded=bool(item.get("succeeded")),
            assurance=level,
            contradicted=bool(item.get("contradicted")),
            needs_review=bool(item.get("needsReview")),
        ))
    return kyc_service.assurance_summary(outcomes)


@api_router.post("/kyc/scheme-gap")
async def scheme_gap(request: Request, req: dict):
    """What would strengthen a claim on one scheme — advisory only.

    Body: {"outcomes": [...], "schemeName": "..."}

    `canStillApply` is always true in the response, and deliberately so: telling
    a citizen they may not even apply is not a power this application has.
    """
    _caller(request)
    from data.gov_forms import get_by_name

    scheme = get_by_name(str(req.get("schemeName") or ""))
    if not scheme:
        raise HTTPException(status_code=404, detail="Scheme not in catalog")
    raw = req.get("outcomes") or []
    outcomes = [
        kyc_service.VerificationOutcome(
            method=str(o.get("method") or ""), succeeded=bool(o.get("succeeded")),
            assurance=kyc_methods.Assurance(int(o.get("assurance", 0))))
        for o in raw if isinstance(o, dict)
    ]
    gap = kyc_service.gap_for_scheme(outcomes, scheme)
    gap["scheme"] = scheme["schemeName"]
    return gap
