"""
GovScheme SuperAgent â€” Daily Scheduler
Runs the crawl pipeline on a configurable schedule:
  - Daily at 6:00 AM IST (default)
  - Configurable via CRAWL_SCHEDULE_HOUR and CRAWL_SCHEDULE_MINUTE
  - Retry on failure with exponential backoff
  - Health check endpoint for monitoring
  - Lock file to prevent concurrent runs
  - Generates run_id per execution for traceability
Usage:
  # Run as daemon (long-running process with built-in scheduler)
  python -m src.scheduler.daily_runner --daemon
  # Run once immediately (for cron / systemd timer)
  python -m src.scheduler.daily_runner --once
  # Generate crontab entry
  python -m src.scheduler.daily_runner --install-cron
  # Generate systemd timer
  python -m src.scheduler.daily_runner --install-systemd
"""
from __future__ import annotations
import argparse
import asyncio
import fcntl
import hashlib
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from typing import Optional
from src.config.settings import AgentConfig
from src.agents.models import DailyRunReport
logger = logging.getLogger("scheduler")
# IST = UTC+5:30
IST = timezone(timedelta(hours=5, minutes=30))
LOCK_FILE = "/tmp/govscheme_crawl.lock"
def _generate_run_id() -> str:
    """Generate a unique run ID: date + short hash of timestamp."""
    today = date.today().isoformat()
    ts_hash = hashlib.md5(str(time.time()).encode()).hexdigest()[:6]
    return f"run_{today}_{ts_hash}"
class DailyScheduler:
    """
    Manages scheduled execution of the GovScheme crawl pipeline.
    Supports daemon mode (internal scheduler) and one-shot mode (external cron).
    """
    def __init__(
        self,
        schedule_hour: int = int(os.getenv("CRAWL_SCHEDULE_HOUR", "6")),
        schedule_minute: int = int(os.getenv("CRAWL_SCHEDULE_MINUTE", "0")),
        max_retries: int = 3,
        retry_delay_minutes: int = 30,
        config: Optional[AgentConfig] = None,
    ):
        self.schedule_hour = schedule_hour
        self.schedule_minute = schedule_minute
        self.max_retries = max_retries
        self.retry_delay_minutes = retry_delay_minutes
        self.config = config or AgentConfig()
        self._shutdown = False
        self._lock_fd = None
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Lock Management (prevent concurrent runs)
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _acquire_lock(self) -> bool:
        try:
            self._lock_fd = open(LOCK_FILE, "w")
            fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._lock_fd.write(f"{os.getpid()}\n{datetime.now(IST).isoformat()}\n")
            self._lock_fd.flush()
            return True
        except (IOError, OSError):
            logger.warning("Another crawl instance is already running (lock file: %s)", LOCK_FILE)
            return False
    def _release_lock(self) -> None:
        if self._lock_fd:
            try:
                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
                self._lock_fd.close()
                Path(LOCK_FILE).unlink(missing_ok=True)
            except Exception:
                pass
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # One-Shot Execution (cron mode)
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def run_once(self) -> Optional[DailyRunReport]:
        """Execute a single crawl run. Returns the daily report."""
        if not self._acquire_lock():
            logger.error("Cannot acquire lock â€” another instance is running")
            return None
        run_id = _generate_run_id()
        logger.info("Starting daily crawl run: %s", run_id)
        try:
            report = asyncio.run(self._execute_crawl(run_id))
            return report
        except Exception as e:
            logger.error("Daily crawl failed: %s", e, exc_info=True)
            return None
        finally:
            self._release_lock()
    def run_once_with_retry(self) -> Optional[DailyRunReport]:
        """Execute with retry logic for reliability."""
        for attempt in range(1, self.max_retries + 1):
            logger.info("Crawl attempt %d/%d", attempt, self.max_retries)
            report = self.run_once()
            if report is not None:
                return report
            if attempt < self.max_retries:
                wait = self.retry_delay_minutes * attempt
                logger.warning("Retrying in %d minutes...", wait)
                time.sleep(wait * 60)
        logger.error("All %d crawl attempts failed", self.max_retries)
        return None
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Daemon Mode (built-in scheduler)
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def run_daemon(self) -> None:
        """Run as a long-lived daemon that executes daily at the scheduled time."""
        logger.info(
            "GovScheme scheduler starting in daemon mode. "
            "Next crawl at %02d:%02d IST daily.",
            self.schedule_hour, self.schedule_minute,
        )
        # Handle graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        while not self._shutdown:
            now = datetime.now(IST)
            next_run = self._next_scheduled_time(now)
            wait_seconds = (next_run - now).total_seconds()
            logger.info(
                "Next scheduled run: %s IST (in %.1f hours)",
                next_run.strftime("%Y-%m-%d %H:%M"),
                wait_seconds / 3600,
            )
            # Sleep until next run, checking for shutdown every 60 seconds
            while wait_seconds > 0 and not self._shutdown:
                sleep_chunk = min(60, wait_seconds)
                time.sleep(sleep_chunk)
                wait_seconds -= sleep_chunk
            if self._shutdown:
                break
            # Execute the crawl
            logger.info("Scheduled crawl time reached. Starting...")
            self.run_once_with_retry()
        logger.info("Scheduler shutting down gracefully.")
    def _next_scheduled_time(self, now: datetime) -> datetime:
        """Compute the next scheduled run time."""
        today_run = now.replace(
            hour=self.schedule_hour,
            minute=self.schedule_minute,
            second=0,
            microsecond=0,
        )
        if now >= today_run:
            return today_run + timedelta(days=1)
        return today_run
    def _signal_handler(self, signum, frame):
        logger.info("Received signal %d, shutting down...", signum)
        self._shutdown = True
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Core Crawl Execution
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    async def _execute_crawl(self, run_id: str) -> DailyRunReport:
        """The actual crawl pipeline execution for a daily run."""
        # Import here to avoid circular imports
        from src.orchestrator import Orchestrator
        orchestrator = Orchestrator(self.config)
        report = await orchestrator.run_daily_pipeline(run_id)
        return report
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Installation Helpers
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    @staticmethod
    def generate_crontab_entry(
        hour: int = 6,
        minute: int = 0,
        python_path: str = "python3",
        project_dir: str = ".",
    ) -> str:
        """Generate a crontab line for scheduling."""
        abs_dir = Path(project_dir).resolve()
        log_file = abs_dir / "logs" / "daily_cron.log"
        return (
            f"# GovScheme SuperAgent â€” Daily crawl at {hour:02d}:{minute:02d} IST\n"
            f"{minute} {hour} * * * "
            f"cd {abs_dir} && "
            f"{python_path} -m src.scheduler.daily_runner --once "
            f">> {log_file} 2>&1\n"
        )
    @staticmethod
    def generate_systemd_units(
        hour: int = 6,
        minute: int = 0,
        python_path: str = "/usr/bin/python3",
        project_dir: str = ".",
        user: str = "",
    ) -> tuple[str, str]:
        """Generate systemd service + timer unit files."""
        abs_dir = Path(project_dir).resolve()
        user = user or os.getenv("USER", "root")
        service = f"""[Unit]
Description=GovScheme SuperAgent â€” Daily Government Scheme Crawler
After=network-online.target
Wants=network-online.target
[Service]
Type=oneshot
User={user}
WorkingDirectory={abs_dir}
ExecStart={python_path} -m src.scheduler.daily_runner --once
Environment="PATH={abs_dir}/venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONPATH={abs_dir}"
StandardOutput=append:{abs_dir}/logs/daily_systemd.log
StandardError=append:{abs_dir}/logs/daily_systemd_err.log
TimeoutStartSec=7200
[Install]
WantedBy=multi-user.target
"""
        timer = f"""[Unit]
Description=GovScheme SuperAgent â€” Daily Schedule Timer
[Timer]
OnCalendar=*-*-* {hour:02d}:{minute:02d}:00
Persistent=true
RandomizedDelaySec=300
[Install]
WantedBy=timers.target
"""
        return service, timer
class SchedulerHealthCheck:
    """Lightweight health check for monitoring the scheduler."""
    def __init__(self, db_path: str = "./data/schemes.db"):
        self.db_path = db_path
    def check(self) -> dict:
        status = {
            "healthy": True,
            "checked_at": datetime.now(IST).isoformat(),
            "db_exists": Path(self.db_path).exists(),
            "lock_active": Path(LOCK_FILE).exists(),
            "last_run": None,
            "total_schemes": 0,
        }
        if status["db_exists"]:
            try:
                from src.storage.database import SchemeDatabase
                db = SchemeDatabase(self.db_path)
                status["total_schemes"] = db.get_total_count()
                runs = db.get_run_history(1)
                if runs:
                    status["last_run"] = runs[0].get("run_date")
            except Exception as e:
                status["healthy"] = False
                status["error"] = str(e)
        return status
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# CLI Entry Point
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("logs/scheduler.log", mode="a"),
        ],
    )
    Path("logs").mkdir(exist_ok=True)
    parser = argparse.ArgumentParser(
        description="GovScheme SuperAgent â€” Daily Scheduler"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--daemon", action="store_true", help="Run as long-lived daemon")
    group.add_argument("--once", action="store_true", help="Run a single crawl immediately")
    group.add_argument("--health", action="store_true", help="Check scheduler health")
    group.add_argument("--install-cron", action="store_true", help="Print crontab entry")
    group.add_argument("--install-systemd", action="store_true", help="Print systemd units")
    parser.add_argument("--hour", type=int, default=6, help="Schedule hour (IST, 0-23)")
    parser.add_argument("--minute", type=int, default=0, help="Schedule minute (0-59)")
    parser.add_argument("--output", default="./output", help="Output directory")
    parser.add_argument("--no-pdfs", action="store_true", help="Skip PDF downloads")
    parser.add_argument("--retries", type=int, default=3, help="Max retry attempts")
    args = parser.parse_args()
    config = AgentConfig(
        output_dir=args.output,
        download_pdfs=not args.no_pdfs,
    )
    scheduler = DailyScheduler(
        schedule_hour=args.hour,
        schedule_minute=args.minute,
        max_retries=args.retries,
        config=config,
    )
    if args.daemon:
        scheduler.run_daemon()
    elif args.once:
        report = scheduler.run_once_with_retry()
        if report:
            print(json.dumps(report.model_dump(mode="json"), indent=2, default=str))
            sys.exit(0)
        else:
            sys.exit(1)
    elif args.health:
        health = SchedulerHealthCheck(config.db_path)
        result = health.check()
        print(json.dumps(result, indent=2))
        sys.exit(0 if result["healthy"] else 1)
    elif args.install_cron:
        entry = DailyScheduler.generate_crontab_entry(args.hour, args.minute)
        print(entry)
        print("# Add with: crontab -e")
    elif args.install_systemd:
        service, timer = DailyScheduler.generate_systemd_units(args.hour, args.minute)
        print("=== govscheme-crawl.service ===")
        print(service)
        print("=== govscheme-crawl.timer ===")
        print(timer)
        print("# Install with:")
        print("#   sudo cp govscheme-crawl.service /etc/systemd/system/")
        print("#   sudo cp govscheme-crawl.timer /etc/systemd/system/")
        print("#   sudo systemctl enable --now govscheme-crawl.timer")
if __name__ == "__main__":
    main()
