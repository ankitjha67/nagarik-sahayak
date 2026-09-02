"""Authentication routes — OTP send/verify."""
import json
import logging
from datetime import datetime, timezone
from fastapi import HTTPException
from database import prisma, motor_db
from config import check_rate_limit, generate_otp, DEMO_MODE
from models import SendOTPRequest, VerifyOTPRequest, AuthResponse
from routes import api_router

logger = logging.getLogger(__name__)


@api_router.post("/auth/send-otp", response_model=AuthResponse)
async def send_otp(req: SendOTPRequest):
    if check_rate_limit(f"otp:{req.phone}"):
        raise HTTPException(status_code=429, detail="Too many OTP requests. Please wait 60 seconds.")

    otp_code = "123456" if DEMO_MODE else generate_otp()

    await motor_db.otp_sessions.update_one(
        {"phone": req.phone},
        {"$set": {"phone": req.phone, "otp": otp_code, "verified": False,
                  "created_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True)

    logger.info(f"OTP generated for {req.phone[:4]}****")
    return AuthResponse(success=True, message="OTP sent successfully")


@api_router.post("/auth/verify-otp", response_model=AuthResponse)
async def verify_otp(req: VerifyOTPRequest):
    if check_rate_limit(f"verify:{req.phone}"):
        raise HTTPException(status_code=429, detail="Too many verification attempts. Please wait 60 seconds.")

    session = await motor_db.otp_sessions.find_one({"phone": req.phone}, {"_id": 0})
    if not session:
        return AuthResponse(success=False, message="OTP session not found. Please request OTP first.")

    stored_otp = session.get("otp", "")
    if not stored_otp or req.otp != stored_otp:
        return AuthResponse(success=False, message="Invalid OTP")

    created_at = session.get("created_at", "")
    if created_at:
        try:
            otp_time = datetime.fromisoformat(created_at)
            if (datetime.now(timezone.utc) - otp_time).total_seconds() > 300:
                return AuthResponse(success=False, message="OTP expired. Please request a new one.")
        except (ValueError, TypeError):
            pass

    await motor_db.otp_sessions.update_one({"phone": req.phone}, {"$set": {"verified": True, "otp": ""}})

    user = await prisma.user.find_unique(where={"phone": req.phone})
    if not user:
        user = await prisma.user.create(data={
            "phone": req.phone, "language": "hi",
            "profile": json.dumps({"name": "", "age": None, "income": None, "state": ""}, ensure_ascii=False),
        })
    return AuthResponse(success=True, message="OTP verified successfully", user_id=user.id, phone=req.phone)
