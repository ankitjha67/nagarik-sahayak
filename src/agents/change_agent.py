"""
GovScheme SuperAgent â€” Change Detection Agent
Compares freshly crawled schemes against the persistent database
to detect: new launches, updates, closures, and approaching deadlines.
"""
from __future__ import annotations
import logging
from datetime import date, timedelta
from typing import Optional
from src.agents.models import (
    ClassifiedScheme, ChangeType, SchemeStatus, DailyRunReport,
)
from src.storage.database import SchemeDatabase
logger = logging.getLogger("change_agent")
class ChangeDetectionAgent:
    """
    The Intelligence Agent â€” compares each crawl run against
    the persistent database to produce a delta report:
      - NEW:    scheme_id not in DB
      - UPDATED: scheme exists but detail_hash has changed
      - CLOSED:  scheme was in DB but not seen for 3+ consecutive days
      - DEADLINE_APPROACHING: end_date or application_end_date within 7/30 days
      - UNCHANGED: scheme exists and detail_hash matches
    """
    def __init__(self, db: SchemeDatabase):
        self.db = db
        self.new_schemes: list[str] = []
        self.updated_schemes: list[str] = []
        self.closed_schemes: list[str] = []
        self.approaching_7d: list[str] = []
        self.approaching_30d: list[str] = []
        self.unchanged_count: int = 0
    def process_classified_batch(
        self,
        schemes: list[ClassifiedScheme],
        run_id: str,
    ) -> list[ClassifiedScheme]:
        """
        Process a batch of classified schemes through change detection.
        Updates each scheme's change_type, scheme_status, and days_until_deadline.
        Persists to database. Returns the annotated schemes.
        """
        seen_ids: set[str] = set()
        annotated: list[ClassifiedScheme] = []
        for scheme in schemes:
            # Compute deadline proximity
            scheme.days_until_deadline = self._compute_days_until_deadline(scheme)
            # Infer status from dates
            scheme.scheme_status = self._infer_status(scheme)
            # Upsert into DB and detect change type
            change = self.db.upsert_scheme(scheme, run_id)
            scheme.change_type = change
            # Track for reporting
            seen_ids.add(scheme.scheme_id)
            if change == ChangeType.NEW:
                self.new_schemes.append(scheme.clean_name)
            elif change == ChangeType.UPDATED:
                self.updated_schemes.append(scheme.clean_name)
            elif change == ChangeType.UNCHANGED:
                self.unchanged_count += 1
            # Track approaching deadlines
            if scheme.days_until_deadline is not None:
                if 0 <= scheme.days_until_deadline <= 7:
                    self.approaching_7d.append(scheme.clean_name)
                    scheme.change_type = ChangeType.DEADLINE_APPROACHING
                elif 0 <= scheme.days_until_deadline <= 30:
                    self.approaching_30d.append(scheme.clean_name)
            annotated.append(scheme)
        # Mark schemes not seen in this run as potentially closed
        closed_count = self.db.mark_missing_as_closed(run_id, seen_ids)
        self.closed_schemes = [f"({closed_count} schemes marked closed)"]
        logger.info(
            "Change detection complete: %d new, %d updated, %d unchanged, "
            "%d closed, %d deadline-approaching",
            len(self.new_schemes), len(self.updated_schemes),
            self.unchanged_count, closed_count, len(self.approaching_7d),
        )
        return annotated
    def generate_daily_report(
        self,
        run_id: str,
        run_started_at,
        run_completed_at,
        errors: int = 0,
    ) -> DailyRunReport:
        """Generate the daily run summary report."""
        stats = self.db.get_stats()
        elapsed = 0.0
        if run_started_at and run_completed_at:
            elapsed = (run_completed_at - run_started_at).total_seconds()
        report = DailyRunReport(
            run_id=run_id,
            run_date=date.today().isoformat(),
            run_started_at=run_started_at,
            run_completed_at=run_completed_at,
            total_schemes_in_db=stats["total"],
            new_schemes=len(self.new_schemes),
            updated_schemes=len(self.updated_schemes),
            closed_schemes=len(self.closed_schemes),
            unchanged_schemes=self.unchanged_count,
            deadlines_within_7_days=len(self.approaching_7d),
            deadlines_within_30_days=len(self.approaching_30d),
            active_schemes=stats.get("active", 0),
            expired_schemes=stats.get("by_status", {}).get("Expired", 0),
            errors=errors,
            elapsed_seconds=elapsed,
            new_scheme_names=self.new_schemes[:50],
            updated_scheme_names=self.updated_schemes[:50],
            approaching_deadline_names=self.approaching_7d[:50],
        )
        # Persist the run report
        self.db.save_daily_run(report)
        return report
    def _compute_days_until_deadline(self, scheme: ClassifiedScheme) -> Optional[int]:
        """Compute days remaining until the closest deadline."""
        today = date.today()
        candidates = [
            scheme.application_end_date,
            scheme.end_date,
            scheme.application_deadline,
        ]
        min_days = None
        for d in candidates:
            if not d:
                continue
            try:
                # Try ISO format first
                deadline = date.fromisoformat(d.strip()[:10])
                days = (deadline - today).days
                if min_days is None or days < min_days:
                    min_days = days
            except (ValueError, TypeError):
                # Try common Indian date formats
                for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%B %d, %Y", "%d %B %Y"]:
                    try:
                        from datetime import datetime as dt
                        deadline = dt.strptime(d.strip(), fmt).date()
                        days = (deadline - today).days
                        if min_days is None or days < min_days:
                            min_days = days
                        break
                    except (ValueError, TypeError):
                        continue
        return min_days
    def _infer_status(self, scheme: ClassifiedScheme) -> SchemeStatus:
        """Infer scheme status from its dates."""
        today = date.today()
        # Check end date / application end date
        for d_str in [scheme.end_date, scheme.application_end_date]:
            if d_str:
                try:
                    end = date.fromisoformat(d_str.strip()[:10])
                    if end < today:
                        return SchemeStatus.EXPIRED
                except (ValueError, TypeError):
                    pass
        # Check start date
        if scheme.start_date:
            try:
                start = date.fromisoformat(scheme.start_date.strip()[:10])
                if start > today:
                    return SchemeStatus.UPCOMING
            except (ValueError, TypeError):
                pass
        # If we have dates and scheme is within range
        if scheme.start_date or scheme.end_date:
            return SchemeStatus.ACTIVE
        return SchemeStatus.UNKNOWN
