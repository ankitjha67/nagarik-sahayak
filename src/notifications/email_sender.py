"""
GovScheme SuperAgent â€” Notification Dispatcher
Sends daily crawl reports via:
  1. Email (SMTP with Excel attachment)
  2. Slack webhook (summary + link)
  3. File drop to configurable directory
  4. Console summary (always)
"""
from __future__ import annotations
import json
import logging
import os
import shutil
import smtplib
import ssl
from datetime import date
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional
import httpx
from src.agents.models import DailyRunReport
logger = logging.getLogger("notifier")
class NotificationConfig:
    """Configuration for notification channels."""
    # Email SMTP
    smtp_host: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    email_from: str = os.getenv("EMAIL_FROM", "")
    email_to: list[str] = []  # populated from EMAIL_TO env var
    email_cc: list[str] = []
    # Slack
    slack_webhook_url: str = os.getenv("SLACK_WEBHOOK_URL", "")
    slack_channel: str = os.getenv("SLACK_CHANNEL", "#govscheme-alerts")
    # File Drop
    file_drop_dir: str = os.getenv("REPORT_DROP_DIR", "")
    def __init__(self):
        to_raw = os.getenv("EMAIL_TO", "")
        self.email_to = [e.strip() for e in to_raw.split(",") if e.strip()]
        cc_raw = os.getenv("EMAIL_CC", "")
        self.email_cc = [e.strip() for e in cc_raw.split(",") if e.strip()]
    @property
    def email_enabled(self) -> bool:
        return bool(self.smtp_user and self.smtp_password and self.email_to)
    @property
    def slack_enabled(self) -> bool:
        return bool(self.slack_webhook_url)
    @property
    def file_drop_enabled(self) -> bool:
        return bool(self.file_drop_dir)
class NotificationDispatcher:
    """Dispatches daily run reports to all configured channels."""
    def __init__(self, config: Optional[NotificationConfig] = None):
        self.config = config or NotificationConfig()
    def dispatch(
        self,
        report: DailyRunReport,
        excel_path: Optional[str] = None,
        exam_report=None,
    ) -> dict[str, bool]:
        """Send the daily report through all enabled channels. Returns success map."""
        results = {}
        # Always log to console
        self._log_console_summary(report)
        # Email
        if self.config.email_enabled and excel_path:
            results["email"] = self._send_email(report, excel_path, exam_report=exam_report)
        else:
            if not self.config.email_enabled:
                logger.info("Email notifications disabled (set SMTP_USER, SMTP_PASSWORD, EMAIL_TO)")
            results["email"] = False
        # Slack
        if self.config.slack_enabled:
            results["slack"] = self._send_slack(report, excel_path, exam_report=exam_report)
        else:
            logger.info("Slack notifications disabled (set SLACK_WEBHOOK_URL)")
            results["slack"] = False
        # File Drop
        if self.config.file_drop_enabled and excel_path:
            results["file_drop"] = self._file_drop(report, excel_path)
        else:
            results["file_drop"] = False
        return results
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Email via SMTP
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _send_email(self, report: DailyRunReport, excel_path: str, exam_report=None) -> bool:
        try:
            msg = MIMEMultipart("mixed")
            msg["From"] = self.config.email_from or self.config.smtp_user
            msg["To"] = ", ".join(self.config.email_to)
            if self.config.email_cc:
                msg["Cc"] = ", ".join(self.config.email_cc)
            msg["Subject"] = self._email_subject(report, exam_report)
            # HTML body
            body = self._build_email_body(report, exam_report)
            msg.attach(MIMEText(body, "html", "utf-8"))
            # Attach Excel
            if excel_path and Path(excel_path).exists():
                with open(excel_path, "rb") as f:
                    attachment = MIMEApplication(f.read(), _subtype="xlsx")
                    attachment.add_header(
                        "Content-Disposition", "attachment",
                        filename=Path(excel_path).name,
                    )
                    msg.attach(attachment)
            # Send
            all_recipients = self.config.email_to + self.config.email_cc
            context = ssl.create_default_context()
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(self.config.smtp_user, self.config.smtp_password)
                server.sendmail(
                    self.config.smtp_user,
                    all_recipients,
                    msg.as_string(),
                )
            logger.info("Email sent to %s", ", ".join(all_recipients))
            return True
        except Exception as e:
            logger.error("Email send failed: %s", e)
            return False
    def _email_subject(self, report: DailyRunReport, exam_report=None) -> str:
        parts = [f"GovScheme Daily Report â€” {report.run_date}"]
        if report.new_schemes > 0:
            parts.append(f"ðŸ†• {report.new_schemes} New")
        if report.deadlines_within_7_days > 0:
            parts.append(f"âš ï¸ {report.deadlines_within_7_days} Deadlines")
        if exam_report and exam_report.application_open_exams > 0:
            parts.append(f"ðŸ“ {exam_report.application_open_exams} Exams Open")
        return " | ".join(parts)
    def _build_email_body(self, report: DailyRunReport, exam_report=None) -> str:
        new_list = ""
        if report.new_scheme_names:
            items = "".join(
                f"<li>{name}</li>" for name in report.new_scheme_names[:20]
            )
            remaining = max(0, report.new_schemes - 20)
            more = f"<li><em>...and {remaining} more</em></li>" if remaining else ""
            new_list = f"""
            <h3 style="color:#2E7D32;">ðŸ†• New Schemes Discovered ({report.new_schemes})</h3>
            <ul>{items}{more}</ul>
            """
        deadline_list = ""
        if report.approaching_deadline_names:
            items = "".join(
                f"<li>{name}</li>" for name in report.approaching_deadline_names[:15]
            )
            deadline_list = f"""
            <h3 style="color:#C62828;">âš ï¸ Approaching Deadlines ({report.deadlines_within_7_days})</h3>
            <ul>{items}</ul>
            """
        updated_list = ""
        if report.updated_scheme_names:
            items = "".join(
                f"<li>{name}</li>" for name in report.updated_scheme_names[:10]
            )
            updated_list = f"""
            <h3 style="color:#F57C00;">ðŸ”„ Updated Schemes ({report.updated_schemes})</h3>
            <ul>{items}</ul>
            """
        return f"""
        <html>
        <body style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto;">
            <div style="background:linear-gradient(135deg,#1F4E79,#2E86C1);
                        padding:20px;border-radius:8px 8px 0 0;">
                <h1 style="color:#fff;margin:0;">ðŸ“Š GovScheme Daily Report</h1>
                <p style="color:#D6E4F0;margin:5px 0 0;">
                    {report.run_date} &middot; Completed in {report.elapsed_seconds:.0f}s
                </p>
            </div>
            <div style="padding:20px;border:1px solid #ddd;border-top:none;">
                <table style="width:100%;border-collapse:collapse;margin-bottom:20px;">
                    <tr style="background:#f5f5f5;">
                        <td style="padding:10px;border:1px solid #ddd;">
                            <strong>Total in DB</strong><br>
                            <span style="font-size:24px;color:#1F4E79;">{report.total_schemes_in_db}</span>
                        </td>
                        <td style="padding:10px;border:1px solid #ddd;">
                            <strong>New Today</strong><br>
                            <span style="font-size:24px;color:#2E7D32;">{report.new_schemes}</span>
                        </td>
                        <td style="padding:10px;border:1px solid #ddd;">
                            <strong>Updated</strong><br>
                            <span style="font-size:24px;color:#F57C00;">{report.updated_schemes}</span>
                        </td>
                        <td style="padding:10px;border:1px solid #ddd;">
                            <strong>Active</strong><br>
                            <span style="font-size:24px;color:#1565C0;">{report.active_schemes}</span>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:10px;border:1px solid #ddd;">
                            <strong>Deadlines (7d)</strong><br>
                            <span style="font-size:24px;color:#C62828;">{report.deadlines_within_7_days}</span>
                        </td>
                        <td style="padding:10px;border:1px solid #ddd;">
                            <strong>Deadlines (30d)</strong><br>
                            <span style="font-size:24px;color:#EF6C00;">{report.deadlines_within_30_days}</span>
                        </td>
                        <td style="padding:10px;border:1px solid #ddd;">
                            <strong>Closed</strong><br>
                            <span style="font-size:24px;color:#757575;">{report.closed_schemes}</span>
                        </td>
                        <td style="padding:10px;border:1px solid #ddd;">
                            <strong>Errors</strong><br>
                            <span style="font-size:24px;color:#B71C1C;">{report.errors}</span>
                        </td>
                    </tr>
                </table>
                {new_list}
                {deadline_list}
                {updated_list}
                {self._build_exam_email_section(exam_report) if exam_report else ''}
                <p style="color:#999;font-size:12px;margin-top:30px;border-top:1px solid #ddd;padding-top:10px;">
                    GovScheme SuperAgent â€” Automated daily crawl report.<br>
                    Full Excel report attached. Open the "Approaching Deadlines" sheet for urgent action items.
                </p>
            </div>
        </body>
        </html>
        """
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Slack Webhook
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _send_slack(self, report: DailyRunReport, excel_path: Optional[str], exam_report=None) -> bool:
        try:
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"ðŸ“Š GovScheme Daily Report â€” {report.run_date}",
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Total in DB:*\n{report.total_schemes_in_db}"},
                        {"type": "mrkdwn", "text": f"*New Today:*\n{report.new_schemes}"},
                        {"type": "mrkdwn", "text": f"*Updated:*\n{report.updated_schemes}"},
                        {"type": "mrkdwn", "text": f"*Deadlines (7d):*\n{report.deadlines_within_7_days}"},
                    ],
                },
            ]
            if report.new_scheme_names:
                names = "\n".join(f"â€¢ {n}" for n in report.new_scheme_names[:10])
                blocks.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*ðŸ†• New Schemes:*\n{names}"},
                })
            if report.approaching_deadline_names:
                names = "\n".join(f"â€¢ {n}" for n in report.approaching_deadline_names[:10])
                blocks.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*âš ï¸ Approaching Deadlines:*\n{names}"},
                })
            # V3: Exam alerts section
            if exam_report:
                blocks.append({"type": "divider"})
                blocks.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "*ðŸ“ Government Exam Alerts*"},
                })
                blocks.append({
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Closing in 7d:* {exam_report.deadlines_within_7_days}"},
                        {"type": "mrkdwn", "text": f"*Open Now:* {exam_report.application_open_exams}"},
                        {"type": "mrkdwn", "text": f"*Exams in 7d:* {exam_report.exams_in_7_days}"},
                        {"type": "mrkdwn", "text": f"*New Notified:* {exam_report.new_exams}"},
                    ],
                })
                if exam_report.new_exam_names:
                    names = "\n".join(f"â€¢ {n}" for n in exam_report.new_exam_names[:8])
                    blocks.append({
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"*ðŸ†• New Exam Notifications:*\n{names}"},
                    })
                if exam_report.approaching_deadline_exams:
                    names = "\n".join(f"â€¢ {n}" for n in exam_report.approaching_deadline_exams[:8])
                    blocks.append({
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"*âš ï¸ Exam App Closing Soon:*\n{names}"},
                    })
            payload = {
                "channel": self.config.slack_channel,
                "blocks": blocks,
            }
            resp = httpx.post(
                self.config.slack_webhook_url,
                json=payload,
                timeout=15,
            )
            if resp.status_code == 200:
                logger.info("Slack notification sent to %s", self.config.slack_channel)
                return True
            else:
                logger.error("Slack webhook returned %d: %s", resp.status_code, resp.text)
                return False
        except Exception as e:
            logger.error("Slack notification failed: %s", e)
            return False
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # File Drop
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _file_drop(self, report: DailyRunReport, excel_path: str) -> bool:
        try:
            drop_dir = Path(self.config.file_drop_dir)
            drop_dir.mkdir(parents=True, exist_ok=True)
            # Copy Excel
            dest = drop_dir / Path(excel_path).name
            shutil.copy2(excel_path, dest)
            # Also write a JSON summary
            summary_path = drop_dir / f"daily_summary_{report.run_date}.json"
            summary_path.write_text(
                json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
            logger.info("Report dropped to %s", drop_dir)
            return True
        except Exception as e:
            logger.error("File drop failed: %s", e)
            return False
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Console Summary (always runs)
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _log_console_summary(self, report: DailyRunReport) -> None:
        logger.info("=" * 60)
        logger.info("DAILY RUN REPORT â€” %s", report.run_date)
        logger.info("=" * 60)
        logger.info("Total in DB:        %d", report.total_schemes_in_db)
        logger.info("New schemes:        %d", report.new_schemes)
        logger.info("Updated schemes:    %d", report.updated_schemes)
        logger.info("Closed schemes:     %d", report.closed_schemes)
        logger.info("Unchanged:          %d", report.unchanged_schemes)
        logger.info("Deadlines (7 days): %d", report.deadlines_within_7_days)
        logger.info("Deadlines (30 days):%d", report.deadlines_within_30_days)
        logger.info("Active schemes:     %d", report.active_schemes)
        logger.info("Errors:             %d", report.errors)
        logger.info("Duration:           %.1f seconds", report.elapsed_seconds)
        if report.excel_report_path:
            logger.info("Excel report:       %s", report.excel_report_path)
        logger.info("=" * 60)
        if report.new_scheme_names:
            logger.info("NEW SCHEMES:")
            for name in report.new_scheme_names[:25]:
                logger.info("  ðŸ†• %s", name)
        if report.approaching_deadline_names:
            logger.info("APPROACHING DEADLINES:")
            for name in report.approaching_deadline_names[:15]:
                logger.info("  âš ï¸  %s", name)
    def _build_exam_email_section(self, exam_report) -> str:
        """Build the HTML section for exam alerts in the email body."""
        if not exam_report:
            return ""
        # KPI row
        section = f"""
        <div style="margin-top:20px;border-top:2px solid #1F4E79;padding-top:15px;">
            <h2 style="color:#1F4E79;">ðŸ“ Government Exam Alerts</h2>
            <table style="width:100%;border-collapse:collapse;margin-bottom:15px;">
                <tr style="background:#f5f5f5;">
                    <td style="padding:8px;border:1px solid #ddd;text-align:center;">
                        <strong>Total Exams</strong><br>
                        <span style="font-size:20px;color:#1F4E79;">{exam_report.total_exams_in_db}</span>
                    </td>
                    <td style="padding:8px;border:1px solid #ddd;text-align:center;">
                        <strong>New Notified</strong><br>
                        <span style="font-size:20px;color:#2E7D32;">{exam_report.new_exams}</span>
                    </td>
                    <td style="padding:8px;border:1px solid #ddd;text-align:center;">
                        <strong>Apps Open</strong><br>
                        <span style="font-size:20px;color:#1565C0;">{exam_report.application_open_exams}</span>
                    </td>
                    <td style="padding:8px;border:1px solid #ddd;text-align:center;">
                        <strong>Closing in 7d</strong><br>
                        <span style="font-size:20px;color:#C62828;">{exam_report.deadlines_within_7_days}</span>
                    </td>
                </tr>
            </table>
        """
        # Applications closing soon
        if exam_report.approaching_deadline_exams:
            items = "".join(
                f"<li>{name}</li>" for name in exam_report.approaching_deadline_exams[:15]
            )
            section += f"""
            <h3 style="color:#C62828;">âš ï¸ Exam Applications Closing in 7 Days</h3>
            <ul>{items}</ul>
            """
        # New exam notifications
        if exam_report.new_exam_names:
            items = "".join(
                f"<li>{name}</li>" for name in exam_report.new_exam_names[:20]
            )
            section += f"""
            <h3 style="color:#2E7D32;">ðŸ†• New Exam Notifications ({exam_report.new_exams})</h3>
            <ul>{items}</ul>
            """
        section += "</div>"
        return section
