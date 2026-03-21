"""
GovScheme SuperAgent â€” Discovery Crawler Agent
Crawls government portals to discover scheme listings.
Handles API-based, HTML-based, and paginated crawling strategies.
"""
from __future__ import annotations
import asyncio
import json
import logging
import re
from datetime import datetime
from typing import AsyncGenerator, Optional
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential
from src.agents.models import RawSchemeData, CrawlStatus
from src.config.settings import (
    PortalSource, PORTAL_SOURCES, MYSCHEME_CATEGORIES,
    MYSCHEME_STATE_SLUGS, AgentConfig,
)
logger = logging.getLogger("discovery_agent")
class DiscoveryCrawler:
    """
    Agent that crawls government portals to discover schemes.
    Supports multiple crawling strategies:
      - API: Direct API calls (myScheme, Startup India)
      - HTML: BeautifulSoup-based scraping
      - Paginated: Multi-page crawling with pagination
    """
    def __init__(self, config: AgentConfig):
        self.config = config
        self.discovered: list[RawSchemeData] = []
        self.seen_urls: set[str] = set()
        self.errors: list[dict] = []
        self._rate_limiter = asyncio.Semaphore(config.max_concurrent_crawlers)
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/json",
            "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8",
        }
    async def crawl_all_sources(self) -> list[RawSchemeData]:
        """Crawl all configured portal sources concurrently."""
        logger.info("Starting discovery crawl across %d sources", len(PORTAL_SOURCES))
        tasks = []
        for source in sorted(PORTAL_SOURCES, key=lambda s: s.priority):
            tasks.append(self._crawl_source_safe(source))
        # Also crawl myScheme categories and states
        tasks.append(self._crawl_myscheme_all_categories())
        tasks.append(self._crawl_myscheme_all_states())
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                logger.error("Source crawl failed: %s", result)
                self.errors.append({"error": str(result), "time": datetime.utcnow().isoformat()})
            elif isinstance(result, list):
                for scheme in result:
                    if scheme.source_url not in self.seen_urls:
                        self.seen_urls.add(scheme.source_url)
                        self.discovered.append(scheme)
        logger.info("Discovery complete: %d unique schemes found", len(self.discovered))
        return self.discovered
    async def _crawl_source_safe(self, source: PortalSource) -> list[RawSchemeData]:
        """Crawl a single source with error handling and rate limiting."""
        async with self._rate_limiter:
            try:
                logger.info("Crawling: %s (%s strategy)", source.name, source.crawl_strategy)
                if source.crawl_strategy == "api":
                    return await self._crawl_api(source)
                elif source.crawl_strategy == "html":
                    return await self._crawl_html(source)
                elif source.crawl_strategy == "paginated":
                    return await self._crawl_paginated(source)
                else:
                    return await self._crawl_html(source)
            except Exception as e:
                logger.error("Failed to crawl %s: %s", source.name, e)
                self.errors.append({
                    "source": source.name,
                    "error": str(e),
                    "time": datetime.utcnow().isoformat(),
                })
                return []
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # STRATEGY: API-based crawling
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def _crawl_api(self, source: PortalSource) -> list[RawSchemeData]:
        """Crawl API endpoints that return JSON."""
        schemes = []
        async with httpx.AsyncClient(
            headers=self.headers,
            timeout=self.config.request_timeout,
            follow_redirects=True,
        ) as client:
            page = 1
            while page <= source.max_pages:
                url = source.api_endpoint or source.base_url
                params = {}
                if source.pagination_param:
                    params[source.pagination_param] = page
                    params["limit"] = 50
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    logger.warning("API %s returned %d on page %d", source.name, resp.status_code, page)
                    break
                try:
                    data = resp.json()
                except json.JSONDecodeError:
                    # Fall back to HTML parsing
                    return await self._crawl_html(source)
                page_schemes = self._parse_api_response(data, source)
                if not page_schemes:
                    break
                schemes.extend(page_schemes)
                page += 1
                await asyncio.sleep(1.0 / source.rate_limit_per_sec)
        logger.info("API crawl %s: found %d schemes", source.name, len(schemes))
        return schemes
    def _parse_api_response(self, data: dict | list, source: PortalSource) -> list[RawSchemeData]:
        """Parse JSON API response into RawSchemeData objects."""
        schemes = []
        # Handle different API response structures
        items = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            # Try common JSON patterns
            for key in ["data", "schemes", "results", "records", "items", "content"]:
                if key in data and isinstance(data[key], list):
                    items = data[key]
                    break
            if not items and "scheme" in data:
                items = [data["scheme"]]
        for item in items:
            if not isinstance(item, dict):
                continue
            name = (
                item.get("schemeName")
                or item.get("scheme_name")
                or item.get("name")
                or item.get("title")
                or ""
            ).strip()
            if not name or len(name) < 5:
                continue
            detail_url = (
                item.get("schemeUrl")
                or item.get("url")
                or item.get("link")
                or item.get("detailUrl")
                or ""
            )
            if detail_url and not detail_url.startswith("http"):
                detail_url = urljoin(source.base_url, detail_url)
            pdf_urls = []
            for key in ["pdfUrl", "guidelinesUrl", "documentUrl", "formUrl"]:
                if key in item and item[key]:
                    pdf_urls.append(item[key])
            scheme = RawSchemeData(
                source_portal=source.name,
                source_url=detail_url or source.base_url,
                scheme_name=name,
                scheme_detail_url=detail_url,
                raw_description=item.get("description") or item.get("details") or item.get("brief"),
                raw_eligibility=item.get("eligibility") or item.get("eligibilityCriteria"),
                raw_benefits=item.get("benefits") or item.get("benefitDetails"),
                raw_application_process=item.get("applicationProcess") or item.get("howToApply"),
                raw_documents_required=item.get("documentsRequired") or item.get("requiredDocuments"),
                raw_ministry=item.get("ministry") or item.get("department") or item.get("nodal_ministry"),
                raw_state=item.get("state") or item.get("stateName"),
                raw_category=item.get("category") or item.get("schemeCategory"),
                pdf_urls=pdf_urls,
            )
            schemes.append(scheme)
        return schemes
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # STRATEGY: HTML-based crawling
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def _crawl_html(self, source: PortalSource) -> list[RawSchemeData]:
        """Crawl HTML pages using BeautifulSoup."""
        schemes = []
        async with httpx.AsyncClient(
            headers=self.headers,
            timeout=self.config.request_timeout,
            follow_redirects=True,
        ) as client:
            resp = await client.get(source.base_url)
            if resp.status_code != 200:
                logger.warning("HTML %s returned %d", source.name, resp.status_code)
                return []
            soup = BeautifulSoup(resp.text, "lxml")
            # Try CSS selectors from config
            if source.selectors.get("scheme_list"):
                elements = soup.select(source.selectors["scheme_list"])
                for el in elements:
                    scheme = self._extract_scheme_from_element(el, source, soup)
                    if scheme:
                        schemes.append(scheme)
            # Fallback: find all links that look like scheme pages
            if not schemes:
                schemes = self._extract_schemes_from_links(soup, source)
            # Look for pagination and crawl additional pages
            if source.pagination_param:
                next_pages = self._find_pagination_links(soup, source.base_url)
                for page_url in next_pages[:source.max_pages]:
                    await asyncio.sleep(1.0 / source.rate_limit_per_sec)
                    page_schemes = await self._crawl_single_page(client, page_url, source)
                    schemes.extend(page_schemes)
        logger.info("HTML crawl %s: found %d schemes", source.name, len(schemes))
        return schemes
    def _extract_scheme_from_element(
        self, el, source: PortalSource, soup: BeautifulSoup
    ) -> Optional[RawSchemeData]:
        """Extract scheme data from a single HTML element."""
        # Get scheme name
        name_el = el.select_one(source.selectors.get("scheme_name", "h3, h4, a"))
        name = name_el.get_text(strip=True) if name_el else el.get_text(strip=True)[:200]
        if not name or len(name) < 5:
            return None
        # Get link
        link_el = el.select_one(source.selectors.get("scheme_link", "a[href]"))
        if not link_el:
            link_el = el.find("a")
        href = link_el.get("href", "") if link_el else ""
        if href and not href.startswith("http"):
            href = urljoin(source.base_url, href)
        # Get description
        desc_el = el.select_one("p, div.description, span.summary")
        description = desc_el.get_text(strip=True) if desc_el else None
        return RawSchemeData(
            source_portal=source.name,
            source_url=href or source.base_url,
            scheme_name=name,
            scheme_detail_url=href,
            raw_description=description,
            raw_state=source.state,
        )
    def _extract_schemes_from_links(
        self, soup: BeautifulSoup, source: PortalSource
    ) -> list[RawSchemeData]:
        """Fallback: extract schemes from all relevant links on the page."""
        schemes = []
        scheme_keywords = [
            "scheme", "scholarship", "grant", "fellowship", "fund",
            "subsidy", "yojana", "pension", "stipend", "award",
        ]
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            text = link.get_text(strip=True)
            if not text or len(text) < 5:
                continue
            href_lower = href.lower()
            text_lower = text.lower()
            if any(kw in href_lower or kw in text_lower for kw in scheme_keywords):
                full_url = href if href.startswith("http") else urljoin(source.base_url, href)
                schemes.append(RawSchemeData(
                    source_portal=source.name,
                    source_url=full_url,
                    scheme_name=text,
                    scheme_detail_url=full_url,
                    raw_state=source.state,
                ))
        return schemes
    def _find_pagination_links(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        """Find pagination links on the page."""
        pages = []
        # Common pagination patterns
        for link in soup.select("a.page-link, a.pagination-link, li.page-item a, a[href*='page=']"):
            href = link.get("href", "")
            if href and href not in pages:
                full_url = href if href.startswith("http") else urljoin(base_url, href)
                pages.append(full_url)
        return pages
    async def _crawl_single_page(
        self, client: httpx.AsyncClient, url: str, source: PortalSource
    ) -> list[RawSchemeData]:
        """Crawl a single page URL."""
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return []
            soup = BeautifulSoup(resp.text, "lxml")
            if source.selectors.get("scheme_list"):
                schemes = []
                for el in soup.select(source.selectors["scheme_list"]):
                    scheme = self._extract_scheme_from_element(el, source, soup)
                    if scheme:
                        schemes.append(scheme)
                return schemes
            return self._extract_schemes_from_links(soup, source)
        except Exception as e:
            logger.warning("Page crawl failed %s: %s", url, e)
            return []
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # STRATEGY: Paginated crawling
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    async def _crawl_paginated(self, source: PortalSource) -> list[RawSchemeData]:
        """Crawl paginated endpoints."""
        schemes = []
        async with httpx.AsyncClient(
            headers=self.headers,
            timeout=self.config.request_timeout,
            follow_redirects=True,
        ) as client:
            for page in range(1, source.max_pages + 1):
                url = f"{source.base_url}?{source.pagination_param}={page}"
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        break
                    soup = BeautifulSoup(resp.text, "lxml")
                    page_schemes = []
                    if source.selectors.get("scheme_list"):
                        for el in soup.select(source.selectors["scheme_list"]):
                            scheme = self._extract_scheme_from_element(el, source, soup)
                            if scheme:
                                page_schemes.append(scheme)
                    else:
                        page_schemes = self._extract_schemes_from_links(soup, source)
                    if not page_schemes:
                        break
                    schemes.extend(page_schemes)
                    await asyncio.sleep(1.0 / source.rate_limit_per_sec)
                except Exception as e:
                    logger.warning("Page %d of %s failed: %s", page, source.name, e)
                    break
        return schemes
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # myScheme-specific crawlers
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    async def _crawl_myscheme_all_categories(self) -> list[RawSchemeData]:
        """Crawl all myScheme categories."""
        schemes = []
        async with httpx.AsyncClient(
            headers=self.headers, timeout=30, follow_redirects=True
        ) as client:
            for category in MYSCHEME_CATEGORIES:
                url = f"https://www.myscheme.gov.in/search?category={category}"
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.text, "lxml")
                        for card in soup.select("div.scheme-card, div.card, li.scheme-item"):
                            name_el = card.select_one("h3, h4, a.title, span.name")
                            if name_el:
                                name = name_el.get_text(strip=True)
                                link = card.select_one("a[href]")
                                href = ""
                                if link:
                                    href = link.get("href", "")
                                    if not href.startswith("http"):
                                        href = urljoin("https://www.myscheme.gov.in", href)
                                schemes.append(RawSchemeData(
                                    source_portal="myScheme_Category",
                                    source_url=href or url,
                                    scheme_name=name,
                                    scheme_detail_url=href,
                                    raw_category=category.replace("-", " ").title(),
                                ))
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.warning("myScheme category %s failed: %s", category, e)
        return schemes
    async def _crawl_myscheme_all_states(self) -> list[RawSchemeData]:
        """Crawl myScheme for each state/UT."""
        schemes = []
        async with httpx.AsyncClient(
            headers=self.headers, timeout=30, follow_redirects=True
        ) as client:
            for state_name, slug in MYSCHEME_STATE_SLUGS.items():
                url = f"https://www.myscheme.gov.in/search?state={slug}"
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.text, "lxml")
                        for card in soup.select("div.scheme-card, div.card, li.scheme-item"):
                            name_el = card.select_one("h3, h4, a.title, span.name")
                            if name_el:
                                name = name_el.get_text(strip=True)
                                link = card.select_one("a[href]")
                                href = ""
                                if link:
                                    href = link.get("href", "")
                                    if not href.startswith("http"):
                                        href = urljoin("https://www.myscheme.gov.in", href)
                                schemes.append(RawSchemeData(
                                    source_portal="myScheme_State",
                                    source_url=href or url,
                                    scheme_name=name,
                                    scheme_detail_url=href,
                                    raw_state=state_name,
                                ))
                    await asyncio.sleep(0.3)
                except Exception as e:
                    logger.warning("myScheme state %s failed: %s", state_name, e)
        return schemes
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Detail page enrichment
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    async def enrich_scheme_details(self, scheme: RawSchemeData) -> RawSchemeData:
        """Fetch the detail page for a scheme and extract additional info."""
        if not scheme.scheme_detail_url:
            return scheme
        try:
            async with httpx.AsyncClient(
                headers=self.headers, timeout=20, follow_redirects=True
            ) as client:
                resp = await client.get(scheme.scheme_detail_url)
                if resp.status_code != 200:
                    return scheme
                soup = BeautifulSoup(resp.text, "lxml")
                # Extract additional details
                if not scheme.raw_description:
                    desc = soup.select_one(
                        "div.scheme-description, div.content, article, div.detail-content"
                    )
                    if desc:
                        scheme.raw_description = desc.get_text(strip=True)[:2000]
                # Find PDF links
                for link in soup.find_all("a", href=True):
                    href = link.get("href", "")
                    if href.lower().endswith(".pdf"):
                        full_url = href if href.startswith("http") else urljoin(
                            scheme.scheme_detail_url, href
                        )
                        if full_url not in scheme.pdf_urls:
                            scheme.pdf_urls.append(full_url)
                # Find form links
                for link in soup.find_all("a", href=True):
                    href = link.get("href", "")
                    text = link.get_text(strip=True).lower()
                    if any(kw in text for kw in ["form", "application", "apply", "download"]):
                        full_url = href if href.startswith("http") else urljoin(
                            scheme.scheme_detail_url, href
                        )
                        if full_url not in scheme.form_urls:
                            scheme.form_urls.append(full_url)
                # Extract eligibility
                if not scheme.raw_eligibility:
                    elig = soup.select_one(
                        "div.eligibility, section.eligibility, div#eligibility"
                    )
                    if elig:
                        scheme.raw_eligibility = elig.get_text(strip=True)[:1000]
        except Exception as e:
            logger.warning("Enrich failed for %s: %s", scheme.scheme_name, e)
        return scheme
    async def enrich_batch(
        self, schemes: list[RawSchemeData], max_concurrent: int = 3
    ) -> list[RawSchemeData]:
        """Enrich multiple schemes concurrently."""
        sem = asyncio.Semaphore(max_concurrent)
        async def _enrich(s: RawSchemeData) -> RawSchemeData:
            async with sem:
                result = await self.enrich_scheme_details(s)
                await asyncio.sleep(0.5)
                return result
        tasks = [_enrich(s) for s in schemes]
        return await asyncio.gather(*tasks)
