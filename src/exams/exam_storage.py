"""
GovScheme SuperAgent â€” Exam Storage Agent (V3)
Builds organized folder hierarchy under output/examinations/ with 4 outputs per exam:
  1. metadata.json â€” structured JSON
  2. exam_details.md â€” human-readable Markdown
  3. website.url â€” Windows URL shortcut
  4. notification_*.pdf â€” downloaded notification PDFs
"""
from __future__ import annotations
import asyncio
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
import httpx
from src.config.settings import AgentConfig
from src.exams.exam_models import (
    ParsedExamData, StoredExamData, ExamLevel, ExamStatus,
)
logger = logging.getLogger("ExamStorage")
class ExamStorageAgent:
    """Organizes parsed exam data into a folder hierarchy."""
    def __init__(self, config: AgentConfig):
        self.config = config
        self.output_dir = config.exam_output_dir
        self.stored_count = 0
        self.errors: list[str] = []
    async def store_batch(
        self, parsed_exams: list[ParsedExamData], max_concurrent: int = 10,
    ) -> list[StoredExamData]:
        """Store a batch of parsed exams into the folder hierarchy."""
        semaphore = asyncio.Semaphore(max_concurrent)
        async def _store_safe(exam: ParsedExamData) -> Optional[StoredExamData]:
            async with semaphore:
                try:
                    return await self._store_single(exam)
                except Exception as e:
                    logger.warning("Store failed for %s: %s", exam.clean_exam_name, e)
                    self.errors.append(f"{exam.clean_exam_name}: {e}")
                    return None
        tasks = [_store_safe(p) for p in parsed_exams]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        stored = []
        for r in results:
            if isinstance(r, StoredExamData):
                stored.append(r)
                self.stored_count += 1
            elif isinstance(r, Exception):
                logger.error("Unexpected store error: %s", r)
        return stored
    async def _store_single(self, parsed: ParsedExamData) -> StoredExamData:
        """Store one exam: create folder, write files, download PDFs."""
        folder = self._compute_exam_folder(parsed)
        folder_path = Path(folder)
        folder_path.mkdir(parents=True, exist_ok=True)
        parsed.folder_path = str(folder_path)
        # Output 1: metadata.json
        meta_path = folder_path / "metadata.json"
        meta_content = self._build_metadata(parsed)
        meta_path.write_text(
            json.dumps(meta_content, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        # Output 2: exam_details.md
        md_path = folder_path / "exam_details.md"
        md_path.write_text(self._build_markdown(parsed), encoding="utf-8")
        # Output 3: website.url
        best_url = (
            parsed.apply_online_url
            or parsed.official_notification_url
            or parsed.official_website
            or parsed.raw.source_url
        )
        if best_url:
            url_path = folder_path / "website.url"
            url_path.write_text(
                f"[InternetShortcut]\nURL={best_url}\n", encoding="utf-8"
            )
        # Output 4: download notification PDFs (up to 5)
        downloaded_pdfs = []
        if self.config.download_pdfs:
            downloaded_pdfs = await self._download_pdfs(parsed, folder_path)
        return StoredExamData(
            parsed=parsed,
            folder_path=str(folder_path),
            metadata_path=str(meta_path),
            detail_markdown_path=str(md_path),
            downloaded_notification_pdfs=downloaded_pdfs,
        )
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Folder Path Computation
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _compute_exam_folder(self, parsed: ParsedExamData) -> str:
        """Build the hierarchical folder path for this exam."""
        parts = [self.output_dir]
        # Level: Central / State / UT
        parts.append(parsed.exam_level.value)
        # State (if state level)
        if parsed.state:
            parts.append(self._sanitize(parsed.state))
        # Category
        parts.append(parsed.exam_category.value)
        # Conducting body (for central exams, adds specificity)
        if parsed.exam_level == ExamLevel.Central:
            body = self._sanitize(parsed.raw.conducting_body)
            if body:
                parts.append(body)
        # Exam name + cycle
        exam_slug = self._sanitize(parsed.clean_exam_name)[:60]
        if parsed.exam_cycle:
            cycle_slug = self._sanitize(parsed.exam_cycle)
            exam_slug = f"{exam_slug}_{cycle_slug}"
        parts.append(exam_slug[:80])
        return str(Path(*parts))
    def _sanitize(self, name: str) -> str:
        """Sanitize a name for use as a folder path component."""
        sanitized = re.sub(r'[<>:"/\\|?*]', '', name)
        sanitized = re.sub(r'\s+', '_', sanitized.strip())
        sanitized = re.sub(r'_+', '_', sanitized).strip("_.")
        return sanitized[:80] or "unknown"
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Metadata JSON
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _build_metadata(self, parsed: ParsedExamData) -> dict:
        """Build the structured metadata.json content."""
        phases_list = []
        for p in parsed.phases:
            phases_list.append({
                "phase_name": p.phase_name,
                "exam_date_start": p.exam_date_start,
                "exam_date_end": p.exam_date_end,
                "admit_card_date": p.admit_card_date,
                "result_date": p.result_date,
                "mode": p.mode,
                "venue": p.venue,
            })
        vacancies_list = []
        for v in parsed.vacancies:
            vacancies_list.append({
                "post_name": v.post_name,
                "total_vacancies": v.total_vacancies,
                "general_vacancies": v.general_vacancies,
                "obc_vacancies": v.obc_vacancies,
                "sc_vacancies": v.sc_vacancies,
                "st_vacancies": v.st_vacancies,
                "ews_vacancies": v.ews_vacancies,
                "pwd_vacancies": v.pwd_vacancies,
                "pay_scale": v.pay_scale,
                "pay_band": v.pay_band,
                "grade_pay": v.grade_pay,
                "job_location": v.job_location,
            })
        return {
            "exam_id": parsed.exam_id,
            "exam_name": parsed.clean_exam_name,
            "short_name": parsed.short_name,
            "conducting_body": parsed.raw.conducting_body,
            "exam_category": parsed.exam_category.value,
            "exam_level": parsed.exam_level.value,
            "state": parsed.state,
            "exam_cycle": parsed.exam_cycle,
            "exam_status": parsed.exam_status.value,
            "dates": {
                "notification_date": parsed.notification_date,
                "application_start_date": parsed.application_start_date,
                "application_end_date": parsed.application_end_date,
                "fee_payment_deadline": parsed.fee_payment_deadline,
                "correction_window": {
                    "start": parsed.correction_window_start,
                    "end": parsed.correction_window_end,
                },
                "phases": phases_list,
                "result_date": parsed.result_date,
                "interview_date": parsed.interview_date,
                "final_result_date": parsed.final_result_date,
                "joining_date": parsed.joining_date,
            },
            "fees": {
                "general": parsed.fee.general,
                "obc": parsed.fee.obc,
                "sc_st": parsed.fee.sc_st,
                "female": parsed.fee.female,
                "ews": parsed.fee.ews,
                "pwd": parsed.fee.pwd,
                "ex_serviceman": parsed.fee.ex_serviceman,
                "is_free": parsed.fee.is_free,
                "fee_note": parsed.fee.fee_note,
                "fee_payment_url": parsed.fee.fee_payment_url,
            },
            "vacancies": {
                "total": parsed.total_vacancies,
                "posts": vacancies_list,
            },
            "eligibility": {
                "age_min": parsed.eligibility.age_min,
                "age_max": parsed.eligibility.age_max,
                "age_relaxation_obc": parsed.eligibility.age_relaxation_obc,
                "age_relaxation_sc_st": parsed.eligibility.age_relaxation_sc_st,
                "age_relaxation_pwd": parsed.eligibility.age_relaxation_pwd,
                "age_relaxation_ex_sm": parsed.eligibility.age_relaxation_ex_sm,
                "age_as_on_date": parsed.eligibility.age_as_on_date,
                "qualification": parsed.eligibility.qualification,
                "min_percentage": parsed.eligibility.min_percentage,
                "experience_years": parsed.eligibility.experience_years,
                "physical_standards": parsed.eligibility.physical_standards,
                "nationality": parsed.eligibility.nationality,
                "domicile_required": parsed.eligibility.domicile_required,
                "gender_restriction": parsed.eligibility.gender_restriction,
            },
            "links": {
                "official_notification": parsed.official_notification_url,
                "apply_online": parsed.apply_online_url,
                "admit_card": parsed.admit_card_url,
                "result": parsed.result_url,
                "syllabus": parsed.syllabus_url,
                "official_website": parsed.official_website,
            },
            "tracking": {
                "source_portal": parsed.raw.source_portal,
                "source_url": parsed.raw.source_url,
                "first_seen_date": parsed.first_seen_date,
                "last_seen_date": parsed.last_seen_date,
                "days_until_application_close": parsed.days_until_application_close,
                "days_until_exam": parsed.days_until_exam,
                "change_type": parsed.change_type.value,
                "parsing_confidence": parsed.parsing_confidence,
            },
            "crawled_at": parsed.raw.crawled_at.isoformat(),
            "stored_at": datetime.utcnow().isoformat(),
        }
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Markdown Details
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _build_markdown(self, parsed: ParsedExamData) -> str:
        """Build exam_details.md with all available data."""
        lines: list[str] = []
        # Title + status badge
        status_emoji = {
            ExamStatus.Upcoming: "ðŸ”µ",
            ExamStatus.Application_Open: "ðŸŸ¢",
            ExamStatus.Application_Closed: "ðŸŸ ",
            ExamStatus.Admit_Card_Out: "ðŸŸ¡",
            ExamStatus.Exam_Ongoing: "ðŸŸ£",
            ExamStatus.Result_Awaited: "â³",
            ExamStatus.Completed: "âœ…",
        }
        emoji = status_emoji.get(parsed.exam_status, "â“")
        lines.append(f"# {parsed.clean_exam_name} {emoji} {parsed.exam_status.value}")
        lines.append("")
        # Metadata table
        lines.append("| Field | Value |")
        lines.append("|-------|-------|")
        lines.append(f"| Conducting Body | {parsed.raw.conducting_body} |")
        lines.append(f"| Category | {parsed.exam_category.value.replace('_', ' ')} |")
        lines.append(f"| Level | {parsed.exam_level.value} |")
        if parsed.state:
            lines.append(f"| State | {parsed.state.replace('_', ' ')} |")
        if parsed.exam_cycle:
            lines.append(f"| Exam Cycle | {parsed.exam_cycle} |")
        if parsed.short_name:
            lines.append(f"| Short Name | {parsed.short_name} |")
        lines.append(f"| Status | {emoji} {parsed.exam_status.value.replace('_', ' ')} |")
        lines.append("")
        # Important Dates
        any_date = any([
            parsed.notification_date, parsed.application_start_date,
            parsed.application_end_date, parsed.fee_payment_deadline,
        ]) or parsed.phases
        if any_date:
            lines.append("## ðŸ“… Important Dates")
            lines.append("")
            lines.append("| Event | Date | Days Away |")
            lines.append("|-------|------|-----------|")
            if parsed.notification_date:
                lines.append(f"| Notification Date | {parsed.notification_date} | â€” |")
            if parsed.application_start_date:
                lines.append(f"| Application Opens | {parsed.application_start_date} | â€” |")
            if parsed.application_end_date:
                days_str = f"{parsed.days_until_application_close}" if parsed.days_until_application_close is not None else "â€”"
                lines.append(f"| âš ï¸ Application Closes | **{parsed.application_end_date}** | **{days_str}** |")
            if parsed.fee_payment_deadline:
                lines.append(f"| Fee Payment Deadline | {parsed.fee_payment_deadline} | â€” |")
            if parsed.correction_window_start:
                lines.append(f"| Correction Window | {parsed.correction_window_start} to {parsed.correction_window_end or 'â€”'} | â€” |")
            for phase in parsed.phases:
                if phase.admit_card_date:
                    lines.append(f"| ðŸŽ« Admit Card ({phase.phase_name}) | {phase.admit_card_date} | â€” |")
                if phase.exam_date_start:
                    end = f" to {phase.exam_date_end}" if phase.exam_date_end else ""
                    days_str = f"{parsed.days_until_exam}" if parsed.days_until_exam is not None else "â€”"
                    lines.append(f"| ðŸ“ Exam ({phase.phase_name}) | **{phase.exam_date_start}{end}** | **{days_str}** |")
                if phase.result_date:
                    lines.append(f"| ðŸ“Š Result ({phase.phase_name}) | {phase.result_date} | â€” |")
            if parsed.interview_date:
                lines.append(f"| ðŸŽ¤ Interview | {parsed.interview_date} | â€” |")
            if parsed.final_result_date:
                lines.append(f"| ðŸ† Final Result | {parsed.final_result_date} | â€” |")
            if parsed.joining_date:
                lines.append(f"| ðŸ¢ Joining | {parsed.joining_date} | â€” |")
            lines.append("")
        # Fees
        fee = parsed.fee
        has_fee = any([fee.general, fee.obc, fee.sc_st, fee.female, fee.ews, fee.pwd, fee.is_free])
        if has_fee:
            lines.append("## ðŸ’° Application Fee")
            lines.append("")
            if fee.is_free:
                lines.append("**No application fee for any category.**")
            else:
                lines.append("| Category | Fee (â‚¹) |")
                lines.append("|----------|---------|")
                if fee.general is not None:
                    lines.append(f"| General / UR | â‚¹{fee.general:,.0f} |")
                if fee.obc is not None:
                    lines.append(f"| OBC | â‚¹{fee.obc:,.0f} |")
                if fee.ews is not None:
                    lines.append(f"| EWS | â‚¹{fee.ews:,.0f} |")
                if fee.sc_st is not None:
                    val = "Exempted" if fee.sc_st == 0 else f"â‚¹{fee.sc_st:,.0f}"
                    lines.append(f"| SC / ST | {val} |")
                if fee.female is not None:
                    val = "Exempted" if fee.female == 0 else f"â‚¹{fee.female:,.0f}"
                    lines.append(f"| Female | {val} |")
                if fee.pwd is not None:
                    val = "Exempted" if fee.pwd == 0 else f"â‚¹{fee.pwd:,.0f}"
                    lines.append(f"| PwD | {val} |")
            if fee.fee_note:
                lines.append(f"\n> {fee.fee_note}")
            lines.append("")
        # Vacancies
        if parsed.vacancies:
            lines.append("## ðŸ“‹ Vacancies")
            lines.append("")
            if parsed.total_vacancies:
                lines.append(f"**Total Vacancies: {parsed.total_vacancies:,}**")
                lines.append("")
            lines.append("| Post | Vacancies | Pay Scale |")
            lines.append("|------|-----------|-----------|")
            for v in parsed.vacancies:
                vac = str(v.total_vacancies) if v.total_vacancies else "â€”"
                pay = v.pay_scale or v.pay_band or "â€”"
                lines.append(f"| {v.post_name} | {vac} | {pay} |")
            lines.append("")
        # Eligibility
        elig = parsed.eligibility
        has_elig = any([elig.age_min, elig.age_max, elig.qualification,
                        elig.physical_standards, elig.domicile_required])
        if has_elig:
            lines.append("## âœ… Eligibility")
            lines.append("")
            if elig.age_min or elig.age_max:
                age_range = f"{elig.age_min or 'â€”'} to {elig.age_max or 'â€”'} years"
                if elig.age_as_on_date:
                    age_range += f" (as on {elig.age_as_on_date})"
                lines.append(f"- **Age:** {age_range}")
                if elig.age_relaxation_obc:
                    lines.append(f"  - OBC: +{elig.age_relaxation_obc} years")
                if elig.age_relaxation_sc_st:
                    lines.append(f"  - SC/ST: +{elig.age_relaxation_sc_st} years")
                if elig.age_relaxation_pwd:
                    lines.append(f"  - PwD: +{elig.age_relaxation_pwd} years")
            if elig.qualification:
                lines.append(f"- **Qualification:** {elig.qualification}")
            if elig.min_percentage:
                lines.append(f"- **Minimum %:** {elig.min_percentage}%")
            if elig.experience_years:
                lines.append(f"- **Experience:** {elig.experience_years} years")
            if elig.physical_standards:
                lines.append(f"- **Physical Standards:** {elig.physical_standards}")
            if elig.domicile_required:
                lines.append(f"- **Domicile:** {elig.domicile_required}")
            if elig.gender_restriction:
                lines.append(f"- **Gender:** {elig.gender_restriction}")
            lines.append("")
        # Exam Pattern (phases)
        if parsed.phases:
            lines.append("## ðŸ“ Exam Pattern")
            lines.append("")
            for phase in parsed.phases:
                mode_str = f" ({phase.mode})" if phase.mode else ""
                lines.append(f"- **{phase.phase_name}**{mode_str}")
                if phase.venue:
                    lines.append(f"  - Venue: {phase.venue}")
            lines.append("")
        # Links
        links = [
            ("Apply Online", parsed.apply_online_url),
            ("Official Notification", parsed.official_notification_url),
            ("Admit Card", parsed.admit_card_url),
            ("Result", parsed.result_url),
            ("Syllabus", parsed.syllabus_url),
            ("Official Website", parsed.official_website),
        ]
        active_links = [(name, url) for name, url in links if url]
        if active_links:
            lines.append("## ðŸ”— Important Links")
            lines.append("")
            for name, url in active_links:
                lines.append(f"- [{name}]({url})")
            lines.append("")
        # Footer
        lines.append("---")
        lines.append(f"*Crawled: {parsed.raw.crawled_at.strftime('%Y-%m-%d %H:%M UTC')} | "
                      f"Source: {parsed.raw.source_portal} | "
                      f"Confidence: {parsed.parsing_confidence:.0%} | "
                      f"Folder: `{parsed.folder_path}`*")
        return "\n".join(lines)
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # PDF Download
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    async def _download_pdfs(
        self, parsed: ParsedExamData, folder: Path, max_pdfs: int = 5,
    ) -> list[str]:
        """Download notification PDFs into the exam folder."""
        downloaded = []
        urls = list(set(parsed.raw.pdf_urls))
        if parsed.official_notification_url and parsed.official_notification_url.endswith(".pdf"):
            urls.insert(0, parsed.official_notification_url)
        for i, url in enumerate(urls[:max_pdfs]):
            try:
                # Determine filename
                is_corrigendum = "corrigendum" in url.lower() or "amendment" in url.lower()
                prefix = "corrigendum" if is_corrigendum else "notification"
                filename = f"{prefix}_{i + 1}.pdf"
                dest = folder / filename
                if dest.exists():
                    downloaded.append(str(dest))
                    continue
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(url, follow_redirects=True)
                    content_length = len(resp.content)
                    max_bytes = self.config.max_pdf_size_mb * 1024 * 1024
                    if content_length > max_bytes:
                        logger.debug("PDF too large (%d bytes), skipping: %s", content_length, url)
                        continue
                    if resp.status_code == 200:
                        dest.write_bytes(resp.content)
                        downloaded.append(str(dest))
                        logger.debug("Downloaded %s â†’ %s", url, dest)
            except Exception as e:
                logger.debug("PDF download failed for %s: %s", url, e)
        return downloaded
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Report Files
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    async def generate_exam_reports(self, all_stored: list[StoredExamData]) -> None:
        """Generate aggregate report files in the output directory."""
        reports_dir = Path(self.output_dir) / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        # exam_index.json
        index = []
        for s in all_stored:
            p = s.parsed
            index.append({
                "exam_id": p.exam_id,
                "exam_name": p.clean_exam_name,
                "short_name": p.short_name,
                "conducting_body": p.raw.conducting_body,
                "category": p.exam_category.value,
                "level": p.exam_level.value,
                "state": p.state,
                "status": p.exam_status.value,
                "application_end_date": p.application_end_date,
                "total_vacancies": p.total_vacancies,
                "folder_path": s.folder_path,
            })
        (reports_dir / "exam_index.json").write_text(
            json.dumps(index, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        # exam_calendar.json â€” sorted by date
        calendar = []
        for s in all_stored:
            p = s.parsed
            if p.application_start_date:
                calendar.append({"date": p.application_start_date, "exam": p.clean_exam_name,
                                  "event": "Application Open", "body": p.raw.conducting_body})
            if p.application_end_date:
                calendar.append({"date": p.application_end_date, "exam": p.clean_exam_name,
                                  "event": "Application Close", "body": p.raw.conducting_body})
            for phase in p.phases:
                if phase.admit_card_date:
                    calendar.append({"date": phase.admit_card_date, "exam": p.clean_exam_name,
                                      "event": f"Admit Card ({phase.phase_name})", "body": p.raw.conducting_body})
                if phase.exam_date_start:
                    calendar.append({"date": phase.exam_date_start, "exam": p.clean_exam_name,
                                      "event": f"Exam ({phase.phase_name})", "body": p.raw.conducting_body})
                if phase.result_date:
                    calendar.append({"date": phase.result_date, "exam": p.clean_exam_name,
                                      "event": f"Result ({phase.phase_name})", "body": p.raw.conducting_body})
        calendar.sort(key=lambda x: x["date"] or "9999")
        (reports_dir / "exam_calendar.json").write_text(
            json.dumps(calendar, indent=2, ensure_ascii=False), encoding="utf-8",
        )
        # open_applications.json
        open_apps = [
            e for e in index if e["status"] == ExamStatus.Application_Open.value
        ]
        (reports_dir / "open_applications.json").write_text(
            json.dumps(open_apps, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        # exam_summary.json
        by_category: dict[str, int] = {}
        by_body: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for e in index:
            by_category[e["category"]] = by_category.get(e["category"], 0) + 1
            by_body[e["conducting_body"]] = by_body.get(e["conducting_body"], 0) + 1
            by_status[e["status"]] = by_status.get(e["status"], 0) + 1
        (reports_dir / "exam_summary.json").write_text(
            json.dumps({
                "total_exams": len(index),
                "by_category": dict(sorted(by_category.items(), key=lambda x: -x[1])),
                "by_body": dict(sorted(by_body.items(), key=lambda x: -x[1])),
                "by_status": dict(sorted(by_status.items(), key=lambda x: -x[1])),
            }, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info(
            "Exam reports generated: index (%d), calendar (%d events), open (%d)",
            len(index), len(calendar), len(open_apps),
        )
