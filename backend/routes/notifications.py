"""Notification preference routes — user-level alert settings and exam subscriptions."""
import json
import logging
from fastapi import HTTPException
from routes import api_router
from database import prisma

logger = logging.getLogger(__name__)

VALID_ALERT_TYPES = {"deadline", "admit_card", "result", "new"}


@api_router.get("/notifications/preferences/{user_id}")
async def get_notification_preferences(user_id: str):
    """Return the user's notification preferences (stored in profile JSON)."""
    try:
        user = await prisma.user.find_unique(where={"id": user_id})
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid user id: {e}")
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    profile = {}
    if user.profile:
        try:
            profile = json.loads(user.profile) if isinstance(user.profile, str) else dict(user.profile)
        except (ValueError, TypeError):
            profile = {}

    prefs = profile.get("notifications", {})
    return {
        "user_id": user_id,
        "scheme_deadline_alerts": prefs.get("scheme_deadline_alerts", False),
        "exam_deadline_alerts": prefs.get("exam_deadline_alerts", False),
        "new_scheme_alerts": prefs.get("new_scheme_alerts", False),
        "email": prefs.get("email", ""),
    }


@api_router.put("/notifications/preferences/{user_id}")
async def update_notification_preferences(user_id: str, req: dict):
    """Update notification preferences. Accepts any of:
    scheme_deadline_alerts, exam_deadline_alerts, new_scheme_alerts (bool), email (str)."""
    try:
        user = await prisma.user.find_unique(where={"id": user_id})
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid user id: {e}")
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    profile = {}
    if user.profile:
        try:
            profile = json.loads(user.profile) if isinstance(user.profile, str) else dict(user.profile)
        except (ValueError, TypeError):
            profile = {}

    prefs = profile.get("notifications", {})
    for key in ("scheme_deadline_alerts", "exam_deadline_alerts", "new_scheme_alerts"):
        if key in req:
            prefs[key] = bool(req[key])
    if "email" in req:
        email = str(req["email"]).strip()[:254]
        # Light validation — empty clears the address
        if email and ("@" not in email or "." not in email.split("@")[-1]):
            raise HTTPException(status_code=400, detail="Invalid email address")
        prefs["email"] = email

    profile["notifications"] = prefs
    await prisma.user.update(
        where={"id": user_id},
        data={"profile": json.dumps(profile)},
    )
    return {"success": True, "notifications": prefs}


@api_router.get("/notifications/subscriptions/{user_id}")
async def list_exam_subscriptions(user_id: str):
    """List the user's exam alert subscriptions."""
    try:
        subs = await prisma.examsubscription.find_many(
            where={"userId": user_id, "active": True},
            order={"createdAt": "desc"},
        )
    except AttributeError:
        # Prisma client not regenerated with the new model yet
        return {"subscriptions": [], "count": 0,
                "error": "ExamSubscription model not available — run `prisma generate`"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    results = []
    for s in subs:
        alert_types = []
        if s.alertTypes:
            try:
                alert_types = json.loads(s.alertTypes) if isinstance(s.alertTypes, str) else list(s.alertTypes)
            except (ValueError, TypeError):
                alert_types = []
        results.append({
            "id": s.id,
            "exam_id": s.examId,
            "exam_name": s.examName,
            "category": s.category,
            "alert_types": alert_types,
            "created_at": s.createdAt.isoformat() if s.createdAt else None,
        })
    return {"subscriptions": results, "count": len(results)}


@api_router.post("/notifications/subscriptions/{user_id}")
async def create_exam_subscription(user_id: str, req: dict):
    """Subscribe a user to alerts for a specific exam.
    Body: {exam_id, exam_name, category?, alert_types?: ["deadline","admit_card","result"]}"""
    exam_id = str(req.get("exam_id", "")).strip()
    exam_name = str(req.get("exam_name", "")).strip()
    if not exam_id or not exam_name:
        raise HTTPException(status_code=400, detail="exam_id and exam_name are required")

    alert_types = req.get("alert_types") or ["deadline"]
    alert_types = [t for t in alert_types if t in VALID_ALERT_TYPES] or ["deadline"]

    try:
        # Avoid duplicate active subscriptions for the same exam
        existing = await prisma.examsubscription.find_first(
            where={"userId": user_id, "examId": exam_id, "active": True},
        )
        if existing:
            return {"success": True, "id": existing.id, "already_subscribed": True}

        sub = await prisma.examsubscription.create(data={
            "userId": user_id,
            "examId": exam_id,
            "examName": exam_name[:500],
            "category": str(req.get("category", ""))[:100],
            "alertTypes": json.dumps(alert_types),
            "email": str(req.get("email", ""))[:254],
        })
        return {"success": True, "id": sub.id, "already_subscribed": False}
    except AttributeError:
        raise HTTPException(
            status_code=503,
            detail="ExamSubscription model not available — run `prisma generate`",
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@api_router.delete("/notifications/subscriptions/{user_id}/{subscription_id}")
async def delete_exam_subscription(user_id: str, subscription_id: str):
    """Unsubscribe (soft-delete) an exam alert subscription."""
    try:
        sub = await prisma.examsubscription.find_unique(where={"id": subscription_id})
        if not sub or sub.userId != user_id:
            raise HTTPException(status_code=404, detail="Subscription not found")
        await prisma.examsubscription.update(
            where={"id": subscription_id},
            data={"active": False},
        )
        return {"success": True}
    except HTTPException:
        raise
    except AttributeError:
        raise HTTPException(
            status_code=503,
            detail="ExamSubscription model not available — run `prisma generate`",
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
