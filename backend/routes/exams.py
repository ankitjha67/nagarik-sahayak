"""Exam routes — exposes V3 exam pipeline data via REST API."""
import asyncio
import logging
from datetime import date, timedelta
from fastapi import HTTPException
from routes import api_router
from services import v3_bridge

logger = logging.getLogger(__name__)


def _exam_to_summary(exam: dict) -> dict:
    """Map a raw exams-table row to the API response shape."""
    return {
        "exam_id": exam.get("exam_id"),
        "exam_name": exam.get("clean_exam_name") or exam.get("exam_name"),
        "short_name": exam.get("short_name"),
        "conducting_body": exam.get("conducting_body"),
        "category": exam.get("exam_category"),
        "level": exam.get("exam_level"),
        "state": exam.get("state"),
        "status": exam.get("exam_status"),
        "notification_date": exam.get("notification_date"),
        "application_start": exam.get("application_start_date"),
        "application_end": exam.get("application_end_date"),
        "total_vacancies": exam.get("total_vacancies"),
        "qualification": exam.get("qualification"),
        "fee_general": exam.get("fee_general"),
        "fee_sc_st": exam.get("fee_sc_st"),
        "official_website": exam.get("official_website"),
        "apply_url": exam.get("apply_online_url"),
        "admit_card_url": exam.get("admit_card_url"),
        "result_url": exam.get("result_url"),
        "change_type": exam.get("change_type"),
        "first_seen": exam.get("first_seen_date"),
        "last_seen": exam.get("last_seen_date"),
    }


def _days_left(date_str: str | None) -> int | None:
    if not date_str:
        return None
    try:
        return (date.fromisoformat(date_str[:10]) - date.today()).days
    except (ValueError, TypeError):
        return None


@api_router.get("/exams")
async def list_exams(
    category: str = "",
    status: str = "",
    level: str = "",
    state: str = "",
    search: str = "",
    limit: int = 50,
    offset: int = 0,
):
    """List exams with optional filtering."""
    def _work():
        db = v3_bridge.get_exam_db()
        if not db:
            return None
        return db.get_all_exams()

    try:
        exams = await asyncio.to_thread(_work)
        if exams is None:
            return {"exams": [], "count": 0, "error": "Exam database not available"}

        def _match(e):
            if category and e.get("exam_category") != category:
                return False
            if status and e.get("exam_status") != status:
                return False
            if level and e.get("exam_level") != level:
                return False
            if state and e.get("state") != state:
                return False
            if search:
                q = search.lower()
                hay = (
                    f"{e.get('clean_exam_name', '')} {e.get('exam_name', '')} "
                    f"{e.get('conducting_body', '')} {e.get('short_name', '')}"
                ).lower()
                if q not in hay:
                    return False
            return True

        filtered = [e for e in exams if _match(e)]
        total = len(filtered)
        limit = max(1, min(limit, 200))
        offset = max(0, offset)
        page = filtered[offset:offset + limit]

        return {
            "exams": [_exam_to_summary(e) for e in page],
            "count": total,
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        logger.error(f"Failed to list exams: {e}")
        return {"exams": [], "count": 0, "error": str(e)}


@api_router.get("/exams/alerts")
async def exam_alerts(days_ahead: int = 30):
    """Get upcoming exam alerts — deadlines, admit cards, results within N days."""
    days_ahead = max(1, min(days_ahead, 365))

    def _work():
        db = v3_bridge.get_exam_db()
        if not db:
            return None
        return {
            "deadlines": db.get_approaching_deadlines(days=days_ahead),
            "all_exams": db.get_all_exams(),
            "new": db.get_new_since((date.today() - timedelta(days=7)).isoformat()),
        }

    try:
        data = await asyncio.to_thread(_work)
        if data is None:
            return {"alerts": [], "count": 0, "error": "Exam database not available"}

        today = date.today()
        alerts = []

        # Application deadlines approaching
        for exam in data["deadlines"]:
            days_left = _days_left(exam.get("application_end_date"))
            if days_left is None or days_left < 0:
                continue
            urgency = "critical" if days_left <= 3 else "high" if days_left <= 7 else "medium"
            alerts.append({
                "type": "deadline",
                "urgency": urgency,
                "exam_name": exam.get("clean_exam_name") or exam.get("exam_name"),
                "conducting_body": exam.get("conducting_body"),
                "date": exam.get("application_end_date"),
                "days_left": days_left,
                "message_hi": f"आवेदन की अंतिम तिथि {days_left} दिन में",
                "message_en": f"Application deadline in {days_left} days",
                "apply_url": exam.get("apply_online_url"),
                "exam_id": exam.get("exam_id"),
            })

        # Admit cards out / results awaited (by status)
        deadline_ids = {a["exam_id"] for a in alerts}
        for exam in data["all_exams"]:
            status = exam.get("exam_status")
            if status == "Admit_Card_Out":
                alerts.append({
                    "type": "admit_card",
                    "urgency": "high",
                    "exam_name": exam.get("clean_exam_name") or exam.get("exam_name"),
                    "conducting_body": exam.get("conducting_body"),
                    "date": None,
                    "message_hi": "एडमिट कार्ड जारी",
                    "message_en": "Admit card released",
                    "url": exam.get("admit_card_url"),
                    "exam_id": exam.get("exam_id"),
                })
            elif status == "Result_Awaited":
                alerts.append({
                    "type": "result",
                    "urgency": "medium",
                    "exam_name": exam.get("clean_exam_name") or exam.get("exam_name"),
                    "conducting_body": exam.get("conducting_body"),
                    "date": exam.get("result_date"),
                    "message_hi": "परिणाम की प्रतीक्षा",
                    "message_en": "Result awaited",
                    "url": exam.get("result_url"),
                    "exam_id": exam.get("exam_id"),
                })

        # New notifications (last 7 days), skip ones already alerted as deadlines
        for exam in data["new"]:
            if exam.get("exam_id") in deadline_ids:
                continue
            alerts.append({
                "type": "new",
                "urgency": "low",
                "exam_name": exam.get("clean_exam_name") or exam.get("exam_name"),
                "conducting_body": exam.get("conducting_body"),
                "date": exam.get("notification_date") or exam.get("first_seen_date"),
                "total_vacancies": exam.get("total_vacancies"),
                "message_hi": "नई अधिसूचना",
                "message_en": "New notification",
                "apply_url": exam.get("apply_online_url"),
                "exam_id": exam.get("exam_id"),
            })

        urgency_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        alerts.sort(key=lambda a: (urgency_order.get(a["urgency"], 4), a.get("days_left") or 999))

        return {
            "alerts": alerts,
            "count": len(alerts),
            "days_ahead": days_ahead,
            "as_of": today.isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get exam alerts: {e}")
        return {"alerts": [], "count": 0, "error": str(e)}


@api_router.get("/exams/upcoming")
async def upcoming_exams(days: int = 30):
    """Exams whose exam date falls within the next N days."""
    days = max(1, min(days, 365))

    def _work():
        db = v3_bridge.get_exam_db()
        if not db:
            return None
        return db.get_upcoming_exams(days=days)

    try:
        exams = await asyncio.to_thread(_work)
        if exams is None:
            return {"exams": [], "count": 0, "error": "Exam database not available"}
        return {"exams": [_exam_to_summary(e) for e in exams], "count": len(exams)}
    except Exception as e:
        return {"exams": [], "count": 0, "error": str(e)}


@api_router.get("/exams/categories")
async def exam_categories():
    """List all exam categories with counts."""
    try:
        stats = await v3_bridge.exam_stats()
        if stats is None:
            return {"categories": {}}
        return {"categories": stats.get("by_category", {})}
    except Exception as e:
        return {"categories": {}, "error": str(e)}


@api_router.get("/exams/stats")
async def exam_stats_endpoint():
    """Aggregated exam statistics."""
    def _work():
        db = v3_bridge.get_exam_db()
        if not db:
            return None
        return {
            "stats": db.get_stats(),
            "deadlines_30d": len(db.get_approaching_deadlines(days=30)),
        }

    try:
        data = await asyncio.to_thread(_work)
        if data is None:
            return {"total_exams": 0, "error": "Exam database not available"}
        stats = data["stats"]
        return {
            "total_exams": stats.get("total", 0),
            "active_exams": stats.get("active", 0),
            "by_category": stats.get("by_category", {}),
            "by_status": stats.get("by_status", {}),
            "by_level": stats.get("by_level", {}),
            "by_body": stats.get("by_body", {}),
            "upcoming_deadlines_30d": data["deadlines_30d"],
        }
    except Exception as e:
        return {"total_exams": 0, "error": str(e)}


@api_router.get("/exams/{exam_id}")
async def get_exam_detail(exam_id: str):
    """Get full details for a single exam."""
    def _work():
        db = v3_bridge.get_exam_db()
        if not db:
            return "unavailable"
        for exam in db.get_all_exams():
            if exam.get("exam_id") == exam_id:
                return exam
        return None

    exam = await asyncio.to_thread(_work)
    if exam == "unavailable":
        raise HTTPException(status_code=503, detail="Exam database not available")
    if exam is None:
        raise HTTPException(status_code=404, detail="Exam not found")
    return exam
