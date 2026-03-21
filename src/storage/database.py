"""
GovScheme SuperAgent â€” Database Persistence Layer
SQLite-backed scheme registry that persists across daily crawl runs.
Tracks: first_seen, last_seen, detail_hash for change detection,
start/end dates, fees, status lifecycle.
"""
from __future__ import annotations
import json
import logging
import sqlite3
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional
from src.agents.models import (
    ClassifiedScheme, SchemeStatus, ChangeType, StoredScheme, DailyRunReport,
)
logger = logging.getLogger("db_layer")
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schemes (
    scheme_id        TEXT PRIMARY KEY,
    content_hash     TEXT NOT NULL,
    detail_hash      TEXT NOT NULL,
    clean_name       TEXT NOT NULL,
    level            TEXT NOT NULL,
    state            TEXT,
    sector           TEXT NOT NULL,
    scheme_type      TEXT NOT NULL,
    summary          TEXT,
    eligibility      TEXT,
    benefit_amount   TEXT,
    target_group     TEXT,
    source_portal    TEXT,
    source_url       TEXT,
    detail_url       TEXT,
    official_website TEXT,
    nodal_ministry   TEXT,
    nodal_department TEXT,
    helpline         TEXT,
    -- Dates
    start_date              TEXT,
    end_date                TEXT,
    application_start_date  TEXT,
    application_end_date    TEXT,
    application_deadline    TEXT,
    -- Fees & Amounts
    application_fee   TEXT,
    fund_amount_min   TEXT,
    fund_amount_max   TEXT,
    frequency         TEXT,
    -- Eligibility Details
    age_limit          TEXT,
    income_limit       TEXT,
    gender_eligibility TEXT,
    caste_eligibility  TEXT,
    documents_required TEXT,   -- JSON array
    -- Status & Lifecycle
    scheme_status          TEXT DEFAULT 'Unknown',
    classification_confidence REAL DEFAULT 0.0,
    folder_path            TEXT,
    -- Tracking
    first_seen_date  TEXT NOT NULL,
    last_seen_date   TEXT NOT NULL,
    last_crawl_run   TEXT,
    times_seen       INTEGER DEFAULT 1,
    change_type      TEXT DEFAULT 'New',
    is_active        INTEGER DEFAULT 1,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS daily_runs (
    run_id              TEXT PRIMARY KEY,
    run_date            TEXT NOT NULL,
    started_at          TEXT NOT NULL,
    completed_at        TEXT,
    total_in_db         INTEGER DEFAULT 0,
    new_schemes         INTEGER DEFAULT 0,
    updated_schemes     INTEGER DEFAULT 0,
    closed_schemes      INTEGER DEFAULT 0,
    unchanged_schemes   INTEGER DEFAULT 0,
    errors              INTEGER DEFAULT 0,
    elapsed_seconds     REAL DEFAULT 0.0,
    new_scheme_names    TEXT,        -- JSON array
    updated_scheme_names TEXT,       -- JSON array
    approaching_deadlines TEXT,      -- JSON array
    excel_report_path   TEXT,
    notes               TEXT
);
CREATE TABLE IF NOT EXISTS scheme_changes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    scheme_id       TEXT NOT NULL,
    run_id          TEXT NOT NULL,
    change_type     TEXT NOT NULL,
    field_changed   TEXT,
    old_value       TEXT,
    new_value       TEXT,
    detected_at     TEXT NOT NULL,
    FOREIGN KEY (scheme_id) REFERENCES schemes(scheme_id),
    FOREIGN KEY (run_id) REFERENCES daily_runs(run_id)
);
CREATE INDEX IF NOT EXISTS idx_schemes_level ON schemes(level);
CREATE INDEX IF NOT EXISTS idx_schemes_sector ON schemes(sector);
CREATE INDEX IF NOT EXISTS idx_schemes_state ON schemes(state);
CREATE INDEX IF NOT EXISTS idx_schemes_status ON schemes(scheme_status);
CREATE INDEX IF NOT EXISTS idx_schemes_end_date ON schemes(end_date);
CREATE INDEX IF NOT EXISTS idx_schemes_detail_hash ON schemes(detail_hash);
CREATE INDEX IF NOT EXISTS idx_changes_run ON scheme_changes(run_id);
CREATE INDEX IF NOT EXISTS idx_changes_scheme ON scheme_changes(scheme_id);
CREATE INDEX IF NOT EXISTS idx_runs_date ON daily_runs(run_date);
"""
class SchemeDatabase:
    """SQLite persistence for scheme tracking across daily runs."""
    def __init__(self, db_path: str = "./data/schemes.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    def _init_db(self) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.executescript(SCHEMA_SQL)
            conn.commit()
        logger.info("Database initialized at %s", self.db_path)
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Scheme CRUD
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def upsert_scheme(self, scheme: ClassifiedScheme, run_id: str) -> ChangeType:
        """Insert or update a scheme. Returns the change type detected."""
        now = datetime.utcnow().isoformat()
        today = date.today().isoformat()
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT scheme_id, detail_hash, scheme_status, last_seen_date, times_seen "
                "FROM schemes WHERE scheme_id = ? OR content_hash = ?",
                (scheme.scheme_id, scheme.raw_data.content_hash),
            ).fetchone()
            docs_json = json.dumps(scheme.documents_list, ensure_ascii=False)
            if existing is None:
                # â”€â”€ NEW SCHEME â”€â”€
                conn.execute("""
                    INSERT INTO schemes (
                        scheme_id, content_hash, detail_hash, clean_name, level, state,
                        sector, scheme_type, summary, eligibility, benefit_amount,
                        target_group, source_portal, source_url, detail_url,
                        official_website, nodal_ministry, nodal_department, helpline,
                        start_date, end_date, application_start_date, application_end_date,
                        application_deadline, application_fee, fund_amount_min,
                        fund_amount_max, frequency, age_limit, income_limit,
                        gender_eligibility, caste_eligibility, documents_required,
                        scheme_status, classification_confidence, folder_path,
                        first_seen_date, last_seen_date, last_crawl_run, times_seen,
                        change_type, is_active, created_at, updated_at
                    ) VALUES (
                        ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
                    )
                """, (
                    scheme.scheme_id, scheme.raw_data.content_hash,
                    scheme.raw_data.detail_hash, scheme.clean_name,
                    scheme.level.value, scheme.state, scheme.sector.value,
                    scheme.scheme_type.value, scheme.summary,
                    scheme.eligibility_summary, scheme.benefit_amount,
                    scheme.target_group, scheme.raw_data.source_portal,
                    scheme.raw_data.source_url, scheme.raw_data.scheme_detail_url,
                    scheme.official_website, scheme.nodal_ministry,
                    scheme.nodal_department, scheme.helpline,
                    scheme.start_date, scheme.end_date,
                    scheme.application_start_date, scheme.application_end_date,
                    scheme.application_deadline, scheme.application_fee,
                    scheme.fund_amount_min, scheme.fund_amount_max,
                    scheme.frequency, scheme.age_limit, scheme.income_limit,
                    scheme.gender_eligibility, scheme.caste_eligibility,
                    docs_json, scheme.scheme_status.value,
                    scheme.classification_confidence, scheme.folder_path,
                    today, today, run_id, 1,
                    ChangeType.NEW.value, 1, now, now,
                ))
                conn.commit()
                return ChangeType.NEW
            else:
                # â”€â”€ EXISTING SCHEME â€” check for changes â”€â”€
                old_hash = existing["detail_hash"]
                new_hash = scheme.raw_data.detail_hash
                times = existing["times_seen"] + 1
                if old_hash != new_hash:
                    change = ChangeType.UPDATED
                    # Log what changed
                    self._record_change(
                        conn, existing["scheme_id"], run_id, "detail_hash",
                        old_hash, new_hash,
                    )
                else:
                    change = ChangeType.UNCHANGED
                conn.execute("""
                    UPDATE schemes SET
                        detail_hash = ?, summary = ?, eligibility = ?,
                        benefit_amount = ?, start_date = ?, end_date = ?,
                        application_start_date = ?, application_end_date = ?,
                        application_deadline = ?, application_fee = ?,
                        fund_amount_min = ?, fund_amount_max = ?,
                        frequency = ?, scheme_status = ?,
                        last_seen_date = ?, last_crawl_run = ?,
                        times_seen = ?, change_type = ?, is_active = 1,
                        updated_at = ?
                    WHERE scheme_id = ?
                """, (
                    new_hash, scheme.summary, scheme.eligibility_summary,
                    scheme.benefit_amount, scheme.start_date, scheme.end_date,
                    scheme.application_start_date, scheme.application_end_date,
                    scheme.application_deadline, scheme.application_fee,
                    scheme.fund_amount_min, scheme.fund_amount_max,
                    scheme.frequency, scheme.scheme_status.value,
                    today, run_id, times, change.value, now,
                    existing["scheme_id"],
                ))
                conn.commit()
                return change
    def _record_change(
        self, conn: sqlite3.Connection, scheme_id: str, run_id: str,
        field: str, old_val: str, new_val: str,
    ) -> None:
        conn.execute(
            "INSERT INTO scheme_changes (scheme_id, run_id, change_type, "
            "field_changed, old_value, new_value, detected_at) "
            "VALUES (?, ?, 'Updated', ?, ?, ?, ?)",
            (scheme_id, run_id, field, old_val, new_val,
             datetime.utcnow().isoformat()),
        )
    def mark_missing_as_closed(self, run_id: str, seen_ids: set[str]) -> int:
        """Mark schemes not seen in this run as potentially Closed."""
        today = date.today().isoformat()
        with self._connect() as conn:
            all_active = conn.execute(
                "SELECT scheme_id FROM schemes WHERE is_active = 1"
            ).fetchall()
            closed_count = 0
            for row in all_active:
                sid = row["scheme_id"]
                if sid not in seen_ids:
                    # Only mark as closed if unseen for 3+ consecutive runs
                    last_seen = conn.execute(
                        "SELECT last_seen_date, times_seen FROM schemes WHERE scheme_id = ?",
                        (sid,),
                    ).fetchone()
                    if last_seen:
                        last = last_seen["last_seen_date"]
                        try:
                            days_unseen = (date.today() - date.fromisoformat(last)).days
                        except (ValueError, TypeError):
                            days_unseen = 0
                        if days_unseen >= 3:
                            conn.execute(
                                "UPDATE schemes SET scheme_status = 'Closed', "
                                "change_type = 'Closed', is_active = 0, updated_at = ? "
                                "WHERE scheme_id = ?",
                                (datetime.utcnow().isoformat(), sid),
                            )
                            self._record_change(
                                conn, sid, run_id, "scheme_status",
                                "Active", "Closed",
                            )
                            closed_count += 1
            conn.commit()
            return closed_count
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Queries for Reporting
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def get_all_schemes(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM schemes ORDER BY sector, clean_name"
            ).fetchall()
            return [dict(r) for r in rows]
    def get_schemes_by_status(self, status: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM schemes WHERE scheme_status = ? ORDER BY sector",
                (status,),
            ).fetchall()
            return [dict(r) for r in rows]
    def get_approaching_deadlines(self, days: int = 7) -> list[dict]:
        """Find schemes whose application_end_date or end_date is within N days."""
        cutoff = (date.today() + timedelta(days=days)).isoformat()
        today_str = date.today().isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM schemes WHERE is_active = 1 "
                "AND (application_end_date BETWEEN ? AND ? "
                "     OR end_date BETWEEN ? AND ?) "
                "ORDER BY COALESCE(application_end_date, end_date)",
                (today_str, cutoff, today_str, cutoff),
            ).fetchall()
            return [dict(r) for r in rows]
    def get_new_since(self, since_date: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM schemes WHERE first_seen_date >= ? ORDER BY first_seen_date DESC",
                (since_date,),
            ).fetchall()
            return [dict(r) for r in rows]
    def get_changes_for_run(self, run_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT sc.*, s.clean_name, s.sector, s.level "
                "FROM scheme_changes sc "
                "JOIN schemes s ON sc.scheme_id = s.scheme_id "
                "WHERE sc.run_id = ? ORDER BY sc.detected_at",
                (run_id,),
            ).fetchall()
            return [dict(r) for r in rows]
    def get_stats(self) -> dict:
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) as c FROM schemes").fetchone()["c"]
            active = conn.execute(
                "SELECT COUNT(*) as c FROM schemes WHERE is_active = 1"
            ).fetchone()["c"]
            by_level = {}
            for row in conn.execute(
                "SELECT level, COUNT(*) as c FROM schemes GROUP BY level"
            ).fetchall():
                by_level[row["level"]] = row["c"]
            by_sector = {}
            for row in conn.execute(
                "SELECT sector, COUNT(*) as c FROM schemes GROUP BY sector ORDER BY c DESC"
            ).fetchall():
                by_sector[row["sector"]] = row["c"]
            by_status = {}
            for row in conn.execute(
                "SELECT scheme_status, COUNT(*) as c FROM schemes GROUP BY scheme_status"
            ).fetchall():
                by_status[row["scheme_status"]] = row["c"]
            by_type = {}
            for row in conn.execute(
                "SELECT scheme_type, COUNT(*) as c FROM schemes GROUP BY scheme_type ORDER BY c DESC"
            ).fetchall():
                by_type[row["scheme_type"]] = row["c"]
            by_state = {}
            for row in conn.execute(
                "SELECT state, COUNT(*) as c FROM schemes WHERE state IS NOT NULL "
                "GROUP BY state ORDER BY c DESC"
            ).fetchall():
                by_state[row["state"]] = row["c"]
            return {
                "total": total,
                "active": active,
                "by_level": by_level,
                "by_sector": by_sector,
                "by_status": by_status,
                "by_type": by_type,
                "by_state": by_state,
            }
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Daily Run Tracking
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def save_daily_run(self, report: DailyRunReport) -> None:
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO daily_runs (
                    run_id, run_date, started_at, completed_at,
                    total_in_db, new_schemes, updated_schemes,
                    closed_schemes, unchanged_schemes, errors,
                    elapsed_seconds, new_scheme_names, updated_scheme_names,
                    approaching_deadlines, excel_report_path
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                report.run_id, report.run_date,
                report.run_started_at.isoformat(),
                report.run_completed_at.isoformat() if report.run_completed_at else None,
                report.total_schemes_in_db, report.new_schemes,
                report.updated_schemes, report.closed_schemes,
                report.unchanged_schemes, report.errors,
                report.elapsed_seconds,
                json.dumps(report.new_scheme_names, ensure_ascii=False),
                json.dumps(report.updated_scheme_names, ensure_ascii=False),
                json.dumps(report.approaching_deadline_names, ensure_ascii=False),
                report.excel_report_path,
            ))
            conn.commit()
    def get_run_history(self, limit: int = 30) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM daily_runs ORDER BY run_date DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
    def get_total_count(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) as c FROM schemes").fetchone()["c"]
