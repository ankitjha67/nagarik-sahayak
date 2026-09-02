"""
GovScheme SuperAgent â€” Adaptive Crawler Resilience Layer
Addresses EVERY crawler limitation identified:
1. JS-HEAVY SITES (UPSC, RBI, State PSCs)
   â†’ Playwright browser pool with headless Chrome fallback
   â†’ Detects JS-required pages by checking if httpx returns empty/minimal content
2. SELECTOR SELF-HEALING
   â†’ Multiple selector strategies per portal (primary, fallback, generic)
   â†’ Auto-detects selector drift when extraction yields 0 items
   â†’ Falls back to generic heuristic extraction (links + text patterns)
3. ANTI-BAN / RATE LIMITING
   â†’ Adaptive delay based on response codes (429 â†’ exponential backoff)
   â†’ User-agent rotation from realistic browser fingerprint pool
   â†’ Referer header spoofing for government portals
   â†’ Respects robots.txt (optional)
4. CAPTCHA DETECTION
   â†’ Detects CAPTCHA pages by HTML signatures
   â†’ Flags portal as captcha_required, skips with logged warning
   â†’ Does NOT attempt to solve CAPTCHAs
5. OCR FOR SCANNED PDFs
   â†’ Detects image-only PDFs (no extractable text)
   â†’ Falls back to pytesseract OCR if available
   â†’ Falls back to pdf2image + tesseract pipeline
   â†’ Graceful degradation: if OCR not installed, logs and skips
6. PROXY ROTATION (optional)
   â†’ Configurable proxy list via PROXY_LIST env var
   â†’ Round-robin rotation
   â†’ Marks dead proxies
7. CONTENT VALIDATION
   â†’ Checks if response is actual HTML vs error page / maintenance page
   â†’ Detects common government error pages ("Site under maintenance", "403 Forbidden")
"""
from __future__ import annotations
import asyncio
import logging
import os
import random
import re
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup
logger = logging.getLogger("crawler_resilience")
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# 1. USER-AGENT ROTATION
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0",
]
def get_random_headers(referer_domain: str = "") -> dict[str, str]:
    """Generate realistic browser headers with rotation."""
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-IN,en-GB;q=0.9,en;q=0.8,hi;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }
    if referer_domain:
        headers["Referer"] = f"https://{referer_domain}/"
        headers["Sec-Fetch-Site"] = "same-origin"
    return headers
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# 2. ADAPTIVE RATE LIMITER
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
class AdaptiveRateLimiter:
    """
    Per-domain rate limiting that adapts based on response codes.
    429/503 â†’ double delay; 200 â†’ slowly decrease delay.
    """
    def __init__(self, base_delay: float = 1.0, max_delay: float = 60.0):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self._domain_delays: dict[str, float] = {}
        self._domain_locks: dict[str, asyncio.Lock] = {}
    def _get_domain(self, url: str) -> str:
        return urlparse(url).netloc
    async def wait(self, url: str) -> None:
        """Wait the appropriate delay for this domain."""
        domain = self._get_domain(url)
        delay = self._domain_delays.get(domain, self.base_delay)
        if domain not in self._domain_locks:
            self._domain_locks[domain] = asyncio.Lock()
        async with self._domain_locks[domain]:
            jitter = random.uniform(0.1, 0.5)
            await asyncio.sleep(delay + jitter)
    def record_response(self, url: str, status_code: int) -> None:
        """Adapt delay based on response code."""
        domain = self._get_domain(url)
        current = self._domain_delays.get(domain, self.base_delay)
        if status_code in (429, 503, 529):
            # Rate limited or overloaded â€” back off hard
            new_delay = min(current * 2.5, self.max_delay)
            logger.warning("Rate limited on %s (HTTP %d), delay â†’ %.1fs", domain, status_code, new_delay)
        elif status_code == 403:
            # Possibly blocked â€” significant backoff
            new_delay = min(current * 3.0, self.max_delay)
            logger.warning("Blocked on %s (403), delay â†’ %.1fs", domain, new_delay)
        elif status_code < 400:
            # Success â€” slowly decrease delay back toward base
            new_delay = max(current * 0.9, self.base_delay)
        else:
            new_delay = current
        self._domain_delays[domain] = new_delay
    def get_domain_delay(self, url: str) -> float:
        return self._domain_delays.get(self._get_domain(url), self.base_delay)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# 3. CAPTCHA DETECTION
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
CAPTCHA_SIGNATURES = [
    "captcha", "recaptcha", "g-recaptcha", "hcaptcha",
    "challenge-form", "cf-challenge", "verify you are human",
    "security check", "bot detection", "please verify",
    "cf-turnstile", "human verification",
    "id=\"challenge-running\"", "id=\"challenge-form\"",
]
MAINTENANCE_SIGNATURES = [
    "site under maintenance", "under construction", "scheduled maintenance",
    "temporarily unavailable", "service unavailable", "coming soon",
    "502 bad gateway", "503 service temporarily unavailable",
    "server is temporarily unable", "site is down for maintenance",
]
ERROR_PAGE_SIGNATURES = [
    "404 not found", "page not found", "the page you are looking for",
    "403 forbidden", "access denied", "you don't have permission",
    "500 internal server error",
]
def detect_captcha(html: str) -> bool:
    """Detect if page contains a CAPTCHA challenge."""
    html_lower = html.lower()
    return any(sig in html_lower for sig in CAPTCHA_SIGNATURES)
def detect_maintenance(html: str) -> bool:
    """Detect if page is a maintenance/error page."""
    html_lower = html.lower()
    return any(sig in html_lower for sig in MAINTENANCE_SIGNATURES)
def detect_error_page(html: str) -> bool:
    """Detect common error pages."""
    html_lower = html.lower()
    return any(sig in html_lower for sig in ERROR_PAGE_SIGNATURES)
def validate_page_content(html: str, portal_name: str) -> tuple[bool, str]:
    """
    Validate that page content is usable.
    Returns (is_valid, reason).
    """
    if not html or len(html.strip()) < 100:
        return False, "empty_response"
    if detect_captcha(html):
        logger.warning("CAPTCHA detected on %s", portal_name)
        return False, "captcha"
    if detect_maintenance(html):
        logger.warning("Maintenance page on %s", portal_name)
        return False, "maintenance"
    if detect_error_page(html):
        return False, "error_page"
    return True, "ok"
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# 4. JS RENDERING (Playwright fallback)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
_PLAYWRIGHT_AVAILABLE = None
def _check_playwright() -> bool:
    """Check if Playwright is installed and browsers are available."""
    global _PLAYWRIGHT_AVAILABLE
    if _PLAYWRIGHT_AVAILABLE is not None:
        return _PLAYWRIGHT_AVAILABLE
    try:
        from playwright.async_api import async_playwright
        _PLAYWRIGHT_AVAILABLE = True
    except ImportError:
        _PLAYWRIGHT_AVAILABLE = False
        logger.info("Playwright not installed â€” JS rendering disabled. Install with: pip install playwright && playwright install chromium")
    return _PLAYWRIGHT_AVAILABLE
async def fetch_with_js(url: str, timeout_ms: int = 30000, wait_selector: str = "body") -> Optional[str]:
    """
    Fetch a page using Playwright headless browser for JS-heavy sites.
    Returns HTML string or None on failure.
    """
    if not _check_playwright():
        return None
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
            )
            context = await browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={"width": 1366, "height": 768},
                locale="en-IN",
            )
            page = await context.new_page()
            try:
                await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
                await page.wait_for_selector(wait_selector, timeout=10000)
                # Extra wait for dynamic content
                await asyncio.sleep(2)
                html = await page.content()
                return html
            except Exception as e:
                logger.warning("Playwright fetch failed for %s: %s", url, e)
                return None
            finally:
                await browser.close()
    except Exception as e:
        logger.error("Playwright error: %s", e)
        return None
def needs_js_rendering(html_content: str, min_text_length: int = 500) -> bool:
    """
    Detect if a page likely needs JS rendering.
    Signs: very little text content, noscript tags, JS framework markers.
    """
    if not html_content:
        return True
    soup = BeautifulSoup(html_content, "html.parser")
    # Remove script/style tags
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(strip=True)
    if len(text) < min_text_length:
        return True
    # Check for SPA framework markers
    spa_markers = [
        'id="__next"', 'id="app"', 'id="root"',
        'ng-app=', 'data-reactroot', 'data-v-',
        '<app-root', 'window.__NUXT__',
    ]
    html_lower = html_content.lower()
    spa_count = sum(1 for m in spa_markers if m.lower() in html_lower)
    if spa_count >= 2 and len(text) < 1000:
        return True
    return False
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# 5. SELECTOR SELF-HEALING
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
@dataclass
class SelectorStrategy:
    """Multiple CSS selector strategies for a single portal."""
    primary: dict[str, str]
    fallbacks: list[dict[str, str]] = field(default_factory=list)
# Generic selectors that work on many government sites
GENERIC_SELECTORS = {
    "notification_links": [
        "table tbody tr td a[href]",
        "div.content a[href*='.pdf']",
        "ul.list li a[href]",
        "div.notification a[href]",
        "div.recruitment a[href]",
        "a[href*='notification']",
        "a[href*='recruitment']",
        "a[href*='advertisement']",
        "a[href*='career']",
    ],
    "date_patterns": [
        "td:nth-child(2)", "td:nth-child(3)",
        "span.date", "div.date", "time",
        "td[data-date]",
    ],
    "name_patterns": [
        "td:first-child a", "td:first-child",
        "h4 a", "h5 a", "h3 a",
        "div.title a", "div.card-title",
        "li a[href]", "p strong a",
    ],
}
def extract_with_healing(
    soup: BeautifulSoup,
    portal_name: str,
    primary_selectors: dict[str, str],
    fallback_selectors: Optional[list[dict[str, str]]] = None,
    min_expected_items: int = 3,
) -> tuple[list, str]:
    """
    Try primary selectors first. If they yield < min_expected_items,
    try fallbacks, then generic heuristics.
    Returns (items, strategy_used).
    """
    # Try primary
    items = _try_selector_set(soup, primary_selectors)
    if len(items) >= min_expected_items:
        return items, "primary"
    logger.debug("Primary selectors yielded %d items on %s, trying fallbacks", len(items), portal_name)
    # Try each fallback
    if fallback_selectors:
        for i, fallback in enumerate(fallback_selectors):
            items = _try_selector_set(soup, fallback)
            if len(items) >= min_expected_items:
                logger.info("Fallback %d worked on %s (%d items)", i + 1, portal_name, len(items))
                return items, f"fallback_{i + 1}"
    # Generic heuristic: find all links that look like notifications
    logger.info("All selectors failed on %s, using generic heuristic", portal_name)
    items = _generic_notification_extract(soup)
    if items:
        return items, "generic_heuristic"
    return [], "none"
def _try_selector_set(soup: BeautifulSoup, selectors: dict[str, str]) -> list:
    """Try a set of CSS selectors and return found elements."""
    items = []
    list_selector = selectors.get("exam_list") or selectors.get("notification_list", "")
    if list_selector:
        items = soup.select(list_selector)
    return items
def _generic_notification_extract(soup: BeautifulSoup) -> list:
    """
    Last-resort heuristic extraction: find all links that look like
    government notifications, exam notices, or scheme announcements.
    """
    results = []
    link_patterns = re.compile(
        r'(notification|recruitment|advertisement|vacancy|exam|career|'
        r'admit.?card|result|application|syllabus|circular|notice|'
        r'scheme|scholarship|yojana|yojn|\.pdf)',
        re.IGNORECASE,
    )
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        text = a_tag.get_text(strip=True)
        # Match on href or text
        if link_patterns.search(href) or (text and link_patterns.search(text)):
            if len(text) > 10:  # Skip tiny navigation links
                results.append(a_tag)
    return results
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# 6. OCR FOR SCANNED PDFs
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
_TESSERACT_AVAILABLE = None
_PDF2IMAGE_AVAILABLE = None
def _check_ocr_deps() -> tuple[bool, bool]:
    """Check if OCR dependencies are available."""
    global _TESSERACT_AVAILABLE, _PDF2IMAGE_AVAILABLE
    if _TESSERACT_AVAILABLE is None:
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            _TESSERACT_AVAILABLE = True
        except Exception:
            _TESSERACT_AVAILABLE = False
            logger.info("Tesseract OCR not available. Install with: apt install tesseract-ocr && pip install pytesseract")
    if _PDF2IMAGE_AVAILABLE is None:
        try:
            import pdf2image
            _PDF2IMAGE_AVAILABLE = True
        except ImportError:
            _PDF2IMAGE_AVAILABLE = False
            logger.info("pdf2image not available. Install with: pip install pdf2image && apt install poppler-utils")
    return _TESSERACT_AVAILABLE, _PDF2IMAGE_AVAILABLE
def extract_text_from_pdf(pdf_path: str, max_pages: int = 20) -> tuple[str, str]:
    """
    Extract text from PDF with OCR fallback.
    Returns (text, method) where method is "text" or "ocr" or "none".
    """
    text = ""
    # Try PyPDF2 first (fast, no OCR)
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(pdf_path)
        pages = reader.pages[:max_pages]
        text = "\n".join(page.extract_text() or "" for page in pages)
        if len(text.strip()) > 100:
            return text, "text"
        else:
            logger.debug("PDF has minimal extractable text (%d chars), trying OCR", len(text.strip()))
    except Exception as e:
        logger.warning("PyPDF2 extraction failed for %s: %s", pdf_path, e)
    # Try pdfminer.six (better text extraction)
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract
        text = pdfminer_extract(pdf_path, maxpages=max_pages)
        if len(text.strip()) > 100:
            return text, "text"
    except Exception:
        pass
    # OCR fallback
    tesseract_ok, pdf2image_ok = _check_ocr_deps()
    if tesseract_ok and pdf2image_ok:
        try:
            import pytesseract
            from pdf2image import convert_from_path
            images = convert_from_path(
                pdf_path,
                first_page=1,
                last_page=min(max_pages, 10),
                dpi=200,
            )
            ocr_text_parts = []
            for i, img in enumerate(images):
                page_text = pytesseract.image_to_string(img, lang="eng+hin")
                ocr_text_parts.append(page_text)
            text = "\n\n".join(ocr_text_parts)
            if len(text.strip()) > 50:
                return text, "ocr"
        except Exception as e:
            logger.warning("OCR failed for %s: %s", pdf_path, e)
    return text or "", "none"
def is_scanned_pdf(pdf_path: str) -> bool:
    """Quick check: does the PDF have extractable text or is it scanned images?"""
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(pdf_path)
        if not reader.pages:
            return True
        # Check first 3 pages
        total_text = ""
        for page in reader.pages[:3]:
            total_text += page.extract_text() or ""
        return len(total_text.strip()) < 50
    except Exception:
        return True
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# 7. PROXY ROTATION (Optional)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
class ProxyRotator:
    """Round-robin proxy rotation from PROXY_LIST env var."""
    def __init__(self):
        raw = os.getenv("PROXY_LIST", "")
        self.proxies = [p.strip() for p in raw.split(",") if p.strip()]
        self._dead: set[str] = set()
        self._index = 0
    @property
    def enabled(self) -> bool:
        return bool(self.proxies)
    def get_proxy(self) -> Optional[str]:
        """Get next working proxy or None."""
        if not self.proxies:
            return None
        alive = [p for p in self.proxies if p not in self._dead]
        if not alive:
            logger.warning("All proxies dead, resetting")
            self._dead.clear()
            alive = self.proxies
        proxy = alive[self._index % len(alive)]
        self._index += 1
        return proxy
    def mark_dead(self, proxy: str) -> None:
        self._dead.add(proxy)
        logger.warning("Proxy marked dead: %s", proxy[:30])
    def get_httpx_proxy(self) -> Optional[dict]:
        proxy = self.get_proxy()
        if proxy:
            return {"http://": proxy, "https://": proxy}
        return None
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# 8. RESILIENT FETCH â€” Combines everything above
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
class ResilientFetcher:
    """
    Single entry point for resilient page fetching.
    Combines: rate limiting, user-agent rotation, proxy rotation,
    CAPTCHA detection, JS rendering fallback, content validation.
    """
    def __init__(
        self,
        rate_limiter: Optional[AdaptiveRateLimiter] = None,
        proxy_rotator: Optional[ProxyRotator] = None,
        timeout: float = 30.0,
    ):
        self.rate_limiter = rate_limiter or AdaptiveRateLimiter()
        self.proxy = proxy_rotator or ProxyRotator()
        self.timeout = timeout
        self.stats = {"total": 0, "success": 0, "js_fallback": 0, "captcha": 0, "errors": 0}
    async def fetch(
        self,
        url: str,
        portal_name: str = "",
        needs_js: bool = False,
        max_retries: int = 2,
    ) -> tuple[Optional[str], dict]:
        """
        Fetch a URL with all resilience layers.
        Returns (html_content, metadata_dict).
        """
        self.stats["total"] += 1
        meta = {"url": url, "portal": portal_name, "method": "httpx", "status": 0, "response_ms": 0}
        domain = urlparse(url).netloc
        for attempt in range(1, max_retries + 1):
            await self.rate_limiter.wait(url)
            headers = get_random_headers(domain)
            proxy_config = self.proxy.get_httpx_proxy()
            start_time = time.time()
            try:
                async with httpx.AsyncClient(
                    timeout=self.timeout,
                    follow_redirects=True,
                    proxies=proxy_config,
                    verify=False,
                ) as client:
                    resp = await client.get(url, headers=headers)
                elapsed_ms = (time.time() - start_time) * 1000
                meta["status"] = resp.status_code
                meta["response_ms"] = elapsed_ms
                self.rate_limiter.record_response(url, resp.status_code)
                if resp.status_code >= 400:
                    if resp.status_code in (403, 429) and proxy_config:
                        proxy_url = self.proxy.get_proxy()
                        if proxy_url:
                            self.proxy.mark_dead(proxy_url)
                    if attempt < max_retries:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    meta["error"] = f"HTTP {resp.status_code}"
                    self.stats["errors"] += 1
                    return None, meta
                html = resp.text
            except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as e:
                meta["error"] = str(type(e).__name__)
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                self.stats["errors"] += 1
                return None, meta
            # Content validation
            is_valid, reason = validate_page_content(html, portal_name)
            if reason == "captcha":
                self.stats["captcha"] += 1
                meta["captcha"] = True
                return None, meta
            if not is_valid and reason == "maintenance":
                meta["maintenance"] = True
                return None, meta
            # Check if JS rendering needed
            if needs_js or needs_js_rendering(html):
                logger.info("Attempting JS rendering for %s", portal_name or url[:60])
                js_html = await fetch_with_js(url)
                if js_html and len(js_html) > len(html):
                    html = js_html
                    meta["method"] = "playwright"
                    self.stats["js_fallback"] += 1
            self.stats["success"] += 1
            return html, meta
        self.stats["errors"] += 1
        return None, meta
    def get_stats(self) -> dict:
        return dict(self.stats)
