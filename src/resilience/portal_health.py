"""
GovScheme SuperAgent â€” Portal Health Monitor + Circuit Breaker
Tracks per-portal reliability across runs. Implements circuit breaker
to skip portals that are consistently failing, saving time and avoiding
IP bans from hammering broken sites.
States:
  CLOSED  â†’ portal is healthy, allow requests
  OPEN    â†’ portal is failing, skip all requests (cool down)
  HALF_OPEN â†’ trial: allow 1 request to test recovery
Persistence: SQLite table portal_health in the main schemes.db
"""
from __future__ import annotations
import json
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional
logger = logging.getLogger("portal_health")
class CircuitState(str, Enum):
    CLOSED = "closed"       # Healthy â€” allow all requests
    OPEN = "open"           # Failing â€” skip requests
    HALF_OPEN = "half_open" # Testing â€” allow 1 probe request
@dataclass
class PortalHealthRecord:
    """Per-portal health tracking."""
    portal_name: str
    domain: str
    circuit_state: CircuitState = CircuitState.CLOSED
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    total_requests: int = 0
    total_successes: int = 0
    total_failures: int = 0
    total_timeouts: int = 0
    total_blocked: int = 0        # HTTP 403/429 responses
    last_success_at: Optional[str] = None
    last_failure_at: Optional[str] = None
    last_failure_reason: Optional[str] = None
    last_http_status: Optional[int] = None
    last_response_time_ms: Optional[float] = None
    avg_response_time_ms: float = 0.0
    opened_at: Optional[str] = None       # When circuit opened
    half_open_at: Optional[str] = None
    cooldown_until: Optional[str] = None  # Don't retry before this time
    schemes_extracted: int = 0
    selectors_working: bool = True
    needs_js: bool = False
    needs_ocr: bool = False
    last_selector_check: Optional[str] = None
    notes: str = ""
    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 1.0
        return self.total_successes / self.total_requests
    @property
    def is_healthy(self) -> bool:
        return self.circuit_state == CircuitState.CLOSED
# â”€â”€ Configuration â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
FAILURE_THRESHOLD = 5       # Consecutive failures before opening circuit
SUCCESS_THRESHOLD = 2       # Consecutive successes to close from half-open
COOLDOWN_MINUTES = 60       # Minutes to wait in OPEN state before trying half-open
MAX_COOLDOWN_MINUTES = 1440 # Max cooldown (24 hours) after repeated failures
BLOCKED_COOLDOWN_HOURS = 6  # Extra cooldown if we got 403/429
PORTAL_HEALTH_SCHEMA = """
CREATE TABLE IF NOT EXISTS portal_health (
    portal_name         TEXT PRIMARY KEY,
    domain              TEXT NOT NULL,
    circuit_state       TEXT DEFAULT 'closed',
    consecutive_failures INTEGER DEFAULT 0,
    consecutive_successes INTEGER DEFAULT 0,
    total_requests      INTEGER DEFAULT 0,
    total_successes     INTEGER DEFAULT 0,
    total_failures      INTEGER DEFAULT 0,
    total_timeouts      INTEGER DEFAULT 0,
    total_blocked       INTEGER DEFAULT 0,
    last_success_at     TEXT,
    last_failure_at     TEXT,
    last_failure_reason TEXT,
    last_http_status    INTEGER,
    last_response_time_ms REAL,
    avg_response_time_ms  REAL DEFAULT 0.0,
    opened_at           TEXT,
    half_open_at        TEXT,
    cooldown_until      TEXT,
    schemes_extracted   INTEGER DEFAULT 0,
    selectors_working   INTEGER DEFAULT 1,
    needs_js            INTEGER DEFAULT 0,
    needs_ocr           INTEGER DEFAULT 0,
    last_selector_check TEXT,
    notes               TEXT DEFAULT '',
    updated_at          TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS portal_request_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    portal_name     TEXT NOT NULL,
    url             TEXT NOT NULL,
    http_status     INTEGER,
    response_time_ms REAL,
    success         INTEGER NOT NULL,
    error_type      TEXT,
    error_message   TEXT,
    items_extracted INTEGER DEFAULT 0,
    requested_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_health_state ON portal_health(circuit_state);
CREATE INDEX IF NOT EXISTS idx_health_domain ON portal_health(domain);
CREATE INDEX IF NOT EXISTS idx_req_log_portal ON portal_request_log(portal_name);
CREATE INDEX IF NOT EXISTS idx_req_log_date ON portal_request_log(requested_at);
"""
class PortalHealthMonitor:
    """
    Tracks portal health, implements circuit breaker, and provides
    data for the health dashboard.
    """
    def __init__(self, db_path: str = "./data/schemes.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, PortalHealthRecord] = {}
        self._init_db()
    def _init_db(self) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.executescript(PORTAL_HEALTH_SCHEMA)
            conn.commit()
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    # â”€â”€â”€ Circuit Breaker Decision â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def should_crawl(self, portal_name: str) -> bool:
        """
        Core decision: should we attempt to crawl this portal right now?
        Returns False if circuit is OPEN and cooldown hasn't expired.
        """
        record = self._get_or_create(portal_name)
        if record.circuit_state == CircuitState.CLOSED:
            return True
        if record.circuit_state == CircuitState.OPEN:
            # Check if cooldown has expired
            if record.cooldown_until:
                try:
                    cooldown_end = datetime.fromisoformat(record.cooldown_until)
                    if datetime.utcnow() < cooldown_end:
                        logger.debug(
                            "Skipping %s â€” circuit OPEN, cooldown until %s",
                            portal_name, record.cooldown_until,
                        )
                        return False
                except (ValueError, TypeError):
                    pass
            # Cooldown expired â€” transition to HALF_OPEN
            self._transition(portal_name, CircuitState.HALF_OPEN)
            return True
        if record.circuit_state == CircuitState.HALF_OPEN:
            # Allow the probe request
            return True
        return True
    # â”€â”€â”€ Record Request Outcomes â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def record_success(
        self,
        portal_name: str,
        url: str,
        response_time_ms: float,
        items_extracted: int = 0,
        http_status: int = 200,
    ) -> None:
        """Record a successful crawl request."""
        now = datetime.utcnow().isoformat()
        record = self._get_or_create(portal_name)
        record.total_requests += 1
        record.total_successes += 1
        record.consecutive_successes += 1
        record.consecutive_failures = 0
        record.last_success_at = now
        record.last_http_status = http_status
        record.last_response_time_ms = response_time_ms
        record.schemes_extracted += items_extracted
        # Update running average response time
        if record.total_successes > 1:
            record.avg_response_time_ms = (
                (record.avg_response_time_ms * (record.total_successes - 1) + response_time_ms)
                / record.total_successes
            )
        else:
            record.avg_response_time_ms = response_time_ms
        # State transition: HALF_OPEN â†’ CLOSED after enough successes
        if record.circuit_state == CircuitState.HALF_OPEN:
            if record.consecutive_successes >= SUCCESS_THRESHOLD:
                self._transition(portal_name, CircuitState.CLOSED)
                logger.info("Portal %s recovered â€” circuit CLOSED", portal_name)
        elif record.circuit_state == CircuitState.OPEN:
            self._transition(portal_name, CircuitState.CLOSED)
        self._save(record)
        self._log_request(portal_name, url, http_status, response_time_ms, True, items_extracted=items_extracted)
    def record_failure(
        self,
        portal_name: str,
        url: str,
        error_type: str,
        error_message: str,
        http_status: Optional[int] = None,
        response_time_ms: float = 0.0,
        is_timeout: bool = False,
        is_blocked: bool = False,
    ) -> None:
        """Record a failed crawl request."""
        now = datetime.utcnow().isoformat()
        record = self._get_or_create(portal_name)
        record.total_requests += 1
        record.total_failures += 1
        record.consecutive_failures += 1
        record.consecutive_successes = 0
        record.last_failure_at = now
        record.last_failure_reason = f"{error_type}: {error_message[:200]}"
        record.last_http_status = http_status
        if is_timeout:
            record.total_timeouts += 1
        if is_blocked:
            record.total_blocked += 1
        # State transitions
        if record.circuit_state == CircuitState.HALF_OPEN:
            # Probe failed â€” back to OPEN with longer cooldown
            cooldown = min(
                COOLDOWN_MINUTES * (2 ** min(record.total_failures // FAILURE_THRESHOLD, 5)),
                MAX_COOLDOWN_MINUTES,
            )
            if is_blocked:
                cooldown = max(cooldown, BLOCKED_COOLDOWN_HOURS * 60)
            self._transition(portal_name, CircuitState.OPEN, cooldown_minutes=cooldown)
            logger.warning(
                "Portal %s probe failed â€” circuit OPEN, cooldown %d min",
                portal_name, cooldown,
            )
        elif record.circuit_state == CircuitState.CLOSED:
            if record.consecutive_failures >= FAILURE_THRESHOLD:
                cooldown = COOLDOWN_MINUTES
                if is_blocked:
                    cooldown = BLOCKED_COOLDOWN_HOURS * 60
                self._transition(portal_name, CircuitState.OPEN, cooldown_minutes=cooldown)
                logger.warning(
                    "Portal %s circuit OPENED after %d consecutive failures (cooldown %d min)",
                    portal_name, record.consecutive_failures, cooldown,
                )
        self._save(record)
        self._log_request(
            portal_name, url, http_status, response_time_ms, False,
            error_type=error_type, error_message=error_message[:500],
        )
    def record_selector_failure(self, portal_name: str, expected_items: int, actual_items: int) -> None:
        """Record when selectors extract far fewer items than expected (selector drift)."""
        record = self._get_or_create(portal_name)
        if actual_items == 0 and expected_items > 5:
            record.selectors_working = False
            record.notes = f"Selector drift detected: expected ~{expected_items}, got {actual_items}"
            logger.warning(
                "Selector drift on %s: expected ~%d items, got %d",
                portal_name, expected_items, actual_items,
            )
        record.last_selector_check = datetime.utcnow().isoformat()
        self._save(record)
    # â”€â”€â”€ State Transitions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _transition(
        self, portal_name: str, new_state: CircuitState, cooldown_minutes: int = 0,
    ) -> None:
        record = self._get_or_create(portal_name)
        old_state = record.circuit_state
        record.circuit_state = new_state
        now = datetime.utcnow()
        if new_state == CircuitState.OPEN:
            record.opened_at = now.isoformat()
            if cooldown_minutes > 0:
                record.cooldown_until = (now + timedelta(minutes=cooldown_minutes)).isoformat()
        elif new_state == CircuitState.HALF_OPEN:
            record.half_open_at = now.isoformat()
        elif new_state == CircuitState.CLOSED:
            record.opened_at = None
            record.half_open_at = None
            record.cooldown_until = None
        logger.info("Portal %s: %s â†’ %s", portal_name, old_state.value, new_state.value)
        self._save(record)
    # â”€â”€â”€ Persistence â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _get_or_create(self, portal_name: str, domain: str = "") -> PortalHealthRecord:
        if portal_name in self._cache:
            return self._cache[portal_name]
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM portal_health WHERE portal_name = ?", (portal_name,)
            ).fetchone()
        if row:
            record = PortalHealthRecord(
                portal_name=row["portal_name"],
                domain=row["domain"],
                circuit_state=CircuitState(row["circuit_state"]),
                consecutive_failures=row["consecutive_failures"],
                consecutive_successes=row["consecutive_successes"],
                total_requests=row["total_requests"],
                total_successes=row["total_successes"],
                total_failures=row["total_failures"],
                total_timeouts=row["total_timeouts"],
                total_blocked=row["total_blocked"],
                last_success_at=row["last_success_at"],
                last_failure_at=row["last_failure_at"],
                last_failure_reason=row["last_failure_reason"],
                last_http_status=row["last_http_status"],
                last_response_time_ms=row["last_response_time_ms"],
                avg_response_time_ms=row["avg_response_time_ms"] or 0.0,
                opened_at=row["opened_at"],
                half_open_at=row["half_open_at"],
                cooldown_until=row["cooldown_until"],
                schemes_extracted=row["schemes_extracted"],
                selectors_working=bool(row["selectors_working"]),
                needs_js=bool(row["needs_js"]),
                needs_ocr=bool(row["needs_ocr"]),
                last_selector_check=row["last_selector_check"],
                notes=row["notes"] or "",
            )
        else:
            record = PortalHealthRecord(portal_name=portal_name, domain=domain)
        self._cache[portal_name] = record
        return record
    def _save(self, record: PortalHealthRecord) -> None:
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO portal_health (
                    portal_name, domain, circuit_state,
                    consecutive_failures, consecutive_successes,
                    total_requests, total_successes, total_failures,
                    total_timeouts, total_blocked,
                    last_success_at, last_failure_at, last_failure_reason,
                    last_http_status, last_response_time_ms, avg_response_time_ms,
                    opened_at, half_open_at, cooldown_until,
                    schemes_extracted, selectors_working, needs_js, needs_ocr,
                    last_selector_check, notes, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                record.portal_name, record.domain, record.circuit_state.value,
                record.consecutive_failures, record.consecutive_successes,
                record.total_requests, record.total_successes, record.total_failures,
                record.total_timeouts, record.total_blocked,
                record.last_success_at, record.last_failure_at, record.last_failure_reason,
                record.last_http_status, record.last_response_time_ms, record.avg_response_time_ms,
                record.opened_at, record.half_open_at, record.cooldown_until,
                record.schemes_extracted, int(record.selectors_working),
                int(record.needs_js), int(record.needs_ocr),
                record.last_selector_check, record.notes, now,
            ))
            conn.commit()
        self._cache[record.portal_name] = record
    def _log_request(
        self, portal_name: str, url: str, http_status: Optional[int],
        response_time_ms: float, success: bool,
        error_type: str = "", error_message: str = "",
        items_extracted: int = 0,
    ) -> None:
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO portal_request_log (
                    portal_name, url, http_status, response_time_ms,
                    success, error_type, error_message, items_extracted, requested_at
                ) VALUES (?,?,?,?,?,?,?,?,?)
            """, (
                portal_name, url[:500], http_status, response_time_ms,
                int(success), error_type, error_message[:500],
                items_extracted, datetime.utcnow().isoformat(),
            ))
            conn.commit()
    # â”€â”€â”€ Reporting â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def get_health_summary(self) -> dict:
        """Get a summary of all portal health for the dashboard."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM portal_health ORDER BY total_failures DESC"
            ).fetchall()
        healthy = [r for r in rows if r["circuit_state"] == "closed"]
        failing = [r for r in rows if r["circuit_state"] in ("open", "half_open")]
        selector_issues = [r for r in rows if not r["selectors_working"]]
        return {
            "total_portals": len(rows),
            "healthy": len(healthy),
            "failing": len(failing),
            "selector_issues": len(selector_issues),
            "portals": [dict(r) for r in rows],
            "failing_portals": [
                {
                    "name": r["portal_name"],
                    "state": r["circuit_state"],
                    "failures": r["consecutive_failures"],
                    "reason": r["last_failure_reason"],
                    "cooldown_until": r["cooldown_until"],
                }
                for r in failing
            ],
        }
    def get_portal_stats(self, portal_name: str) -> Optional[dict]:
        record = self._get_or_create(portal_name)
        return {
            "portal_name": record.portal_name,
            "state": record.circuit_state.value,
            "success_rate": f"{record.success_rate:.1%}",
            "total_requests": record.total_requests,
            "avg_response_ms": f"{record.avg_response_time_ms:.0f}",
            "consecutive_failures": record.consecutive_failures,
            "last_success": record.last_success_at,
            "last_failure": record.last_failure_at,
            "selectors_ok": record.selectors_working,
        }
    def reset_portal(self, portal_name: str) -> None:
        """Manually reset a portal's circuit breaker (e.g., after fixing selectors)."""
        record = self._get_or_create(portal_name)
        record.circuit_state = CircuitState.CLOSED
        record.consecutive_failures = 0
        record.opened_at = None
        record.half_open_at = None
        record.cooldown_until = None
        record.selectors_working = True
        record.notes = f"Manually reset at {datetime.utcnow().isoformat()}"
        self._save(record)
        logger.info("Portal %s manually reset to CLOSED", portal_name)
    def cleanup_old_logs(self, days: int = 30) -> int:
        """Remove request logs older than N days."""
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        with self._connect() as conn:
            result = conn.execute(
                "DELETE FROM portal_request_log WHERE requested_at < ?", (cutoff,)
            )
            conn.commit()
            return result.rowcount
