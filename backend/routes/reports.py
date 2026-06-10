"""Report routes — Excel downloads and notification dispatch."""
import asyncio
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from fastapi import HTTPException
from fastapi.responses import FileResponse
from routes import api_router
from services import v3_bridge

logger = logging.getLogger(__name__)

EXCEL_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _generate_excel(include_exams: bool) -> str | None:
    """Blocking: generate the Excel workbook, return its file path."""
    mods = v3_bridge.get_v3_modules()
    if not mods:
        return None
    try:
        from src.storage.excel_report import ExcelReportGenerator
    except ImportError as e:
        logger.warning(f"openpyxl/excel_report not available: {e}")
        return None

    config = mods["AgentConfig"]()
    db = mods["SchemeDatabase"](config.db_path)
    exam_db = mods["ExamDatabase"](config.exam_db_path) if include_exams else None

    # Write to a temp dir; generator saves to <output_dir>/reports/<name>.xlsx
    tmp_dir = Path(tempfile.gettempdir()) / "ns_reports"
    generator = ExcelReportGenerator(db, output_dir=str(tmp_dir), exam_db=exam_db)
    return generator.generate_full_report()


@api_router.get("/reports/schemes-excel")
async def download_schemes_excel():
    """Generate and download a comprehensive Excel report of all schemes."""
    try:
        filepath = await asyncio.to_thread(_generate_excel, False)
    except Exception as e:
        logger.error(f"Excel report generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    if not filepath:
        raise HTTPException(status_code=503, detail="Report modules not available")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return FileResponse(
        path=filepath,
        media_type=EXCEL_MEDIA_TYPE,
        filename=f"GovScheme_Report_{timestamp}.xlsx",
    )


@api_router.get("/reports/exams-excel")
async def download_exams_excel():
    """Generate and download an Excel report including exam sheets."""
    try:
        filepath = await asyncio.to_thread(_generate_excel, True)
    except Exception as e:
        logger.error(f"Exam Excel report failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    if not filepath:
        raise HTTPException(status_code=503, detail="Report modules not available")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return FileResponse(
        path=filepath,
        media_type=EXCEL_MEDIA_TYPE,
        filename=f"GovExam_Report_{timestamp}.xlsx",
    )


@api_router.get("/reports/notification-config")
async def get_notification_config():
    """Return current notification channel configuration status."""
    try:
        from src.notifications.email_sender import NotificationConfig
    except ImportError:
        return {"email_enabled": False, "slack_enabled": False}

    config = NotificationConfig()
    return {
        "email_enabled": config.email_enabled,
        "email_to": config.email_to,
        "slack_enabled": config.slack_enabled,
        "slack_channel": config.slack_channel,
        "file_drop_dir": config.file_drop_dir or None,
    }


@api_router.post("/reports/send-alert")
async def send_scheme_alert(req: dict | None = None):
    """Dispatch the latest daily run report via configured channels (email/Slack)."""
    req = req or {}

    def _work():
        mods = v3_bridge.get_v3_modules()
        if not mods:
            return {"error": "V3 modules not available"}
        try:
            from src.notifications.email_sender import (
                NotificationDispatcher, NotificationConfig,
            )
            from src.agents.models import DailyRunReport
        except ImportError as e:
            return {"error": f"Notification modules not available: {e}"}

        config = NotificationConfig()
        email_to = req.get("email_to")
        if email_to:
            config.email_to = [email_to] if isinstance(email_to, str) else list(email_to)

        agent_config = mods["AgentConfig"]()
        db = mods["SchemeDatabase"](agent_config.db_path)
        runs = db.get_run_history(limit=1)
        if not runs:
            return {"error": "No crawl runs recorded yet — run a discovery crawl first"}

        run = runs[0]
        # Reconstruct a DailyRunReport from the persisted run row
        import json as _json

        def _parse_list(val):
            if not val:
                return []
            try:
                return _json.loads(val) if isinstance(val, str) else list(val)
            except (ValueError, TypeError):
                return []

        def _parse_dt(val):
            if not val:
                return datetime.now(timezone.utc)
            try:
                return datetime.fromisoformat(str(val))
            except (ValueError, TypeError):
                return datetime.now(timezone.utc)

        report = DailyRunReport(
            run_id=run.get("run_id", "unknown"),
            run_date=run.get("run_date", ""),
            run_started_at=_parse_dt(run.get("started_at")),
            run_completed_at=_parse_dt(run.get("completed_at")) if run.get("completed_at") else None,
            total_schemes_in_db=run.get("total_in_db", 0) or 0,
            new_schemes=run.get("new_schemes", 0) or 0,
            updated_schemes=run.get("updated_schemes", 0) or 0,
            closed_schemes=run.get("closed_schemes", 0) or 0,
            unchanged_schemes=run.get("unchanged_schemes", 0) or 0,
            errors=run.get("errors", 0) or 0,
            elapsed_seconds=run.get("elapsed_seconds", 0.0) or 0.0,
            new_scheme_names=_parse_list(run.get("new_scheme_names")),
            updated_scheme_names=_parse_list(run.get("updated_scheme_names")),
            approaching_deadline_names=_parse_list(run.get("approaching_deadlines")),
        )

        dispatcher = NotificationDispatcher(config)
        excel_path = run.get("excel_report_path") or ""
        results = dispatcher.dispatch(report, excel_path)
        return {
            "success": any(results.values()) if results else False,
            "channels": results,
            "run_id": report.run_id,
        }

    result = await asyncio.to_thread(_work)
    if "error" in result:
        raise HTTPException(status_code=503, detail=result["error"])
    return result
