"""
GovScheme SuperAgent â€” Exam Discovery Crawler
Crawls 150+ government career/recruitment portals to discover exam notifications.
Integrates with resilience layer: circuit breaker, adaptive rate limiting,
JS rendering, CAPTCHA detection, selector self-healing.
"""
from __future__ import annotations
import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential
from src.config.settings import AgentConfig
from src.exams.exam_models import RawExamData
from src.resilience.portal_health import PortalHealthMonitor
from src.resilience.crawler_resilience import (
    ResilientFetcher, AdaptiveRateLimiter, ProxyRotator,
    extract_with_healing, GENERIC_SELECTORS,
    get_random_headers, validate_page_content,
)
logger = logging.getLogger("exam_crawler")
# Date patterns for extracting dates near context keywords
DATE_PATTERNS = [
    re.compile(r'\b(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})\b'),
    re.compile(r'\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+(\d{4})\b', re.I),
    re.compile(r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b', re.I),
    re.compile(r'\b(\d{4})[/\-](\d{2})[/\-](\d{2})\b'),
]
DATE_CONTEXT_KEYWORDS = {
    "raw_application_start": ["application opens", "apply from", "online registration start", "registration begins", "start date"],
    "raw_application_end": ["last date", "closing date", "deadline", "apply before", "apply by", "last date to apply", "last date of application"],
    "raw_fee_payment_deadline": ["fee payment", "payment deadline", "fee last date"],
    "raw_admit_card_date": ["admit card", "hall ticket", "call letter", "e-admit"],
    "raw_exam_date": ["exam date", "examination date", "written test", "cbt date", "test date", "date of exam"],
    "raw_result_date": ["result", "merit list", "select list", "result date"],
    "raw_interview_date": ["interview", "document verification", "dv date", "personality test"],
}
# Minimum text length to consider an item as a valid exam notification
MIN_EXAM_NAME_LENGTH = 10
class ExamDiscoveryCrawler:
    """Discovers exam notifications across 150+ government portals."""
    def __init__(self, config: AgentConfig):
        self.config = config
        self.discovered: list[RawExamData] = []
        self.seen_hashes: set[str] = set()
        self.errors: list[dict] = []
        self._semaphore = asyncio.Semaphore(config.max_concurrent_crawlers)
        db_path = getattr(config, 'db_path', './data/schemes.db')
        self.health_monitor = PortalHealthMonitor(db_path)
        self.fetcher = ResilientFetcher(
            rate_limiter=AdaptiveRateLimiter(base_delay=1.0, max_delay=30.0),
            proxy_rotator=ProxyRotator(),
            timeout=30.0,
        )
    async def crawl_all_exam_sources(self, sources: list = None) -> list[RawExamData]:
        """Crawl all exam portal sources. Returns deduplicated RawExamData list."""
        if sources is None:
            try:
                from src.config.settings import EXAM_PORTAL_SOURCES
                sources = EXAM_PORTAL_SOURCES
            except ImportError:
                logger.warning("EXAM_PORTAL_SOURCES not found in settings")
                return []
        # Sort by priority
        sources = sorted(sources, key=lambda s: getattr(s, 'priority', 2))
        tasks = [self._crawl_source_safe(src) for src in sources]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.errors.append({
                    "source": getattr(sources[i], 'name', 'unknown'),
                    "error": str(result),
                })
                logger.error("Source %s failed: %s", getattr(sources[i], 'name', '?'), result)
        logger.info(
            "Exam discovery complete: %d raw exams from %d sources (%d errors)",
            len(self.discovered), len(sources), len(self.errors),
        )
        return self.discovered
    async def _crawl_source_safe(self, source) -> None:
        """Crawl a single source with circuit breaker and semaphore."""
        portal_name = getattr(source, 'name', str(source))
        # Circuit breaker check
        if not self.health_monitor.should_crawl(portal_name):
            logger.debug("Skipping %s (circuit open)", portal_name)
            return
        async with self._semaphore:
            try:
                strategy = getattr(source, 'crawl_strategy', 'html')
                if strategy == "rss":
                    await self._crawl_rss(source)
                elif strategy == "pdf":
                    await self._crawl_pdf_index(source)
                else:
                    await self._crawl_html(source)
            except Exception as e:
                self.health_monitor.record_failure(
                    portal_name, getattr(source, 'base_url', ''),
                    type(e).__name__, str(e)[:200],
                )
                raise
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10), reraise=True)
    async def _crawl_html(self, source) -> None:
        """Crawl HTML notification pages for a source."""
        portal_name = getattr(source, 'name', 'unknown')
        urls = getattr(source, 'notification_urls', [])
        if not urls:
            base = getattr(source, 'base_url', '')
            if base:
                urls = [base]
        for url in urls:
            import time as _t
            start = _t.time()
            html, meta = await self.fetcher.fetch(
                url, portal_name=portal_name,
                needs_js=getattr(source, 'needs_js', False),
            )
            elapsed_ms = (_t.time() - start) * 1000
            if not html:
                self.health_monitor.record_failure(
                    portal_name, url,
                    meta.get("error", "fetch_failed"),
                    json.dumps(meta)[:200],
                    http_status=meta.get("status"),
                    response_time_ms=elapsed_ms,
                    is_blocked=meta.get("status") == 403,
                )
                continue
            soup = BeautifulSoup(html, "html.parser")
            selectors = getattr(source, 'selectors', {})
            # Extract with self-healing selectors
            items, strategy_used = extract_with_healing(
                soup, portal_name, selectors,
                min_expected_items=1,
            )
            if not items:
                self.health_monitor.record_selector_failure(portal_name, 10, 0)
                # Fallback: extract dates from entire page text
                page_dates = self._extract_dates_from_text(soup.get_text())
                if page_dates:
                    logger.info("No items from selectors, but found %d dates on %s", len(page_dates), portal_name)
            exams_found = 0
            for item in items:
                exam = self._extract_exam_from_element(item, source, url)
                if exam and exam.content_hash not in self.seen_hashes:
                    self.seen_hashes.add(exam.content_hash)
                    self.discovered.append(exam)
                    exams_found += 1
            self.health_monitor.record_success(
                portal_name, url, elapsed_ms, items_extracted=exams_found,
            )
            # Rate limit between pages
            rate = getattr(source, 'rate_limit_per_sec', 1.0)
            if rate > 0:
                await asyncio.sleep(1.0 / rate)
    def _extract_exam_from_element(self, el, source, page_url: str) -> Optional[RawExamData]:
        """Extract a RawExamData from a single HTML element."""
        if isinstance(el, str):
            return None
        # Get exam name
        text = el.get_text(strip=True)
        if len(text) < MIN_EXAM_NAME_LENGTH:
            return None
        # Skip generic navigation links
        skip_patterns = re.compile(
            r'^(home|about|contact|faq|login|register|sitemap|archive|back|next|prev)',
            re.IGNORECASE,
        )
        if skip_patterns.match(text):
            return None
        # Get links
        links = el.find_all("a", href=True) if hasattr(el, 'find_all') else []
        if not links and el.name == "a" and el.get("href"):
            links = [el]
        notification_url = None
        apply_url = None
        pdf_urls = []
        for a in links:
            href = urljoin(page_url, a["href"])
            href_lower = href.lower()
            if href_lower.endswith(".pdf"):
                pdf_urls.append(href)
                if not notification_url:
                    notification_url = href
            elif any(kw in href_lower for kw in ["apply", "registration", "online"]):
                apply_url = href
            elif not notification_url:
                notification_url = href
        # Extract raw dates from surrounding text
        surrounding_text = text
        parent = el.parent
        if parent:
            surrounding_text = parent.get_text(strip=True)
        date_fields = self._extract_dates_from_text(surrounding_text)
        conducting_body = getattr(source, 'body_code', getattr(source, 'name', 'Unknown'))
        return RawExamData(
            source_portal=getattr(source, 'name', 'unknown'),
            source_url=page_url,
            exam_name=text[:300],
            conducting_body=conducting_body,
            notification_url=notification_url,
            apply_url=apply_url,
            pdf_urls=pdf_urls[:5],
            raw_application_start=date_fields.get("raw_application_start"),
            raw_application_end=date_fields.get("raw_application_end"),
            raw_exam_date=date_fields.get("raw_exam_date"),
            raw_admit_card_date=date_fields.get("raw_admit_card_date"),
            raw_result_date=date_fields.get("raw_result_date"),
            raw_fee=date_fields.get("raw_fee"),
        )
    def _extract_dates_from_text(self, text: str) -> dict[str, str]:
        """Extract dates near context keywords from text."""
        results = {}
        text_lower = text.lower()
        for field_name, keywords in DATE_CONTEXT_KEYWORDS.items():
            for keyword in keywords:
                pos = text_lower.find(keyword.lower())
                if pos < 0:
                    continue
                # Extract 200-char window after keyword
                window = text[pos:pos + 200]
                for pattern in DATE_PATTERNS:
                    match = pattern.search(window)
                    if match:
                        results[field_name] = match.group(0)
                        break
                if field_name in results:
                    break
        # Also look for fee patterns
        fee_match = re.search(r'(?:â‚¹|Rs\.?|INR)\s*([\d,]+)', text)
        if fee_match:
            results["raw_fee"] = fee_match.group(0)
        return results
    async def _crawl_rss(self, source) -> None:
        """Crawl RSS feed for exam notifications."""
        rss_url = getattr(source, 'rss_url', None)
        if not rss_url:
            return
        portal_name = getattr(source, 'name', 'unknown')
        try:
            import feedparser
        except ImportError:
            logger.warning("feedparser not installed, skipping RSS for %s", portal_name)
            return
        html, meta = await self.fetcher.fetch(rss_url, portal_name=portal_name)
        if not html:
            return
        feed = feedparser.parse(html)
        for entry in feed.entries[:50]:
            title = entry.get("title", "").strip()
            if len(title) < MIN_EXAM_NAME_LENGTH:
                continue
            link = entry.get("link", "")
            description = entry.get("description", "")
            pub_date = entry.get("published", entry.get("updated", ""))
            exam = RawExamData(
                source_portal=portal_name,
                source_url=rss_url,
                exam_name=title[:300],
                conducting_body=getattr(source, 'body_code', portal_name),
                notification_url=link,
                raw_notification_date=pub_date,
                raw_notification_text=description[:2000],
            )
            if exam.content_hash not in self.seen_hashes:
                self.seen_hashes.add(exam.content_hash)
                self.discovered.append(exam)
    async def _crawl_pdf_index(self, source) -> None:
        """Crawl pages that primarily list notification PDFs."""
        portal_name = getattr(source, 'name', 'unknown')
        urls = getattr(source, 'notification_urls', [getattr(source, 'base_url', '')])
        for url in urls:
            html, meta = await self.fetcher.fetch(url, portal_name=portal_name)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            # Find all PDF links
            pdf_links = soup.find_all("a", href=re.compile(r'\.pdf$', re.I))
            for a_tag in pdf_links:
                href = urljoin(url, a_tag["href"])
                text = a_tag.get_text(strip=True)
                if len(text) < MIN_EXAM_NAME_LENGTH:
                    # Try parent text
                    parent = a_tag.parent
                    if parent:
                        text = parent.get_text(strip=True)
                    if len(text) < MIN_EXAM_NAME_LENGTH:
                        continue
                exam = RawExamData(
                    source_portal=portal_name,
                    source_url=url,
                    exam_name=text[:300],
                    conducting_body=getattr(source, 'body_code', portal_name),
                    notification_url=href,
                    pdf_urls=[href],
                )
                if exam.content_hash not in self.seen_hashes:
                    self.seen_hashes.add(exam.content_hash)
                    self.discovered.append(exam)
    # â”€â”€â”€ Enrichment â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    async def enrich_exam_details(
        self, exams: list[RawExamData], max_concurrent: int = 3,
    ) -> list[RawExamData]:
        """Enrich exams by fetching notification PDFs and detail pages."""
        semaphore = asyncio.Semaphore(max_concurrent)
        async def _enrich_one(exam: RawExamData) -> RawExamData:
            async with semaphore:
                # Try fetching notification PDF text
                if exam.notification_url and exam.notification_url.lower().endswith(".pdf"):
                    try:
                        from src.resilience.crawler_resilience import extract_text_from_pdf
                        # Download PDF to temp file
                        async with httpx.AsyncClient(timeout=30, verify=False) as client:
                            resp = await client.get(exam.notification_url, headers=get_random_headers())
                            if resp.status_code == 200 and len(resp.content) < 10 * 1024 * 1024:
                                import tempfile
                                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                                    f.write(resp.content)
                                    pdf_path = f.name
                                text, method = extract_text_from_pdf(pdf_path)
                                if text:
                                    exam.raw_notification_text = text[:5000]
                                    # Re-extract dates from PDF text
                                    date_fields = self._extract_dates_from_text(text)
                                    for k, v in date_fields.items():
                                        if hasattr(exam, k) and not getattr(exam, k):
                                            setattr(exam, k, v)
                                import os
                                os.unlink(pdf_path)
                    except Exception as e:
                        logger.debug("PDF enrichment failed for %s: %s", exam.exam_name[:50], e)
                return exam
        enriched = await asyncio.gather(
            *[_enrich_one(e) for e in exams[:200]],
            return_exceptions=True,
        )
        results = []
        for i, result in enumerate(enriched):
            if isinstance(result, Exception):
                results.append(exams[i])
            else:
                results.append(result)
        return results
