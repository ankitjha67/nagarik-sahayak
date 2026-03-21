"""
GovScheme SuperAgent â€” Orchestrator
The CEO agent that coordinates Discovery â†’ Dedup â†’ Classification â†’ Storage pipeline.
"""
from __future__ import annotations
import argparse
import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from src.config.settings import AgentConfig, PORTAL_SOURCES, EXAM_PORTAL_SOURCES
from src.crawlers.discovery_crawler import DiscoveryCrawler
from src.classifiers.classify_agent import ClassificationAgent
from src.storage.storage_agent import StorageAgent
from src.storage.database import SchemeDatabase
from src.storage.excel_report import ExcelReportGenerator
from src.agents.dedup_agent import DeduplicationAgent
from src.agents.change_agent import ChangeDetectionAgent
from src.agents.models import CrawlProgress, DailyRunReport
from src.notifications.email_sender import NotificationDispatcher, NotificationConfig
# V3: Exam pipeline imports
from src.exams.exam_crawler import ExamDiscoveryCrawler
from src.exams.exam_parser import ExamParser
from src.exams.exam_database import ExamDatabase
from src.exams.exam_storage import ExamStorageAgent
from src.exams.exam_alert import ExamAlertEngine
from src.exams.exam_models import ExamDailyReport, ExamChangeType
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("govscheme_crawl.log"),
    ],
)
logger = logging.getLogger("orchestrator")
console = Console()
class Orchestrator:
    """
    The CEO Agent â€” coordinates the full pipeline:
    1. Discovery: Crawl all government portals
    2. Dedup: Remove duplicate schemes
    3. Enrichment: Fetch detail pages for more data
    4. Classification: LLM-powered categorization
    5. Storage: Organize into folder hierarchy
    6. Reporting: Generate summary reports
    """
    def __init__(self, config: AgentConfig | None = None):
        self.config = config or AgentConfig()
        self.discovery = DiscoveryCrawler(self.config)
        self.classifier = ClassificationAgent(self.config)
        self.storage = StorageAgent(self.config)
        self.dedup = DeduplicationAgent(self.config)
        self.progress = CrawlProgress()
        self.db = SchemeDatabase(self.config.db_path)
        # V3: Exam pipeline agents
        self.exam_crawler = ExamDiscoveryCrawler(self.config)
        self.exam_parser = ExamParser(self.config)
        self.exam_db = ExamDatabase(self.config.exam_db_path)
        self.exam_storage = ExamStorageAgent(self.config)
        self.exam_alert = ExamAlertEngine(self.exam_db)
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # DAILY PIPELINE â€” The primary scheduled execution
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    async def run_daily_pipeline(
        self, run_id: str, skip_exams: bool = False, skip_schemes: bool = False,
    ) -> DailyRunReport:
        """
        Execute the full daily crawl pipeline (14 phases).
        Scheme Pipeline (Phases 1â€“8):
          1. Discovery â†’ 2. Dedup â†’ 3. Enrichment â†’ 4. Classification
          5. Change Detection â†’ 6. Storage â†’ 7. Excel â†’ 8. Notify
        Exam Pipeline (Phases 9â€“14):
          9. Exam Discovery â†’ 10. Exam Dedup â†’ 11. Exam Parsing
          12. Exam Change Detection â†’ 13. Exam Storage â†’ 14. Exam Alert+Notify
        """
        run_started = datetime.utcnow()
        self.progress.start_time = run_started
        self.progress.run_date = run_id
        self.progress.total_sources = len(PORTAL_SOURCES)
        errors = 0
        total_phases = 14
        mode_label = "schemes + exams"
        if skip_exams:
            mode_label = "schemes only"
        elif skip_schemes:
            mode_label = "exams only"
        console.print(Panel.fit(
            "[bold cyan]GovScheme + GovExam SuperAgent â€” Daily Pipeline[/bold cyan]\n"
            f"Run ID: {run_id} | Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"Mode: {mode_label}",
            border_style="cyan",
        ))
        if skip_schemes:
            # Jump straight to exam pipeline
            daily_report = self._empty_daily_report(run_id, run_started, 0)
            exam_report = await self._run_exam_pipeline(run_id) if self.config.run_exam_pipeline else None
            self._print_daily_summary(daily_report, exam_report)
            return daily_report
        console.print("\n[bold green]â•â•â• SCHEMES PIPELINE â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•[/bold green]")
        # â”€â”€ Phase 1: DISCOVERY â”€â”€
        console.print("\n[bold green]Phase 1/14: DISCOVERY[/bold green] â€” Crawling government portals...")
        start = time.time()
        try:
            raw_schemes = await self.discovery.crawl_all_sources()
        except Exception as e:
            logger.error("Discovery phase failed: %s", e, exc_info=True)
            raw_schemes = []
            errors += 1
        self.progress.total_schemes_discovered = len(raw_schemes)
        console.print(f"  âœ“ Discovered [bold]{len(raw_schemes)}[/bold] raw schemes in {time.time()-start:.1f}s")
        if not raw_schemes:
            console.print("[red]No schemes discovered. Generating empty report.[/red]")
            return self._empty_daily_report(run_id, run_started, errors + 1)
        # â”€â”€ Phase 2: DEDUPLICATION â”€â”€
        console.print("\n[bold green]Phase 2/14: DEDUPLICATION[/bold green] â€” Removing duplicates...")
        start = time.time()
        unique_schemes = self.dedup.deduplicate_batch(raw_schemes)
        self.progress.duplicates_found = len(raw_schemes) - len(unique_schemes)
        console.print(
            f"  âœ“ [bold]{len(unique_schemes)}[/bold] unique schemes "
            f"({self.progress.duplicates_found} duplicates removed) in {time.time()-start:.1f}s"
        )
        # â”€â”€ Phase 3: ENRICHMENT â”€â”€
        console.print("\n[bold green]Phase 3/14: ENRICHMENT[/bold green] â€” Fetching scheme details...")
        start = time.time()
        needs_enrichment = [s for s in unique_schemes if not s.raw_description]
        if needs_enrichment:
            console.print(f"  Enriching {len(needs_enrichment)} schemes missing details...")
            try:
                enriched = await self.discovery.enrich_batch(
                    needs_enrichment[:200], max_concurrent=3,
                )
                enriched_map = {s.source_url: s for s in enriched}
                for i, scheme in enumerate(unique_schemes):
                    if scheme.source_url in enriched_map:
                        unique_schemes[i] = enriched_map[scheme.source_url]
            except Exception as e:
                logger.warning("Enrichment partially failed: %s", e)
                errors += 1
        console.print(f"  âœ“ Enrichment complete in {time.time()-start:.1f}s")
        # â”€â”€ Phase 4: CLASSIFICATION â”€â”€
        console.print("\n[bold green]Phase 4/14: CLASSIFICATION[/bold green] â€” LLM categorization + date/fee extraction...")
        start = time.time()
        has_llm = bool(self.config.anthropic_api_key or self.config.openai_api_key)
        if has_llm:
            console.print("  Using LLM for classification (with date/fee extraction)...")
            try:
                classified = await self.classifier.classify_batch(
                    unique_schemes, max_concurrent=3, batch_size=10,
                )
            except Exception as e:
                logger.error("LLM classification failed, falling back: %s", e)
                classified = [self.classifier._fallback_classify(s) for s in unique_schemes]
                errors += 1
        else:
            console.print("  [yellow]No LLM API key â€” using rule-based classification[/yellow]")
            classified = [self.classifier._fallback_classify(s) for s in unique_schemes]
        self.progress.schemes_classified = len(classified)
        console.print(
            f"  âœ“ Classified [bold]{len(classified)}[/bold] schemes in {time.time()-start:.1f}s"
        )
        # â”€â”€ Phase 5: CHANGE DETECTION â”€â”€
        console.print("\n[bold green]Phase 5/14: CHANGE DETECTION[/bold green] â€” Comparing against database...")
        start = time.time()
        change_agent = ChangeDetectionAgent(self.db)
        annotated = change_agent.process_classified_batch(classified, run_id)
        self.progress.new_schemes_found = len(change_agent.new_schemes)
        self.progress.updated_schemes = len(change_agent.updated_schemes)
        self.progress.deadlines_approaching = len(change_agent.approaching_7d)
        console.print(
            f"  âœ“ [bold green]{len(change_agent.new_schemes)}[/bold green] new, "
            f"[bold yellow]{len(change_agent.updated_schemes)}[/bold yellow] updated, "
            f"[bold]{change_agent.unchanged_count}[/bold] unchanged, "
            f"[bold red]{len(change_agent.approaching_7d)}[/bold red] deadlines approaching "
            f"in {time.time()-start:.1f}s"
        )
        # â”€â”€ Phase 6: STORAGE â”€â”€
        console.print("\n[bold green]Phase 6/14: STORAGE[/bold green] â€” Organizing into folders...")
        start = time.time()
        try:
            stored = await self.storage.store_batch(annotated, max_concurrent=5)
        except Exception as e:
            logger.error("Storage phase failed: %s", e)
            stored = []
            errors += 1
        self.progress.schemes_stored = len(stored)
        console.print(f"  âœ“ Stored [bold]{len(stored)}[/bold] schemes in {time.time()-start:.1f}s")
        # Also generate folder-based reports
        try:
            await self.storage.generate_reports(stored)
        except Exception as e:
            logger.warning("Report generation partially failed: %s", e)
        # â”€â”€ Phase 7: EXCEL REPORT â”€â”€
        console.print("\n[bold green]Phase 7/14: EXCEL REPORT[/bold green] â€” Generating tracking workbook...")
        start = time.time()
        run_completed = datetime.utcnow()
        daily_report = change_agent.generate_daily_report(
            run_id, run_started, run_completed, errors,
        )
        try:
            excel_gen = ExcelReportGenerator(self.db, self.config.output_dir)
            excel_path = excel_gen.generate_full_report(daily_report)
            daily_report.excel_report_path = excel_path
            console.print(f"  âœ“ Excel report: [bold]{excel_path}[/bold] in {time.time()-start:.1f}s")
        except Exception as e:
            logger.error("Excel report generation failed: %s", e, exc_info=True)
            excel_path = None
            errors += 1
        # â”€â”€ Phase 8: SCHEME NOTIFY â”€â”€
        console.print("\n[bold green]Phase 8/14: SCHEME NOTIFY[/bold green] â€” Dispatching scheme reports...")
        try:
            notifier = NotificationDispatcher()
            results = notifier.dispatch(daily_report, excel_path)
            sent = [k for k, v in results.items() if v]
            if sent:
                console.print(f"  âœ“ Notifications sent via: [bold]{', '.join(sent)}[/bold]")
            else:
                console.print("  â„¹ No notification channels configured (set SMTP_USER/SLACK_WEBHOOK_URL)")
        except Exception as e:
            logger.warning("Notification dispatch failed: %s", e)
        # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
        # EXAMS PIPELINE (Phases 9â€“14) â€” V3
        # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
        exam_report = None
        if self.config.run_exam_pipeline and not skip_exams:
            console.print("\n[bold magenta]â•â•â• EXAMS PIPELINE â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•[/bold magenta]")
            exam_report = await self._run_exam_pipeline(run_id)
        # â”€â”€ Final Combined Summary â”€â”€
        self._print_daily_summary(daily_report, exam_report)
        # Update Excel with exam data if available
        if exam_report and excel_path:
            try:
                exam_excel_gen = ExcelReportGenerator(
                    self.db, self.config.output_dir, exam_db=self.exam_db,
                )
                excel_path = exam_excel_gen.generate_full_report(daily_report, exam_report=exam_report)
                daily_report.excel_report_path = excel_path
                console.print(f"\n[bold green]ðŸ“Š Final 15-sheet Excel:[/bold green] {excel_path}")
            except Exception as e:
                logger.warning("Failed to add exam sheets to Excel: %s", e)
        # Re-send notification with exam data included
        if exam_report:
            try:
                notifier = NotificationDispatcher()
                notifier.dispatch(daily_report, excel_path, exam_report=exam_report)
            except Exception as e:
                logger.warning("Exam notification dispatch failed: %s", e)
        return daily_report
    async def _run_exam_pipeline(self, run_id: str) -> ExamDailyReport | None:
        """Execute exam pipeline phases 9â€“14."""
        exam_started = datetime.utcnow()
        exam_errors = 0
        total_phases = 14
        # â”€â”€ Phase 9: EXAM DISCOVERY â”€â”€
        console.print(f"\n[bold magenta]Phase 9/{total_phases}: EXAM DISCOVERY[/bold magenta] â€” Crawling 150+ exam portals...")
        start = time.time()
        try:
            raw_exams = await self.exam_crawler.crawl_all_exam_sources(EXAM_PORTAL_SOURCES)
        except Exception as e:
            logger.error("Exam discovery failed: %s", e, exc_info=True)
            raw_exams = []
            exam_errors += 1
        console.print(f"  âœ“ Discovered [bold]{len(raw_exams)}[/bold] raw exam notifications in {time.time()-start:.1f}s")
        if not raw_exams:
            console.print("[yellow]No exam notifications discovered. Skipping exam phases.[/yellow]")
            return ExamDailyReport(
                run_id=run_id,
                run_date=datetime.utcnow().strftime("%Y-%m-%d"),
                errors=exam_errors + 1,
            )
        # â”€â”€ Phase 10: EXAM DEDUP â”€â”€
        console.print(f"\n[bold magenta]Phase 10/{total_phases}: EXAM DEDUP[/bold magenta] â€” Removing duplicates...")
        start = time.time()
        seen_hashes: set[str] = set()
        unique_exams = []
        for ex in raw_exams:
            h = ex.content_hash
            if h not in seen_hashes:
                seen_hashes.add(h)
                unique_exams.append(ex)
        dupes = len(raw_exams) - len(unique_exams)
        console.print(f"  âœ“ [bold]{len(unique_exams)}[/bold] unique exams ({dupes} duplicates removed) in {time.time()-start:.1f}s")
        # â”€â”€ Phase 11: EXAM PARSING â”€â”€
        console.print(f"\n[bold magenta]Phase 11/{total_phases}: EXAM PARSING[/bold magenta] â€” Extracting dates, fees, vacancies...")
        start = time.time()
        try:
            parsed_exams = await self.exam_parser.parse_batch(
                unique_exams, max_concurrent=self.config.exam_llm_max_concurrent,
            )
        except Exception as e:
            logger.error("Exam parsing failed: %s", e, exc_info=True)
            parsed_exams = []
            exam_errors += 1
        llm_count = sum(1 for p in parsed_exams if p.parsing_confidence >= 0.7)
        regex_count = len(parsed_exams) - llm_count
        console.print(
            f"  âœ“ Parsed [bold]{len(parsed_exams)}[/bold] exams "
            f"(LLM: {llm_count}, Regex: {regex_count}) in {time.time()-start:.1f}s"
        )
        # â”€â”€ Phase 12: EXAM CHANGE DETECTION â”€â”€
        console.print(f"\n[bold magenta]Phase 12/{total_phases}: EXAM CHANGE DETECT[/bold magenta] â€” Comparing against DB...")
        start = time.time()
        new_count, updated_count, unchanged_count = 0, 0, 0
        date_revised, vacancy_revised, fee_revised = 0, 0, 0
        new_exam_names: list[str] = []
        seen_exam_ids: set[str] = set()
        for parsed in parsed_exams:
            try:
                change_type = self.exam_db.upsert_exam(parsed, run_id)
                seen_exam_ids.add(parsed.exam_id)
                parsed.change_type = change_type
                if change_type == ExamChangeType.New_Notification:
                    new_count += 1
                    new_exam_names.append(parsed.clean_exam_name or parsed.raw.exam_name)
                elif change_type == ExamChangeType.Unchanged:
                    unchanged_count += 1
                elif change_type == ExamChangeType.Date_Revised:
                    date_revised += 1
                    updated_count += 1
                elif change_type == ExamChangeType.Vacancy_Revised:
                    vacancy_revised += 1
                    updated_count += 1
                elif change_type == ExamChangeType.Fee_Revised:
                    fee_revised += 1
                    updated_count += 1
                else:
                    updated_count += 1
            except Exception as e:
                logger.warning("Exam upsert failed for %s: %s", parsed.raw.exam_name, e)
                exam_errors += 1
        # Mark missing exams as closed (unseen for 3+ days)
        closed_count = self.exam_db.mark_missing_as_closed(run_id, seen_exam_ids)
        console.print(
            f"  âœ“ {new_count} new, {date_revised} date-revised, "
            f"{vacancy_revised} vacancy-revised, {fee_revised} fee-revised, "
            f"{unchanged_count} unchanged, {closed_count} closed in {time.time()-start:.1f}s"
        )
        # â”€â”€ Phase 13: EXAM STORAGE â”€â”€
        console.print(f"\n[bold magenta]Phase 13/{total_phases}: EXAM STORAGE[/bold magenta] â€” Building examinations/ folders...")
        start = time.time()
        stored_count = 0
        try:
            stored_exams = await self.exam_storage.store_batch(parsed_exams)
            stored_count = len(stored_exams)
        except Exception as e:
            logger.error("Exam storage batch failed: %s", e, exc_info=True)
            exam_errors += 1
        console.print(f"  âœ“ Stored [bold]{stored_count}[/bold] exams in {time.time()-start:.1f}s")
        # Generate exam report index files
        try:
            if stored_exams:
                await self.exam_storage.generate_exam_reports(stored_exams)
        except Exception as e:
            logger.warning("Exam report index generation failed: %s", e)
        # â”€â”€ Phase 14: EXAM ALERT + NOTIFY â”€â”€
        console.print(f"\n[bold magenta]Phase 14/{total_phases}: EXAM ALERT + NOTIFY[/bold magenta]")
        alerts = self.exam_alert.generate_alerts(datetime.utcnow().strftime("%Y-%m-%d"))
        exam_completed = datetime.utcnow()
        exam_elapsed = (exam_completed - exam_started).total_seconds()
        # Build ExamDailyReport
        exam_report = ExamDailyReport(
            run_id=run_id,
            run_date=datetime.utcnow().strftime("%Y-%m-%d"),
            run_started_at=exam_started,
            run_completed_at=exam_completed,
            total_exams_in_db=self.exam_db.get_total_count(),
            new_exams=new_count,
            updated_exams=updated_count,
            date_revised_exams=date_revised,
            vacancy_revised_exams=vacancy_revised,
            closed_exams=closed_count,
            application_open_exams=len(alerts.get("newly_opened", [])),
            deadlines_within_7_days=len(alerts.get("application_closing_7d", [])),
            deadlines_within_30_days=len(alerts.get("application_closing_30d", [])),
            exams_in_7_days=len(alerts.get("exams_in_7d", [])),
            exams_in_30_days=len(alerts.get("exams_in_30d", [])),
            errors=exam_errors,
            elapsed_seconds=exam_elapsed,
            new_exam_names=new_exam_names[:50],
            approaching_deadline_exams=[
                e.get("clean_exam_name", e.get("exam_name", "Unknown"))
                for e in alerts.get("application_closing_7d", [])[:20]
            ],
        )
        # Persist exam run to DB
        try:
            self.exam_db.save_exam_run(exam_report)
        except Exception as e:
            logger.warning("Failed to save exam run: %s", e)
        console.print(f"  âœ“ Exam alerts generated. Pipeline completed in {exam_elapsed:.1f}s")
        return exam_report
    def _empty_daily_report(
        self, run_id: str, started: datetime, errors: int,
    ) -> DailyRunReport:
        """Generate a report when no schemes were discovered."""
        from src.agents.models import DailyRunReport
        report = DailyRunReport(
            run_id=run_id,
            run_date=datetime.utcnow().strftime("%Y-%m-%d"),
            run_started_at=started,
            run_completed_at=datetime.utcnow(),
            errors=errors,
        )
        self.db.save_daily_run(report)
        # Still try to generate Excel from existing DB data
        try:
            excel_gen = ExcelReportGenerator(self.db, self.config.output_dir)
            report.excel_report_path = excel_gen.generate_full_report(report)
        except Exception:
            pass
        return report
    def _print_daily_summary(self, report: DailyRunReport, exam_report: ExamDailyReport | None = None) -> None:
        """Print the daily run summary with Rich tables."""
        table = Table(
            title=f"GovScheme + GovExam â€” Combined Daily Report â€” {report.run_date}",
            border_style="cyan",
        )
        table.add_column("Metric", style="bold")
        table.add_column("Value", justify="right")
        # Scheme metrics
        table.add_row("[bold cyan]â•â• SCHEMES â•â•[/bold cyan]", "")
        table.add_row("Total in Database", str(report.total_schemes_in_db))
        table.add_row("ðŸ†• New Schemes", f"[green]{report.new_schemes}[/green]")
        table.add_row("ðŸ”„ Updated", f"[yellow]{report.updated_schemes}[/yellow]")
        table.add_row("ðŸ“¦ Unchanged", str(report.unchanged_schemes))
        table.add_row("ðŸš« Closed", str(report.closed_schemes))
        table.add_row("âš ï¸  Deadlines (7 days)", f"[red]{report.deadlines_within_7_days}[/red]")
        table.add_row("âœ… Active Schemes", str(report.active_schemes))
        table.add_row("âŒ Errors", str(report.errors))
        # Exam metrics
        if exam_report:
            table.add_row("", "")
            table.add_row("[bold magenta]â•â• EXAMS â•â•[/bold magenta]", "")
            table.add_row("Total Exams in DB", str(exam_report.total_exams_in_db))
            table.add_row("ðŸ†• New Notifications", f"[green]{exam_report.new_exams}[/green]")
            table.add_row("ðŸ“… Date Revised", f"[yellow]{exam_report.date_revised_exams}[/yellow]")
            table.add_row("ðŸ“¦ Vacancy Revised", str(exam_report.vacancy_revised_exams))
            table.add_row("ðŸŸ¢ Applications Open", str(exam_report.application_open_exams))
            table.add_row("âš ï¸  App Closing 7d", f"[red]{exam_report.deadlines_within_7_days}[/red]")
            table.add_row("âš ï¸  App Closing 30d", f"[yellow]{exam_report.deadlines_within_30_days}[/yellow]")
            table.add_row("ðŸ“† Exams in 7 Days", str(exam_report.exams_in_7_days))
            table.add_row("ðŸ“† Exams in 30 Days", str(exam_report.exams_in_30_days))
            table.add_row("âŒ Exam Errors", str(exam_report.errors))
        if report.excel_report_path:
            table.add_row("", "")
            table.add_row("ðŸ“Š Excel Report", report.excel_report_path)
        console.print()
        console.print(table)
        if report.new_scheme_names:
            new_table = Table(title="ðŸ†• New Schemes Discovered", border_style="green")
            new_table.add_column("#", width=4)
            new_table.add_column("Scheme Name")
            for i, name in enumerate(report.new_scheme_names[:20], 1):
                new_table.add_row(str(i), name)
            console.print(new_table)
        if report.approaching_deadline_names:
            dl_table = Table(title="âš ï¸ Approaching Deadlines", border_style="red")
            dl_table.add_column("#", width=4)
            dl_table.add_column("Scheme Name")
            for i, name in enumerate(report.approaching_deadline_names[:15], 1):
                dl_table.add_row(str(i), name)
            console.print(dl_table)
    async def run_full_pipeline(self) -> None:
        """Execute the complete agent pipeline."""
        self.progress.start_time = datetime.utcnow()
        self.progress.total_sources = len(PORTAL_SOURCES)
        console.print(Panel.fit(
            "[bold cyan]GovScheme SuperAgent[/bold cyan]\n"
            "Crawling Indian Government Schemes across Central, State & UT portals",
            border_style="cyan",
        ))
        # â”€â”€ Phase 1: DISCOVERY â”€â”€
        console.print("\n[bold green]Phase 1: DISCOVERY[/bold green] â€” Crawling government portals...")
        start = time.time()
        raw_schemes = await self.discovery.crawl_all_sources()
        self.progress.total_schemes_discovered = len(raw_schemes)
        self.progress.last_update = datetime.utcnow()
        console.print(f"  âœ“ Discovered [bold]{len(raw_schemes)}[/bold] raw schemes in {time.time()-start:.1f}s")
        if not raw_schemes:
            console.print("[red]No schemes discovered. Check network connectivity and portal availability.[/red]")
            return
        # â”€â”€ Phase 2: DEDUPLICATION â”€â”€
        console.print("\n[bold green]Phase 2: DEDUPLICATION[/bold green] â€” Removing duplicates...")
        start = time.time()
        unique_schemes = self.dedup.deduplicate_batch(raw_schemes)
        self.progress.duplicates_found = len(raw_schemes) - len(unique_schemes)
        self.progress.last_update = datetime.utcnow()
        console.print(
            f"  âœ“ [bold]{len(unique_schemes)}[/bold] unique schemes "
            f"({self.progress.duplicates_found} duplicates removed) in {time.time()-start:.1f}s"
        )
        # â”€â”€ Phase 3: ENRICHMENT â”€â”€
        console.print("\n[bold green]Phase 3: ENRICHMENT[/bold green] â€” Fetching scheme details...")
        start = time.time()
        # Enrich top-priority schemes first (those missing descriptions)
        needs_enrichment = [s for s in unique_schemes if not s.raw_description]
        if needs_enrichment:
            console.print(f"  Enriching {len(needs_enrichment)} schemes with missing details...")
            enriched = await self.discovery.enrich_batch(
                needs_enrichment[:200],  # Limit to avoid excessive crawling
                max_concurrent=3,
            )
            # Merge enriched data back
            enriched_map = {s.source_url: s for s in enriched}
            for i, scheme in enumerate(unique_schemes):
                if scheme.source_url in enriched_map:
                    unique_schemes[i] = enriched_map[scheme.source_url]
        console.print(f"  âœ“ Enrichment complete in {time.time()-start:.1f}s")
        # â”€â”€ Phase 4: CLASSIFICATION â”€â”€
        console.print("\n[bold green]Phase 4: CLASSIFICATION[/bold green] â€” LLM-powered categorization...")
        start = time.time()
        # Check if we have an API key for LLM classification
        has_llm = bool(self.config.anthropic_api_key or self.config.openai_api_key)
        if has_llm:
            console.print("  Using LLM for intelligent classification...")
            classified = await self.classifier.classify_batch(
                unique_schemes,
                max_concurrent=3,
                batch_size=10,
            )
        else:
            console.print("  [yellow]No LLM API key found â€” using rule-based classification[/yellow]")
            classified = [
                self.classifier._fallback_classify(s)
                for s in unique_schemes
            ]
        self.progress.schemes_classified = len(classified)
        self.progress.last_update = datetime.utcnow()
        console.print(
            f"  âœ“ Classified [bold]{len(classified)}[/bold] schemes "
            f"(LLM: {self.classifier.classified_count}, "
            f"Fallback: {self.classifier.failed_count}) in {time.time()-start:.1f}s"
        )
        # â”€â”€ Phase 5: STORAGE â”€â”€
        console.print("\n[bold green]Phase 5: STORAGE[/bold green] â€” Organizing into folders...")
        start = time.time()
        stored = await self.storage.store_batch(classified, max_concurrent=5)
        self.progress.schemes_stored = len(stored)
        self.progress.last_update = datetime.utcnow()
        console.print(f"  âœ“ Stored [bold]{len(stored)}[/bold] schemes in {time.time()-start:.1f}s")
        # â”€â”€ Phase 6: REPORTING â”€â”€
        console.print("\n[bold green]Phase 6: REPORTING[/bold green] â€” Generating summary reports...")
        await self.storage.generate_reports(stored)
        self._print_final_summary(stored)
    async def run_discovery_only(self) -> None:
        """Run only the discovery phase."""
        console.print("[bold]Running discovery-only mode...[/bold]")
        raw = await self.discovery.crawl_all_sources()
        unique = self.dedup.deduplicate_batch(raw)
        # Save raw data
        output = Path(self.config.output_dir) / "raw_discoveries.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(
            [s.model_dump(mode="json") for s in unique],
            indent=2,
            ensure_ascii=False,
            default=str,
        ))
        console.print(f"Saved {len(unique)} unique schemes to {output}")
    def _print_final_summary(self, stored) -> None:
        """Print the final summary table."""
        table = Table(title="GovScheme SuperAgent â€” Final Report", border_style="cyan")
        table.add_column("Metric", style="bold")
        table.add_column("Value", justify="right")
        table.add_row("Total Discovered", str(self.progress.total_schemes_discovered))
        table.add_row("Duplicates Removed", str(self.progress.duplicates_found))
        table.add_row("Classified", str(self.progress.schemes_classified))
        table.add_row("Stored", str(self.progress.schemes_stored))
        table.add_row("Errors", str(len(self.discovery.errors)))
        table.add_row("Elapsed Time", f"{self.progress.elapsed_minutes:.1f} min")
        table.add_row("Output Directory", self.config.output_dir)
        console.print()
        console.print(table)
        # Sector breakdown
        if stored:
            sector_counts: dict[str, int] = {}
            level_counts: dict[str, int] = {}
            for s in stored:
                sec = s.classified.sector.value
                sector_counts[sec] = sector_counts.get(sec, 0) + 1
                lev = s.classified.level.value
                level_counts[lev] = level_counts.get(lev, 0) + 1
            sector_table = Table(title="By Sector", border_style="green")
            sector_table.add_column("Sector")
            sector_table.add_column("Count", justify="right")
            for sec, count in sorted(sector_counts.items(), key=lambda x: -x[1]):
                sector_table.add_row(sec.replace("_", " "), str(count))
            console.print(sector_table)
            level_table = Table(title="By Level", border_style="blue")
            level_table.add_column("Level")
            level_table.add_column("Count", justify="right")
            for lev, count in sorted(level_counts.items(), key=lambda x: -x[1]):
                level_table.add_row(lev, str(count))
            console.print(level_table)
def main():
    parser = argparse.ArgumentParser(description="GovScheme + GovExam SuperAgent â€” Government Scheme & Exam Crawler")
    parser.add_argument(
        "--mode",
        choices=["full", "daily", "discover", "classify", "store", "report-only", "exams-only", "schemes-only"],
        default="full",
        help="Pipeline mode: full (bootstrap), daily (scheduled delta), exams-only, schemes-only, report-only (Excel from DB)",
    )
    parser.add_argument("--output", default="./output", help="Output directory")
    parser.add_argument("--llm-provider", choices=["anthropic", "openai"], default="anthropic")
    parser.add_argument("--model", default="claude-sonnet-4-5-20250929", help="LLM model name")
    parser.add_argument("--max-crawlers", type=int, default=5, help="Max concurrent crawlers")
    parser.add_argument("--no-pdfs", action="store_true", help="Skip PDF downloads")
    parser.add_argument("--run-id", default=None, help="Custom run ID for daily mode")
    parser.add_argument("--db-path", default="./data/schemes.db", help="SQLite database path")
    parser.add_argument("--exam-db-path", default="./data/exams.db", help="SQLite exam database path")
    parser.add_argument("--skip-exams", action="store_true", help="Skip exam pipeline for this run")
    args = parser.parse_args()
    config = AgentConfig(
        output_dir=args.output,
        llm_provider=args.llm_provider,
        model_name=args.model,
        max_concurrent_crawlers=args.max_crawlers,
        download_pdfs=not args.no_pdfs,
        db_path=args.db_path,
        exam_db_path=args.exam_db_path,
    )
    orchestrator = Orchestrator(config)
    if args.mode == "full":
        asyncio.run(orchestrator.run_full_pipeline())
    elif args.mode in ("daily", "exams-only", "schemes-only"):
        import hashlib as _hl
        run_id = args.run_id or f"run_{datetime.utcnow().strftime('%Y-%m-%d')}_{_hl.md5(str(time.time()).encode()).hexdigest()[:6]}"
        skip_exams = args.skip_exams or args.mode == "schemes-only"
        skip_schemes = args.mode == "exams-only"
        report = asyncio.run(orchestrator.run_daily_pipeline(
            run_id, skip_exams=skip_exams, skip_schemes=skip_schemes,
        ))
        if report:
            console.print(f"\n[bold green]Pipeline complete.[/bold green] Excel: {report.excel_report_path}")
        else:
            console.print("[red]Pipeline failed.[/red]")
            sys.exit(1)
    elif args.mode == "discover":
        asyncio.run(orchestrator.run_discovery_only())
    elif args.mode == "report-only":
        # Generate Excel from existing DBs without crawling
        db = SchemeDatabase(config.db_path)
        exam_db = ExamDatabase(config.exam_db_path) if Path(config.exam_db_path).exists() else None
        excel_gen = ExcelReportGenerator(db, config.output_dir, exam_db=exam_db)
        path = excel_gen.generate_full_report()
        console.print(f"[bold green]Excel report generated:[/bold green] {path}")
    else:
        console.print(f"[yellow]Mode '{args.mode}' not yet implemented as standalone[/yellow]")
        asyncio.run(orchestrator.run_full_pipeline())
if __name__ == "__main__":
    main()
