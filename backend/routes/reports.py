"""Report routes — Excel downloads and notification preferences."""
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from fastapi import HTTPException
from fastapi.responses import FileResponse
from routes import api_router

logger = logging.getLogger(__name__)


def _get_report_modules():
    """Lazy-import V3 report modules."""
    try:
        import sys
        project_root = str(Path(__file__).resolve().parent.parent.parent)
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        from src.storage.excel_report import ExcelReportGenerator
        from src.storage.database import SchemeDatabase
        from src.exams.exam_database import ExamDatabase
        from src.config.settings import AgentConfig
        from src.notifications.email_sender import NotificationDispatcher, NotificationConfig
        return {
            "ExcelReportGenerator": ExcelReportGenerator,
            "SchemeDatabase": SchemeDatabase,
            "ExamDatabase": ExamDatabase,
            "AgentConfig": AgentConfig,
            "NotificationDispatcher": NotificationDispatcher,
            "NotificationConfig": NotificationConfig,
        }
    except ImportError as e:
        logger.warning(f"V3 report modules not available: {e}")
        return None


@api_router.get("/reports/schemes-excel")
async def download_schemes_excel():
    """Generate and download comprehensive Excel report of all schemes."""
    mods = _get_report_modules()
    if not mods:
        raise HTTPException(status_code=503, detail="Report modules not available")

    try:
        config = mods["AgentConfig"]()
        db = mods["SchemeDatabase"](config.output_dir / "schemes.db")
        generator = mods["ExcelReportGenerator"](db)

        # Generate to temp file
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_path = Path(tempfile.gettempdir()) / f"govscheme_report_{timestamp}.xlsx"
        generator.generate_full_report(str(output_path))

        return FileResponse(
            path=str(output_path),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=f"GovScheme_Report_{timestamp}.xlsx",
        )
    except Exception as e:
        logger.error(f"Excel report generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/reports/exams-excel")
async def download_exams_excel():
    """Generate and download Excel report of all tracked exams."""
    mods = _get_report_modules()
    if not mods:
        raise HTTPException(status_code=503, detail="Report modules not available")

    try:
        config = mods["AgentConfig"]()
        db = mods["SchemeDatabase"](config.output_dir / "schemes.db")
        exam_db = mods["ExamDatabase"](config.output_dir / "exams.db")
        generator = mods["ExcelReportGenerator"](db, exam_db=exam_db)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_path = Path(tempfile.gettempdir()) / f"exam_report_{timestamp}.xlsx"
        generator.generate_full_report(str(output_path), include_exams=True)

        return FileResponse(
            path=str(output_path),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=f"GovExam_Report_{timestamp}.xlsx",
        )
    except Exception as e:
        logger.error(f"Exam Excel report failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/reports/notification-config")
async def get_notification_config():
    """Return current notification configuration status."""
    mods = _get_report_modules()
    if not mods:
        return {"email_enabled": False, "slack_enabled": False}

    config = mods["NotificationConfig"]()
    return {
        "email_enabled": config.email_enabled,
        "email_to": config.email_to,
        "slack_enabled": config.slack_enabled,
        "slack_channel": config.slack_channel,
        "file_drop_dir": config.file_drop_dir or None,
    }


@api_router.post("/reports/send-alert")
async def send_scheme_alert(req: dict = {}):
    """Send a notification alert (email/slack) about schemes/exams."""
    mods = _get_report_modules()
    if not mods:
        raise HTTPException(status_code=503, detail="Notification modules not available")

    alert_type = req.get("type", "schemes")  # schemes | exams | custom
    email_to = req.get("email_to")  # Override recipients
    message = req.get("message", "")

    try:
        config = mods["NotificationConfig"]()
        if email_to:
            config.email_to = [email_to] if isinstance(email_to, str) else email_to

        dispatcher = mods["NotificationDispatcher"](config)

        if alert_type == "custom" and message:
            dispatcher.send_custom_alert(subject="Nagarik Sahayak Alert", body=message)
        else:
            # Generate and send daily report
            agent_config = mods["AgentConfig"]()
            db = mods["SchemeDatabase"](agent_config.output_dir / "schemes.db")
            report = db.get_latest_run_report()
            if report:
                dispatcher.send_daily_report(report)

        return {"success": True, "channels": {
            "email": config.email_enabled,
            "slack": config.slack_enabled,
        }}
    except Exception as e:
        logger.error(f"Alert send failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
