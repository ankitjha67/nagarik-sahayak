"""
GovScheme SuperAgent â€” Exam Alert Engine (V3)
Generates urgency-ranked alerts for approaching deadlines, upcoming exams,
admit card releases, and result declarations.
"""
from __future__ import annotations
import json
import logging
from datetime import date, datetime, timedelta
from typing import Optional
from src.exams.exam_database import ExamDatabase
from src.exams.exam_models import (
    ExamDailyReport, ExamChangeType, ParsedExamData,
)
logger = logging.getLogger("ExamAlert")
class ExamAlertEngine:
    """Generates exam alerts across multiple urgency levels."""
    def __init__(self, db: ExamDatabase):
        self.db = db
        # Change tracking (populated during process_batch)
        self.new_exams: list[str] = []
        self.date_revised: list[str] = []
        self.vacancy_revised: list[str] = []
        self.fee_revised: list[str] = []
        self.unchanged_count: int = 0
        self.closed_count: int = 0
        self._seen_exam_ids: set[str] = set()
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # CHANGE DETECTION + TRACKING
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    def process_parsed_batch(
        self, parsed_exams: list[ParsedExamData], run_id: str,
    ) -> list[ParsedExamData]:
        """
        Upsert each exam into the DB, detect changes, and annotate.
        Returns the same list with change_type, first/last_seen_date set.
        """
        self._seen_exam_ids.clear()
        for exam in parsed_exams:
            exam_id = exam.exam_id
            self._seen_exam_ids.add(exam_id)
            change_type = self.db.upsert_exam(exam, run_id)
            exam.change_type = change_type
            # Track changes
            if change_type == ExamChangeType.New_Notification:
                self.new_exams.append(exam.clean_exam_name)
                exam.first_seen_date = date.today().isoformat()
            elif change_type == ExamChangeType.Date_Revised:
                self.date_revised.append(exam.clean_exam_name)
            elif change_type == ExamChangeType.Vacancy_Revised:
                self.vacancy_revised.append(exam.clean_exam_name)
            elif change_type == ExamChangeType.Fee_Revised:
                self.fee_revised.append(exam.clean_exam_name)
            elif change_type == ExamChangeType.Unchanged:
                self.unchanged_count += 1
            exam.last_seen_date = date.today().isoformat()
        # Mark exams not seen in this run as closed (after 3-day grace)
        self.closed_count = self.db.mark_missing_as_closed(run_id, self._seen_exam_ids)
        return parsed_exams
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # ALERT GENERATION
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    def generate_alerts(self, run_date: Optional[str] = None) -> dict:
        """
        Generate structured alerts for notification + Excel integration.
        Returns a dict of alert categories.
        """
        return {
            "application_closing_7d": self.db.get_approaching_deadlines(7),
            "application_closing_30d": self.db.get_approaching_deadlines(30),
            "exams_in_7d": self.db.get_upcoming_exams(7),
            "exams_in_30d": self.db.get_upcoming_exams(30),
            "application_open": self.db.get_application_open(),
            "admit_card_releasing": self._get_admit_card_alerts(),
            "results_expected": self._get_result_alerts(),
            "new_notifications": self.db.get_new_since(
                run_date or date.today().isoformat()
            ),
        }
    def _get_admit_card_alerts(self, days: int = 14) -> list[dict]:
        """Get exams where admit card is expected to release within N days."""
        today = date.today()
        cutoff = (today + timedelta(days=days)).isoformat()
        all_exams = self.db.get_all_exams()
        alerts = []
        for exam in all_exams:
            phases_raw = exam.get("phases_json")
            if not phases_raw:
                continue
            try:
                phases = json.loads(phases_raw)
            except (json.JSONDecodeError, TypeError):
                continue
            for phase in phases:
                ac_date = phase.get("admit_card_date")
                if ac_date and today.isoformat() <= ac_date <= cutoff:
                    alerts.append({
                        **exam,
                        "alert_phase": phase.get("phase_name", "Written"),
                        "alert_date": ac_date,
                        "alert_type": "Admit Card",
                    })
        return sorted(alerts, key=lambda x: x.get("alert_date", "9999"))
    def _get_result_alerts(self, days: int = 30) -> list[dict]:
        """Get exams where result is expected within N days."""
        today = date.today()
        cutoff = (today + timedelta(days=days)).isoformat()
        all_exams = self.db.get_all_exams()
        alerts = []
        for exam in all_exams:
            result_date = exam.get("result_date")
            final_result = exam.get("final_result_date")
            for rd_name, rd_val in [("Result", result_date), ("Final Result", final_result)]:
                if rd_val and today.isoformat() <= rd_val <= cutoff:
                    alerts.append({
                        **exam,
                        "alert_type": rd_name,
                        "alert_date": rd_val,
                    })
            # Also check phase-level results
            phases_raw = exam.get("phases_json")
            if phases_raw:
                try:
                    phases = json.loads(phases_raw)
                    for phase in phases:
                        pr = phase.get("result_date")
                        if pr and today.isoformat() <= pr <= cutoff:
                            alerts.append({
                                **exam,
                                "alert_type": f"Result ({phase.get('phase_name', '')})",
                                "alert_date": pr,
                            })
                except (json.JSONDecodeError, TypeError):
                    pass
        return sorted(alerts, key=lambda x: x.get("alert_date", "9999"))
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # URGENCY CLASSIFICATION
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    @staticmethod
    def get_urgency(days: Optional[int]) -> str:
        """Classify urgency based on days remaining."""
        if days is None:
            return "UNKNOWN"
        if days <= 2:
            return "CRITICAL"    # Red â€” immediate action
        if days <= 7:
            return "HIGH"        # Orange â€” this week
        if days <= 15:
            return "MEDIUM"      # Yellow â€” next two weeks
        return "LOW"             # Blue â€” more than 2 weeks
    @staticmethod
    def get_urgency_emoji(days: Optional[int]) -> str:
        """Emoji for urgency level."""
        if days is None:
            return "â“"
        if days <= 2:
            return "ðŸ”´"
        if days <= 7:
            return "ðŸŸ "
        if days <= 15:
            return "ðŸŸ¡"
        return "ðŸ”µ"
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # DAILY REPORT GENERATION
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    def generate_daily_report(
        self,
        run_id: str,
        run_started: datetime,
        run_completed: datetime,
        errors: int = 0,
    ) -> ExamDailyReport:
        """Create the daily exam report from current state."""
        stats = self.db.get_stats()
        app_closing_7 = self.db.get_approaching_deadlines(7)
        app_closing_30 = self.db.get_approaching_deadlines(30)
        exams_7d = self.db.get_upcoming_exams(7)
        exams_30d = self.db.get_upcoming_exams(30)
        app_open = self.db.get_application_open()
        report = ExamDailyReport(
            run_id=run_id,
            run_date=date.today().isoformat(),
            run_started_at=run_started,
            run_completed_at=run_completed,
            total_exams_in_db=self.db.get_total_count(),
            new_exams=len(self.new_exams),
            updated_exams=len(self.date_revised) + len(self.vacancy_revised) + len(self.fee_revised),
            date_revised_exams=len(self.date_revised),
            vacancy_revised_exams=len(self.vacancy_revised),
            closed_exams=self.closed_count,
            application_open_exams=len(app_open),
            deadlines_within_7_days=len(app_closing_7),
            deadlines_within_30_days=len(app_closing_30),
            exams_in_7_days=len(exams_7d),
            exams_in_30_days=len(exams_30d),
            errors=errors,
            elapsed_seconds=(run_completed - run_started).total_seconds(),
            new_exam_names=self.new_exams[:50],
            approaching_deadline_exams=[
                e.get("clean_exam_name", e.get("exam_name", ""))
                for e in app_closing_7[:20]
            ],
        )
        # Persist the run
        self.db.save_exam_run(report)
        return report
