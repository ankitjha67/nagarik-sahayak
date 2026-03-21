"""
GovScheme SuperAgent â€” Storage Agent
Organizes classified schemes into structured folder hierarchies
and downloads associated PDFs, forms, and guidelines.
"""
from __future__ import annotations
import asyncio
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
import httpx
from src.agents.models import ClassifiedScheme, StoredScheme, SchemeLevel
from src.config.settings import AgentConfig
logger = logging.getLogger("storage_agent")
class StorageAgent:
    """
    Organizes classified schemes into the folder hierarchy:
    output/
    â”œâ”€â”€ Central/
    â”‚   â”œâ”€â”€ Education/
    â”‚   â”‚   â””â”€â”€ Scheme_Name/
    â”‚   â”‚       â”œâ”€â”€ metadata.json
    â”‚   â”‚       â”œâ”€â”€ scheme_details.md
    â”‚   â”‚       â””â”€â”€ *.pdf
    â”œâ”€â”€ State/
    â”‚   â””â”€â”€ Tamil_Nadu/
    â”‚       â””â”€â”€ Fisheries/
    â””â”€â”€ Union_Territory/
    """
    def __init__(self, config: AgentConfig):
        self.config = config
        self.output_dir = Path(config.output_dir)
        self.stored_count = 0
        self.download_errors = 0
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        }
    def _sanitize_filename(self, name: str) -> str:
        """Clean a string for use as a folder/file name."""
        # Remove special characters, keep alphanumeric and spaces
        clean = re.sub(r'[^\w\s\-]', '', name)
        clean = re.sub(r'\s+', '_', clean.strip())
        return clean[:80]  # Limit length
    def _compute_folder_path(self, scheme: ClassifiedScheme) -> Path:
        """Compute the folder path based on classification."""
        parts = [self.output_dir]
        # Level 1: Central / State / Union_Territory
        parts.append(scheme.level.value)
        # Level 2 (for State/UT): State name
        if scheme.level in (SchemeLevel.STATE, SchemeLevel.UNION_TERRITORY) and scheme.state:
            parts.append(self._sanitize_filename(scheme.state))
        # Level 3: Sector
        parts.append(scheme.sector.value)
        # Level 4: Scheme name folder
        parts.append(self._sanitize_filename(scheme.clean_name))
        return Path(*[str(p) for p in parts])
    async def store_scheme(self, scheme: ClassifiedScheme) -> StoredScheme:
        """Store a classified scheme: create folders, save metadata, download assets."""
        folder = self._compute_folder_path(scheme)
        folder.mkdir(parents=True, exist_ok=True)
        # 1. Save metadata.json
        metadata_path = folder / "metadata.json"
        metadata = {
            "scheme_id": scheme.scheme_id,
            "name": scheme.clean_name,
            "level": scheme.level.value,
            "state": scheme.state,
            "sector": scheme.sector.value,
            "type": scheme.scheme_type.value,
            "summary": scheme.summary,
            "eligibility": scheme.eligibility_summary,
            "benefit_amount": scheme.benefit_amount,
            "target_group": scheme.target_group,
            "source_portal": scheme.raw_data.source_portal,
            "source_url": scheme.raw_data.source_url,
            "detail_url": scheme.raw_data.scheme_detail_url,
            "classification_confidence": scheme.classification_confidence,
            "crawled_at": scheme.raw_data.crawled_at.isoformat(),
            "classified_at": scheme.classified_at.isoformat(),
            "stored_at": datetime.utcnow().isoformat(),
        }
        metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False))
        # 2. Save scheme details markdown
        detail_path = folder / "scheme_details.md"
        detail_md = self._generate_scheme_markdown(scheme)
        detail_path.write_text(detail_md, encoding="utf-8")
        # 3. Download PDFs
        downloaded_pdfs = []
        if self.config.download_pdfs and scheme.raw_data.pdf_urls:
            downloaded_pdfs = await self._download_files(
                scheme.raw_data.pdf_urls, folder, "pdf"
            )
        # 4. Download forms
        downloaded_forms = []
        if self.config.download_forms and scheme.raw_data.form_urls:
            downloaded_forms = await self._download_files(
                scheme.raw_data.form_urls, folder, "form"
            )
        # 5. Save the website URL as a .url shortcut
        url_path = folder / "website.url"
        website_url = scheme.raw_data.scheme_detail_url or scheme.raw_data.source_url
        url_path.write_text(
            f"[InternetShortcut]\nURL={website_url}\n", encoding="utf-8"
        )
        self.stored_count += 1
        stored = StoredScheme(
            classified=scheme,
            folder_path=str(folder),
            metadata_path=str(metadata_path),
            detail_markdown_path=str(detail_path),
            downloaded_pdfs=downloaded_pdfs,
            downloaded_forms=downloaded_forms,
        )
        logger.info(
            "Stored: %s â†’ %s (%d PDFs, %d forms)",
            scheme.clean_name, folder, len(downloaded_pdfs), len(downloaded_forms),
        )
        return stored
    async def store_batch(
        self, schemes: list[ClassifiedScheme], max_concurrent: int = 5
    ) -> list[StoredScheme]:
        """Store a batch of schemes concurrently."""
        sem = asyncio.Semaphore(max_concurrent)
        stored = []
        async def _store_one(s: ClassifiedScheme) -> Optional[StoredScheme]:
            async with sem:
                try:
                    return await self.store_scheme(s)
                except Exception as e:
                    logger.error("Store failed for '%s': %s", s.clean_name, e)
                    return None
        tasks = [_store_one(s) for s in schemes]
        results = await asyncio.gather(*tasks)
        for result in results:
            if isinstance(result, StoredScheme):
                stored.append(result)
        return stored
    def _generate_scheme_markdown(self, scheme: ClassifiedScheme) -> str:
        """Generate a detailed markdown file for the scheme."""
        raw = scheme.raw_data
        lines = [
            f"# {scheme.clean_name}",
            "",
            f"**Level:** {scheme.level.value}",
        ]
        if scheme.state:
            lines.append(f"**State/UT:** {scheme.state.replace('_', ' ')}")
        lines.extend([
            f"**Sector:** {scheme.sector.value.replace('_', ' ')}",
            f"**Type:** {scheme.scheme_type.value.replace('_', ' ')}",
            f"**Source:** [{raw.source_portal}]({raw.source_url})",
            "",
        ])
        if scheme.summary:
            lines.extend(["## Summary", "", scheme.summary, ""])
        if scheme.benefit_amount:
            lines.extend(["## Benefits", "", f"**Amount:** {scheme.benefit_amount}", ""])
        if raw.raw_benefits:
            lines.extend([raw.raw_benefits[:1000], ""])
        if scheme.eligibility_summary:
            lines.extend(["## Eligibility", "", scheme.eligibility_summary, ""])
        if raw.raw_eligibility and raw.raw_eligibility != scheme.eligibility_summary:
            lines.extend(["### Detailed Eligibility", "", raw.raw_eligibility[:1000], ""])
        if raw.raw_application_process:
            lines.extend(["## How to Apply", "", raw.raw_application_process[:1000], ""])
        if raw.raw_documents_required:
            lines.extend(["## Documents Required", "", raw.raw_documents_required[:1000], ""])
        if scheme.target_group:
            lines.extend(["## Target Group", "", scheme.target_group, ""])
        # Links
        lines.extend(["## Links", ""])
        if raw.scheme_detail_url:
            lines.append(f"- [Official Scheme Page]({raw.scheme_detail_url})")
        lines.append(f"- [Source Portal]({raw.source_url})")
        if raw.pdf_urls:
            lines.extend(["", "### Documents"])
            for i, pdf_url in enumerate(raw.pdf_urls):
                lines.append(f"- [Document {i + 1}]({pdf_url})")
        lines.extend([
            "",
            "---",
            f"*Crawled: {raw.crawled_at.strftime('%Y-%m-%d %H:%M')} UTC*",
            f"*Classification Confidence: {scheme.classification_confidence:.0%}*",
        ])
        return "\n".join(lines)
    async def _download_files(
        self, urls: list[str], folder: Path, prefix: str
    ) -> list[str]:
        """Download files (PDFs, forms) to the scheme folder."""
        downloaded = []
        async with httpx.AsyncClient(
            headers=self.headers,
            timeout=30,
            follow_redirects=True,
        ) as client:
            for i, url in enumerate(urls[:10]):  # Limit to 10 files per scheme
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        continue
                    # Determine filename
                    content_type = resp.headers.get("content-type", "")
                    ext = ".pdf"
                    if "html" in content_type:
                        ext = ".html"
                    elif "doc" in content_type:
                        ext = ".doc"
                    # Check file size
                    content_length = len(resp.content)
                    if content_length > self.config.max_pdf_size_mb * 1024 * 1024:
                        logger.warning("File too large (%d MB): %s", content_length // (1024*1024), url)
                        continue
                    filename = f"{prefix}_{i + 1}{ext}"
                    filepath = folder / filename
                    filepath.write_bytes(resp.content)
                    downloaded.append(str(filepath))
                    logger.debug("Downloaded: %s â†’ %s", url, filepath)
                except Exception as e:
                    logger.warning("Download failed %s: %s", url, e)
                    self.download_errors += 1
        return downloaded
    async def generate_reports(self, stored_schemes: list[StoredScheme]) -> None:
        """Generate summary reports in the output directory."""
        reports_dir = self.output_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        # Crawl Summary
        summary = {
            "total_schemes": len(stored_schemes),
            "by_level": {},
            "by_sector": {},
            "by_type": {},
            "by_state": {},
            "generated_at": datetime.utcnow().isoformat(),
        }
        for s in stored_schemes:
            c = s.classified
            level = c.level.value
            summary["by_level"][level] = summary["by_level"].get(level, 0) + 1
            sector = c.sector.value
            summary["by_sector"][sector] = summary["by_sector"].get(sector, 0) + 1
            stype = c.scheme_type.value
            summary["by_type"][stype] = summary["by_type"].get(stype, 0) + 1
            if c.state:
                state = c.state
                summary["by_state"][state] = summary["by_state"].get(state, 0) + 1
        (reports_dir / "crawl_summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False)
        )
        # Sector Distribution
        (reports_dir / "sector_distribution.json").write_text(
            json.dumps(summary["by_sector"], indent=2)
        )
        # State Distribution
        (reports_dir / "state_distribution.json").write_text(
            json.dumps(summary["by_state"], indent=2)
        )
        # Full scheme index
        index = []
        for s in stored_schemes:
            c = s.classified
            index.append({
                "name": c.clean_name,
                "level": c.level.value,
                "state": c.state,
                "sector": c.sector.value,
                "type": c.scheme_type.value,
                "folder": s.folder_path,
                "source_url": c.raw_data.source_url,
            })
        (reports_dir / "scheme_index.json").write_text(
            json.dumps(index, indent=2, ensure_ascii=False)
        )
        logger.info("Reports generated in %s", reports_dir)
