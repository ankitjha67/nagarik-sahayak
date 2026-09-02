"""
GovScheme SuperAgent â€” Exam Database (SQLite Persistence)
Tracks all government exams across daily runs with change detection.
Tables: exams (50+ cols), exam_changes (audit log), exam_runs (daily logs).
"""
from __future__ import annotations
import json
import logging
import sqlite3
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional
from src.exams.exam_models import (
    ParsedExamData, ExamChangeType, ExamStatus, ExamDailyReport,
)
logger = logging.getLogger("exam_database")
EXAM_SCHEMA = """
CREATE TABLE IF NOT EXISTS exams (
    exam_id                 TEXT PRIMARY KEY,
    exam_name               TEXT NOT NULL,
    clean_exam_name         TEXT,
    short_name              TEXT,
    conducting_body         TEXT NOT NULL,
    exam_category           TEXT NOT NULL,
    exam_level              TEXT NOT NULL DEFAULT 'Central',
    state                   TEXT,
    exam_cycle              TEXT,
    notification_date       TEXT,
    application_start_date  TEXT,
    application_end_date    TEXT,
    fee_payment_deadline    TEXT,
    correction_window_start TEXT,
    correction_window_end   TEXT,
    phases_json             TEXT,
    result_date             TEXT,
    interview_date          TEXT,
    final_result_date       TEXT,
    joining_date            TEXT,
    fee_general             REAL,
    fee_obc                 REAL,
    fee_sc_st               REAL,
    fee_female              REAL,
    fee_ews                 REAL,
    fee_pwd                 REAL,
    fee_note                TEXT,
    fee_payment_url         TEXT,
    is_free                 INTEGER DEFAULT 0,
    raw_fee_text            TEXT,
    vacancies_json          TEXT,
    total_vacancies         INTEGER,
    age_min                 INTEGER,
    age_max                 INTEGER,
    age_relaxation_obc      INTEGER,
    age_relaxation_sc_st    INTEGER,
    age_relaxation_pwd      INTEGER,
    qualification           TEXT,
    min_percentage          REAL,
    experience_years        INTEGER,
    physical_standards      TEXT,
    domicile_required       TEXT,
    gender_restriction      TEXT,
    official_notification_url TEXT,
    apply_online_url        TEXT,
    admit_card_url          TEXT,
    result_url              TEXT,
    syllabus_url            TEXT,
    official_website        TEXT,
    exam_status             TEXT DEFAULT 'Upcoming',
    change_type             TEXT DEFAULT 'New_Notification',
    detail_hash             TEXT NOT NULL,
    source_portal           TEXT,
    source_url              TEXT,
    first_seen_date         TEXT NOT NULL,
    last_seen_date          TEXT NOT NULL,
    last_crawl_run          TEXT,
    times_seen              INTEGER DEFAULT 1,
    is_active               INTEGER DEFAULT 1,
    parsing_confidence      REAL DEFAULT 0.0,
    folder_path             TEXT,
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS exam_changes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id         TEXT NOT NULL,
    run_id          TEXT NOT NULL,
    change_type     TEXT NOT NULL,
    field_changed   TEXT,
    old_value       TEXT,
    new_value       TEXT,
    detected_at     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS exam_runs (
    run_id              TEXT PRIMARY KEY,
    run_date            TEXT NOT NULL,
    started_at          TEXT NOT NULL,
    completed_at        TEXT,
    total_exams_in_db   INTEGER DEFAULT 0,
    new_exams           INTEGER DEFAULT 0,
    updated_exams       INTEGER DEFAULT 0,
    closed_exams        INTEGER DEFAULT 0,
    errors              INTEGER DEFAULT 0,
    elapsed_seconds     REAL DEFAULT 0.0,
    new_exam_names      TEXT,
    excel_sheet_path    TEXT
);
CREATE INDEX IF NOT EXISTS idx_exams_category ON exams(exam_category);
CREATE INDEX IF NOT EXISTS idx_exams_level ON exams(exam_level);
CREATE INDEX IF NOT EXISTS idx_exams_state ON exams(state);
CREATE INDEX IF NOT EXISTS idx_exams_status ON exams(exam_status);
CREATE INDEX IF NOT EXISTS idx_exams_app_end ON exams(application_end_date);
CREATE INDEX IF NOT EXISTS idx_exams_body ON exams(conducting_body);
CREATE INDEX IF NOT EXISTS idx_exams_hash ON exams(detail_hash);
CREATE INDEX IF NOT EXISTS idx_exams_active ON exams(is_active);
CREATE INDEX IF NOT EXISTS idx_exam_changes_run ON exam_changes(run_id);
CREATE INDEX IF NOT EXISTS idx_exam_runs_date ON exam_runs(run_date);
"""
class ExamDatabase:
    """SQLite persistence for government exam tracking."""
    def __init__(self, db_path: str = "./data/exams.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    def _init_db(self) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.executescript(EXAM_SCHEMA)
            conn.commit()
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    # â”€â”€â”€ Upsert â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def upsert_exam(self, parsed: ParsedExamData, run_id: str) -> ExamChangeType:
        """Insert or update an exam. Returns the change type detected."""
        now = datetime.utcnow().isoformat()
        today = date.today().isoformat()
        exam_id = parsed.exam_id
        phases_json = json.dumps(
            [p.model_dump(mode="json") for p in parsed.phases],
            ensure_ascii=False,
        )
        vacancies_json = json.dumps(
            [v.model_dump(mode="json") for v in parsed.vacancies],
            ensure_ascii=False,
        )
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT * FROM exams WHERE exam_id = ?", (exam_id,)
            ).fetchone()
            if existing is None:
                # New exam
                conn.execute("""
                    INSERT INTO exams (
                        exam_id, exam_name, clean_exam_name, short_name,
                        conducting_body, exam_category, exam_level, state, exam_cycle,
                        notification_date, application_start_date, application_end_date,
                        fee_payment_deadline, correction_window_start, correction_window_end,
                        phases_json, result_date, interview_date, final_result_date, joining_date,
                        fee_general, fee_obc, fee_sc_st, fee_female, fee_ews, fee_pwd,
                        fee_note, fee_payment_url, is_free, raw_fee_text,
                        vacancies_json, total_vacancies,
                        age_min, age_max, age_relaxation_obc, age_relaxation_sc_st,
                        age_relaxation_pwd, qualification, min_percentage,
                        experience_years, physical_standards, domicile_required, gender_restriction,
                        official_notification_url, apply_online_url, admit_card_url,
                        result_url, syllabus_url, official_website,
                        exam_status, change_type, detail_hash,
                        source_portal, source_url,
                        first_seen_date, last_seen_date, last_crawl_run,
                        times_seen, is_active, parsing_confidence, folder_path,
                        created_at, updated_at
                    ) VALUES (
                        ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,
                        ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,
                        ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
                    )
                """, (
                    exam_id, parsed.raw.exam_name, parsed.clean_exam_name, parsed.short_name,
                    parsed.raw.conducting_body, parsed.exam_category.value,
                    parsed.exam_level.value, parsed.state, parsed.exam_cycle,
                    parsed.notification_date, parsed.application_start_date,
                    parsed.application_end_date, parsed.fee_payment_deadline,
                    parsed.correction_window_start, parsed.correction_window_end,
                    phases_json, parsed.result_date, parsed.interview_date,
                    parsed.final_result_date, parsed.joining_date,
                    parsed.fee.general, parsed.fee.obc, parsed.fee.sc_st,
                    parsed.fee.female, parsed.fee.ews, parsed.fee.pwd,
                    parsed.fee.fee_note, parsed.fee.fee_payment_url,
                    int(parsed.fee.is_free), parsed.fee.raw_fee_text,
                    vacancies_json, parsed.total_vacancies,
                    parsed.eligibility.age_min, parsed.eligibility.age_max,
                    parsed.eligibility.age_relaxation_obc,
                    parsed.eligibility.age_relaxation_sc_st,
                    parsed.eligibility.age_relaxation_pwd,
                    parsed.eligibility.qualification,
                    parsed.eligibility.min_percentage,
                    parsed.eligibility.experience_years,
                    parsed.eligibility.physical_standards,
                    parsed.eligibility.domicile_required,
                    parsed.eligibility.gender_restriction,
                    parsed.official_notification_url, parsed.apply_online_url,
                    parsed.admit_card_url, parsed.result_url,
                    parsed.syllabus_url, parsed.official_website,
                    parsed.exam_status.value,
                    ExamChangeType.New_Notification.value,
                    parsed.raw.detail_hash,
                    parsed.raw.source_portal, parsed.raw.source_url,
                    today, today, run_id,
                    1, 1, parsed.parsing_confidence, parsed.folder_path,
                    now, now,
                ))
                conn.commit()
                return ExamChangeType.New_Notification
            # Existing â€” check for changes
            old_hash = existing["detail_hash"]
            new_hash = parsed.raw.detail_hash
            if old_hash == new_hash:
                # Unchanged
                conn.execute("""
                    UPDATE exams SET
                        last_seen_date = ?, last_crawl_run = ?,
                        times_seen = times_seen + 1,
                        change_type = ?, updated_at = ?
                    WHERE exam_id = ?
                """, (today, run_id, ExamChangeType.Unchanged.value, now, exam_id))
                conn.commit()
                return ExamChangeType.Unchanged
            # Changed â€” determine what changed
            change_type = ExamChangeType.Notification_Amended
            changes_detected = []
            # Date changes
            date_fields = [
                ("application_start_date", parsed.application_start_date),
                ("application_end_date", parsed.application_end_date),
                ("fee_payment_deadline", parsed.fee_payment_deadline),
                ("result_date", parsed.result_date),
                ("final_result_date", parsed.final_result_date),
            ]
            for field_name, new_val in date_fields:
                old_val = existing[field_name]
                if str(new_val or "") != str(old_val or ""):
                    changes_detected.append((field_name, old_val, new_val))
                    change_type = ExamChangeType.Date_Revised
            # Vacancy changes
            old_vacancies = existing["total_vacancies"]
            if parsed.total_vacancies and old_vacancies != parsed.total_vacancies:
                changes_detected.append(("total_vacancies", old_vacancies, parsed.total_vacancies))
                if change_type != ExamChangeType.Date_Revised:
                    change_type = ExamChangeType.Vacancy_Revised
            # Fee changes
            old_fee = existing["fee_general"]
            if parsed.fee.general and old_fee != parsed.fee.general:
                changes_detected.append(("fee_general", old_fee, parsed.fee.general))
                if change_type not in (ExamChangeType.Date_Revised, ExamChangeType.Vacancy_Revised):
                    change_type = ExamChangeType.Fee_Revised
            # Status change
            old_status = existing["exam_status"]
            if parsed.exam_status.value != old_status:
                changes_detected.append(("exam_status", old_status, parsed.exam_status.value))
                if not changes_detected:
                    change_type = ExamChangeType.Status_Changed
            # Record changes
            for field_name, old_val, new_val in changes_detected:
                conn.execute("""
                    INSERT INTO exam_changes (exam_id, run_id, change_type, field_changed, old_value, new_value, detected_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (exam_id, run_id, change_type.value, field_name,
                      str(old_val)[:500] if old_val else None,
                      str(new_val)[:500] if new_val else None, now))
            # Update the exam record
            conn.execute("""
                UPDATE exams SET
                    clean_exam_name = ?, short_name = ?,
                    notification_date = ?, application_start_date = ?,
                    application_end_date = ?, fee_payment_deadline = ?,
                    correction_window_start = ?, correction_window_end = ?,
                    phases_json = ?, result_date = ?, interview_date = ?,
                    final_result_date = ?, joining_date = ?,
                    fee_general = ?, fee_obc = ?, fee_sc_st = ?,
                    fee_female = ?, fee_ews = ?, fee_pwd = ?,
                    fee_note = ?, is_free = ?, raw_fee_text = ?,
                    vacancies_json = ?, total_vacancies = ?,
                    age_min = ?, age_max = ?, qualification = ?,
                    physical_standards = ?,
                    official_notification_url = ?, apply_online_url = ?,
                    admit_card_url = ?, result_url = ?, syllabus_url = ?,
                    exam_status = ?, change_type = ?, detail_hash = ?,
                    last_seen_date = ?, last_crawl_run = ?,
                    times_seen = times_seen + 1,
                    parsing_confidence = ?, updated_at = ?
                WHERE exam_id = ?
            """, (
                parsed.clean_exam_name, parsed.short_name,
                parsed.notification_date, parsed.application_start_date,
                parsed.application_end_date, parsed.fee_payment_deadline,
                parsed.correction_window_start, parsed.correction_window_end,
                phases_json, parsed.result_date, parsed.interview_date,
                parsed.final_result_date, parsed.joining_date,
                parsed.fee.general, parsed.fee.obc, parsed.fee.sc_st,
                parsed.fee.female, parsed.fee.ews, parsed.fee.pwd,
                parsed.fee.fee_note, int(parsed.fee.is_free), parsed.fee.raw_fee_text,
                vacancies_json, parsed.total_vacancies,
                parsed.eligibility.age_min, parsed.eligibility.age_max,
                parsed.eligibility.qualification,
                parsed.eligibility.physical_standards,
                parsed.official_notification_url, parsed.apply_online_url,
                parsed.admit_card_url, parsed.result_url, parsed.syllabus_url,
                parsed.exam_status.value, change_type.value, parsed.raw.detail_hash,
                today, run_id, parsed.parsing_confidence, now,
                exam_id,
            ))
            conn.commit()
            logger.info("Exam %s updated: %s (%d field changes)", exam_id, change_type.value, len(changes_detected))
            return change_type
    # â”€â”€â”€ Closure Detection â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def mark_missing_as_closed(self, run_id: str, seen_exam_ids: set[str]) -> int:
        """Mark exams not seen for 3+ consecutive days as inactive."""
        today = date.today()
        cutoff = (today - timedelta(days=3)).isoformat()
        now = datetime.utcnow().isoformat()
        closed_count = 0
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT exam_id, last_seen_date FROM exams WHERE is_active = 1"
            ).fetchall()
            for row in rows:
                if row["exam_id"] in seen_exam_ids:
                    continue
                if row["last_seen_date"] and row["last_seen_date"] <= cutoff:
                    conn.execute("""
                        UPDATE exams SET
                            is_active = 0, exam_status = 'Completed',
                            change_type = 'Status_Changed', updated_at = ?
                        WHERE exam_id = ?
                    """, (now, row["exam_id"]))
                    conn.execute("""
                        INSERT INTO exam_changes (exam_id, run_id, change_type, field_changed, old_value, new_value, detected_at)
                        VALUES (?, ?, 'Status_Changed', 'exam_status', 'Active', 'Completed', ?)
                    """, (row["exam_id"], run_id, now))
                    closed_count += 1
            conn.commit()
        if closed_count:
            logger.info("Marked %d exams as closed (unseen for 3+ days)", closed_count)
        return closed_count
    # â”€â”€â”€ Query Methods â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def get_all_exams(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM exams ORDER BY exam_category, clean_exam_name"
            ).fetchall()
        return [dict(r) for r in rows]
    def get_new_since(self, since_date: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM exams WHERE first_seen_date >= ? ORDER BY exam_category",
                (since_date,),
            ).fetchall()
        return [dict(r) for r in rows]
    def get_application_open(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM exams WHERE exam_status = 'Application_Open' AND is_active = 1 ORDER BY application_end_date",
            ).fetchall()
        return [dict(r) for r in rows]
    def get_approaching_deadlines(self, days: int = 7) -> list[dict]:
        cutoff = (date.today() + timedelta(days=days)).isoformat()
        today_str = date.today().isoformat()
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT * FROM exams
                WHERE application_end_date IS NOT NULL
                  AND application_end_date >= ?
                  AND application_end_date <= ?
                  AND is_active = 1
                ORDER BY application_end_date
            """, (today_str, cutoff)).fetchall()
        return [dict(r) for r in rows]
    def get_upcoming_exams(self, days: int = 30) -> list[dict]:
        """Get exams with exam dates within N days (checks phases_json)."""
        today = date.today()
        cutoff = (today + timedelta(days=days)).isoformat()
        today_str = today.isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM exams WHERE phases_json IS NOT NULL AND is_active = 1"
            ).fetchall()
        results = []
        for row in rows:
            try:
                phases = json.loads(row["phases_json"])
                for phase in phases:
                    exam_start = phase.get("exam_date_start")
                    if exam_start and today_str <= exam_start <= cutoff:
                        results.append(dict(row))
                        break
            except (json.JSONDecodeError, TypeError):
                continue
        return sorted(results, key=lambda x: x.get("application_end_date") or "9999")
    def get_by_category(self, category: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM exams WHERE exam_category = ? AND is_active = 1 ORDER BY clean_exam_name",
                (category,),
            ).fetchall()
        return [dict(r) for r in rows]
    def get_by_conducting_body(self, body: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM exams WHERE conducting_body = ? AND is_active = 1",
                (body,),
            ).fetchall()
        return [dict(r) for r in rows]
    def get_by_state(self, state: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM exams WHERE state = ? AND is_active = 1 ORDER BY exam_category",
                (state,),
            ).fetchall()
        return [dict(r) for r in rows]
    def get_changes_for_run(self, run_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT ec.*, e.clean_exam_name, e.exam_category, e.conducting_body
                FROM exam_changes ec
                LEFT JOIN exams e ON ec.exam_id = e.exam_id
                WHERE ec.run_id = ?
                ORDER BY ec.detected_at DESC
            """, (run_id,)).fetchall()
        return [dict(r) for r in rows]
    def get_stats(self) -> dict:
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM exams").fetchone()[0]
            active = conn.execute("SELECT COUNT(*) FROM exams WHERE is_active = 1").fetchone()[0]
            by_category = {}
            for row in conn.execute(
                "SELECT exam_category, COUNT(*) as cnt FROM exams WHERE is_active = 1 GROUP BY exam_category ORDER BY cnt DESC"
            ).fetchall():
                by_category[row["exam_category"]] = row["cnt"]
            by_level = {}
            for row in conn.execute(
                "SELECT exam_level, COUNT(*) as cnt FROM exams WHERE is_active = 1 GROUP BY exam_level"
            ).fetchall():
                by_level[row["exam_level"]] = row["cnt"]
            by_status = {}
            for row in conn.execute(
                "SELECT exam_status, COUNT(*) as cnt FROM exams WHERE is_active = 1 GROUP BY exam_status"
            ).fetchall():
                by_status[row["exam_status"]] = row["cnt"]
            by_body = {}
            for row in conn.execute(
                "SELECT conducting_body, COUNT(*) as cnt FROM exams WHERE is_active = 1 GROUP BY conducting_body ORDER BY cnt DESC"
            ).fetchall():
                by_body[row["conducting_body"]] = row["cnt"]
            by_state = {}
            for row in conn.execute(
                "SELECT state, COUNT(*) as cnt FROM exams WHERE state IS NOT NULL AND is_active = 1 GROUP BY state ORDER BY cnt DESC"
            ).fetchall():
                by_state[row["state"]] = row["cnt"]
        return {
            "total": total, "active": active,
            "by_category": by_category, "by_level": by_level,
            "by_status": by_status, "by_body": by_body, "by_state": by_state,
        }
    # â”€â”€â”€ Run Management â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def save_exam_run(self, report: ExamDailyReport) -> None:
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO exam_runs (
                    run_id, run_date, started_at, completed_at,
                    total_exams_in_db, new_exams, updated_exams,
                    closed_exams, errors, elapsed_seconds,
                    new_exam_names, excel_sheet_path
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                report.run_id, report.run_date,
                report.run_started_at.isoformat() if report.run_started_at else now,
                report.run_completed_at.isoformat() if report.run_completed_at else now,
                report.total_exams_in_db, report.new_exams,
                report.updated_exams, report.closed_exams,
                report.errors, report.elapsed_seconds,
                json.dumps(report.new_exam_names[:50], ensure_ascii=False),
                report.excel_sheet_path,
            ))
            conn.commit()
    def get_run_history(self, limit: int = 60) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM exam_runs ORDER BY run_date DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
    def get_total_count(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM exams").fetchone()[0]
