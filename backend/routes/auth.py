"""Authentication routes: one-time codes, sessions, MFA, operator consent.

  POST /auth/send-otp            request a code (hashed at rest, delivered by SMS)
  POST /auth/verify-otp          exchange the code for an access + refresh token
                                 (admins also present a TOTP; an operator may
                                 instead record a citizen's consent)
  POST /auth/refresh             rotate the refresh token, new access token
  POST /auth/logout              revoke this session
  POST /auth/logout-all          revoke every session of the caller
  GET  /auth/me                  who am I, which role, which session
  POST /auth/mfa/enroll          admin: start TOTP enrolment (secret + otpauth URI)
  POST /auth/mfa/confirm         admin: confirm with a first code
  GET  /auth/audit/verify        admin: check the auth audit chain
"""
from __future__ import annotations

import json
import logging
import time

from fastapi import HTTPException, Request
from pydantic import BaseModel

from auth import audit, otp, settings, sms, tokens, totp
from auth.deps import Principal, principal_of, require_role
from auth.store import get_store
from config import check_rate_limit
from database import find_user, prisma
from models import AuthResponse, SendOTPRequest, VerifyOTPRequest
from routes import api_router
from api.middleware import client_ip

logger = logging.getLogger(__name__)


def _ip(request: Request) -> str:
    return client_ip(request.scope)


@api_router.post("/auth/send-otp", response_model=AuthResponse)
async def send_otp(req: SendOTPRequest, request: Request):
    if check_rate_limit(f"otp:{req.phone}"):
        raise HTTPException(status_code=429, detail="Too many OTP requests. Please wait 60 seconds.")
    try:
        issued = await otp.issue(req.phone)
    except otp.OtpError as e:
        raise HTTPException(status_code=e.status, detail=e.reason,
                            headers={"Retry-After": str(e.retry_after)} if e.retry_after else None)

    delivered = "mock"
    if not issued.mocked:
        try:
            delivered = await sms.send_otp(req.phone, issued.code)
        except sms.SmsError as e:
            logger.error("OTP delivery failed for %s****: %s", req.phone[:4], e)
            await get_store().otp_delete(req.phone)
            raise HTTPException(status_code=502, detail="Could not send the code right now. Please try again.")

    await audit.record("otp_issued", subject=req.phone[-4:], ip=_ip(request),
                       detail={"via": delivered})
    logger.info("OTP issued for %s**** via %s", req.phone[:4], delivered)
    return AuthResponse(success=True, message="OTP sent successfully",
                        expires_in=issued.expires_in, mock=issued.mocked)


@api_router.post("/auth/verify-otp", response_model=AuthResponse)
async def verify_otp(req: VerifyOTPRequest, request: Request):
    if check_rate_limit(f"verify:{req.phone}"):
        raise HTTPException(status_code=429, detail="Too many verification attempts. Please wait 60 seconds.")
    try:
        await otp.verify(req.phone, req.otp)
    except otp.OtpError as e:
        await audit.record("otp_failed", subject=req.phone[-4:], ip=_ip(request), detail={"reason": e.reason})
        raise HTTPException(status_code=e.status, detail=e.reason,
                            headers={"Retry-After": str(e.retry_after)} if e.retry_after else None)

    user = await prisma.user.find_unique(where={"phone": req.phone})
    if not user:
        user = await prisma.user.create(data={
            "phone": req.phone, "language": "hi",
            "profile": json.dumps({"name": "", "age": None, "income": None, "state": ""}, ensure_ascii=False),
        })

    # An operator records the citizen's consent instead of signing them in:
    # the citizen has just proven the phone is theirs, on the operator's device.
    if req.for_operator:
        operator = getattr(request.state, "principal", None)
        if operator is None or operator.role != "operator":
            raise HTTPException(status_code=403, detail="Only a signed-in operator can record consent.")
        ttl = max(5, min(int(req.consent_minutes or 60), 240)) * 60
        await get_store().consent_put({
            "operator_id": operator.user_id, "citizen_id": user.id,
            "granted_at": time.time(), "expires_at": time.time() + ttl, "revoked": False,
        })
        await audit.record("consent_recorded", actor=operator.user_id, subject=user.id, ip=_ip(request),
                           detail={"minutes": ttl // 60})
        return AuthResponse(success=True, message="Consent recorded", user_id=user.id, phone=req.phone,
                            consent_expires_in=ttl)

    role = settings.role_for_phone(req.phone)
    if role == "admin" and settings.admin_mfa_required():
        mfa = await get_store().mfa_get(user.id)
        if mfa and mfa.get("confirmed"):
            if not req.totp or not totp.verify(mfa["secret"], req.totp):
                await audit.record("login_mfa_failed", subject=user.id, ip=_ip(request))
                raise HTTPException(status_code=401, detail="Authenticator code required or wrong.")
        # An admin who has not enrolled yet signs in and must enrol before
        # admin routes are useful; /auth/me reports mfa_enrolled=false.

    session = await tokens.create_session(
        user.id, role, phone=req.phone,
        user_agent=request.headers.get("user-agent", ""), ip=_ip(request))
    await audit.record("login", actor=user.id, subject=user.id, ip=_ip(request),
                       detail={"role": role, "sid": session["sid"]})
    return AuthResponse(success=True, message="OTP verified successfully", user_id=user.id, phone=req.phone,
                        access_token=session["access_token"], refresh_token=session["refresh_token"],
                        token_type="bearer", expires_in=session["expires_in"], role=role)


class RefreshRequest(BaseModel):
    refresh_token: str


@api_router.post("/auth/refresh")
async def refresh(req: RefreshRequest, request: Request):
    try:
        session = await tokens.refresh_session(req.refresh_token)
    except tokens.TokenError as e:
        await audit.record("refresh_reuse" if "revoked" in e.reason.lower() else "refresh_failed",
                           ip=_ip(request), detail={"reason": e.reason})
        raise HTTPException(status_code=e.status, detail=e.reason)
    await audit.record("refresh", subject=session["sid"], ip=_ip(request))
    return session


@api_router.post("/auth/logout")
async def logout(request: Request):
    p = principal_of(request)
    if p.sid:
        await tokens.revoke_session(p.sid)
    await audit.record("logout", actor=p.user_id, subject=p.user_id, ip=_ip(request))
    return {"success": True}


@api_router.post("/auth/logout-all")
async def logout_all(request: Request):
    p = principal_of(request)
    n = await tokens.revoke_all(p.user_id)
    await audit.record("logout_all", actor=p.user_id, subject=p.user_id, ip=_ip(request), detail={"sessions": n})
    return {"success": True, "revoked": n}


@api_router.get("/auth/me")
async def me(request: Request):
    p: Principal = principal_of(request)
    user = await find_user(p.user_id) if p.via == "bearer" else None
    mfa = await get_store().mfa_get(p.user_id) if p.role == "admin" else None
    return {
        "user_id": p.user_id, "role": p.role, "sid": p.sid, "via": p.via,
        "phone_masked": (f"******{user.phone[-4:]}" if user else None),
        "language": user.language if user else None,
        "mfa_enrolled": bool(mfa and mfa.get("confirmed")),
        "expires_in": settings.access_ttl_seconds(),
    }


class MfaConfirm(BaseModel):
    code: str


@api_router.post("/auth/mfa/enroll")
async def mfa_enroll(request: Request):
    p = await require_role("admin")(request)
    secret = totp.generate_secret()
    await get_store().mfa_put(p.user_id, {"user_id": p.user_id, "secret": secret, "confirmed": False,
                                         "created_at": time.time()})
    return {"secret": secret, "otpauth_uri": totp.otpauth_uri(secret, account=p.user_id)}


@api_router.post("/auth/mfa/confirm")
async def mfa_confirm(req: MfaConfirm, request: Request):
    p = await require_role("admin")(request)
    rec = await get_store().mfa_get(p.user_id)
    if not rec:
        raise HTTPException(status_code=400, detail="Start enrolment first.")
    if not totp.verify(rec["secret"], req.code):
        raise HTTPException(status_code=401, detail="That code did not match. Check the time on your phone.")
    await get_store().mfa_put(p.user_id, {**rec, "confirmed": True, "confirmed_at": time.time()})
    await audit.record("mfa_enrolled", actor=p.user_id, subject=p.user_id, ip=_ip(request))
    return {"success": True}


@api_router.get("/auth/audit/verify")
async def audit_verify(request: Request):
    await require_role("admin")(request)
    return await audit.verify_chain()
