"""Exam routes — exposes V3 exam pipeline data via REST API."""
import logging
from datetime import date, datetime, timedelta, timezone
from fastapi import HTTPException, BackgroundTasks
from routes import api_router

logger = logging.getLogger(__name__)

# In-memory exam crawl state
_exam_crawl_state = {
    "status": "idle",
    "started_at": None,
    "completed_at": None,
    "exams_found": 0,
    "exams_new": 0,
    "portals_crawled": 0,
    "error": None,
}


def _get_exam_modules():
    """Lazy-import V3 exam modules."""
    try:
        import sys
        from pathlib import Path
        project_root = str(Path(__file__).resolve().parent.parent.parent)
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        from src.exams.exam_database import ExamDatabase
        from src.exams.exam_alert import ExamAlertEngine
        from src.exams.exam_crawler import ExamDiscoveryCrawler
        from src.exams.exam_parser import ExamParser
        from src.exams.exam_storage import ExamStorageAgent
        from src.exams.exam_models import ExamCategory, ExamStatus
        from src.config.settings import AgentConfig, EXAM_PORTAL_SOURCES
        return {
            "ExamDatabase": ExamDatabase,
            "ExamAlertEngine": ExamAlertEngine,
            "ExamDiscoveryCrawler": ExamDiscoveryCrawler,
            "ExamParser": ExamParser,
            "ExamStorageAgent": ExamStorageAgent,
            "ExamCategory": ExamCategory,
            "ExamStatus": ExamStatus,
            "AgentConfig": AgentConfig,
            "EXAM_PORTAL_SOURCES": EXAM_PORTAL_SOURCES,
        }
    except ImportError as e:
        logger.warning(f"V3 exam modules not available: {e}")
        return None


def _get_exam_db():
    """Get or create the exam database instance."""
    mods = _get_exam_modules()
    if not mods:
        return None, mods
    config = mods["AgentConfig"]()
    db = mods["ExamDatabase"](config.output_dir / "exams.db")
    return db, mods


@api_router.get("/exams")
async def list_exams(
    category: str = "",
    status: str = "",
    level: str = "",
    search: str = "",
    limit: int = 50,
    offset: int = 0,
):
    """List exams with optional filtering."""
    db, mods = _get_exam_db()
    if not db:
        return {"exams": [], "count": 0, "error": "Exam database not available"}

    try:
        filters = {}
        if category:
            filters["exam_category"] = category
        if status:
            filters["exam_status"] = status
        if level:
            filters["exam_level"] = level
        if search:
            filters["search"] = search

        exams = db.search_exams(filters, limit=limit, offset=offset)
        total = db.count_exams(filters)

        results = []
        for exam in exams:
            results.append({
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
            })

        return {"exams": results, "count": total, "limit": limit, "offset": offset}
    except Exception as e:
        logger.error(f"Failed to list exams: {e}")
        return {"exams": [], "count": 0, "error": str(e)}


@api_router.get("/exams/alerts")
async def exam_alerts(days_ahead: int = 30):
    """Get upcoming exam alerts — deadlines, admit cards, results within N days."""
    db, mods = _get_exam_db()
    if not db:
        return {"alerts": [], "error": "Exam database not available"}

    try:
        today = date.today()
        cutoff = today + timedelta(days=days_ahead)
        today_str = today.isoformat()
        cutoff_str = cutoff.isoformat()

        alerts = []

        # Application deadlines approaching
        deadline_exams = db.get_exams_by_date_range(
            "application_end_date", today_str, cutoff_str
        )
        for exam in deadline_exams:
            days_left = (date.fromisoformat(exam["application_end_date"]) - today).days
            urgency = "critical" if days_left <= 3 else "high" if days_left <= 7 else "medium"
            alerts.append({
                "type": "deadline",
                "urgency": urgency,
                "exam_name": exam.get("clean_exam_name") or exam.get("exam_name"),
                "conducting_body": exam.get("conducting_body"),
                "date": exam["application_end_date"],
                "days_left": days_left,
                "message_hi": f"आवेदन की अंतिम तिथि {days_left} दिन में",
                "message_en": f"Application deadline in {days_left} days",
                "apply_url": exam.get("apply_online_url"),
                "exam_id": exam.get("exam_id"),
            })

        # Admit cards out
        admit_exams = db.get_exams_by_status("Admit_Card_Out")
        for exam in admit_exams:
            alerts.append({
                "type": "admit_card",
                "urgency": "high",
                "exam_name": exam.get("clean_exam_name") or exam.get("exam_name"),
                "conducting_body": exam.get("conducting_body"),
                "date": exam.get("admit_card_date"),
                "message_hi": "एडमिट कार्ड जारी",
                "message_en": "Admit card released",
                "url": exam.get("admit_card_url"),
                "exam_id": exam.get("exam_id"),
            })

        # Results declared
        result_exams = db.get_exams_by_status("Result_Awaited")
        for exam in result_exams:
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

        # New notifications (discovered in last 7 days)
        new_exams = db.get_recently_added(days=7)
        for exam in new_exams:
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

        # Sort by urgency
        urgency_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        alerts.sort(key=lambda a: urgency_order.get(a["urgency"], 4))

        return {
            "alerts": alerts,
            "count": len(alerts),
            "days_ahead": days_ahead,
            "as_of": today_str,
        }
    except Exception as e:
        logger.error(f"Failed to get exam alerts: {e}")
        return {"alerts": [], "count": 0, "error": str(e)}


@api_router.get("/exams/categories")
async def exam_categories():
    """List all exam categories with counts."""
    db, mods = _get_exam_db()
    if not db:
        return {"categories": []}

    try:
        counts = db.get_count_by_field("exam_category")
        return {"categories": counts}
    except Exception as e:
        return {"categories": [], "error": str(e)}


@api_router.get("/exams/stats")
async def exam_stats():
    """Aggregated exam statistics."""
    db, mods = _get_exam_db()
    if not db:
        return {"error": "Exam database not available"}

    try:
        total = db.count_exams({})
        by_category = db.get_count_by_field("exam_category")
        by_status = db.get_count_by_field("exam_status")
        by_level = db.get_count_by_field("exam_level")

        # Upcoming deadlines in next 30 days
        today = date.today()
        cutoff = (today + timedelta(days=30)).isoformat()
        upcoming = db.get_exams_by_date_range(
            "application_end_date", today.isoformat(), cutoff
        )

        return {
            "total_exams": total,
            "by_category": by_category,
            "by_status": by_status,
            "by_level": by_level,
            "upcoming_deadlines_30d": len(upcoming),
        }
    except Exception as e:
        return {"total_exams": 0, "error": str(e)}


@api_router.get("/exams/{exam_id}")
async def get_exam_detail(exam_id: str):
    """Get full details for a single exam."""
    db, mods = _get_exam_db()
    if not db:
        raise HTTPException(status_code=503, detail="Exam database not available")

    try:
        exam = db.get_exam_by_id(exam_id)
        if not exam:
            raise HTTPException(status_code=404, detail="Exam not found")
        return exam
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
