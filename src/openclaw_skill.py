"""
GovScheme SuperAgent â€” OpenClaw Skill Integration
Exposes the agent pipeline as an OpenClaw skill for the buildathon.
"""
from __future__ import annotations
import asyncio
import json
import os
from pathlib import Path
# â”€â”€â”€ OpenClaw Skill Manifest â”€â”€â”€
OPENCLAW_SKILL_MANIFEST = {
    "name": "govscheme-india",
    "version": "1.0.0",
    "description": (
        "Crawls 50+ Indian government portals to discover, classify, and organize "
        "700+ scholarships, grants, startup funds, and welfare schemes. "
        "Organizes into structured folder hierarchies by Central/State/UT, "
        "sector, and scheme type."
    ),
    "author": "GovScheme SuperAgent Team",
    "tags": ["india", "government", "scholarships", "grants", "crawling", "agents"],
    "triggers": [
        "find indian government schemes",
        "search scholarships india",
        "crawl government portals",
        "find grants for startup india",
        "list state scholarships",
    ],
    "parameters": {
        "mode": {
            "type": "string",
            "enum": ["full", "discover", "classify", "search"],
            "default": "full",
            "description": "Pipeline mode: full (crawl+classify+store), discover (crawl only), search (query existing)",
        },
        "state": {
            "type": "string",
            "description": "Filter by Indian state (e.g., 'Tamil_Nadu', 'Karnataka')",
            "required": False,
        },
        "sector": {
            "type": "string",
            "description": "Filter by sector (e.g., 'Education', 'Startup', 'Agriculture')",
            "required": False,
        },
        "query": {
            "type": "string",
            "description": "Search query for finding specific schemes",
            "required": False,
        },
    },
}
async def run_skill(params: dict) -> dict:
    """
    OpenClaw skill entry point.
    Called when the skill is triggered via OpenClaw agent.
    """
    from src.config.settings import AgentConfig
    from src.orchestrator import Orchestrator
    mode = params.get("mode", "full")
    state_filter = params.get("state")
    sector_filter = params.get("sector")
    query = params.get("query")
    config = AgentConfig(
        output_dir=os.getenv("GOVSCHEME_OUTPUT_DIR", "./output"),
    )
    if mode == "search" and query:
        return await _search_existing(query, state_filter, sector_filter, config)
    orchestrator = Orchestrator(config)
    if mode == "full":
        await orchestrator.run_full_pipeline()
        return {
            "status": "complete",
            "total_schemes": orchestrator.progress.schemes_stored,
            "duplicates_removed": orchestrator.progress.duplicates_found,
            "output_dir": config.output_dir,
            "elapsed_minutes": orchestrator.progress.elapsed_minutes,
        }
    elif mode == "discover":
        await orchestrator.run_discovery_only()
        return {
            "status": "discovery_complete",
            "total_discovered": orchestrator.progress.total_schemes_discovered,
        }
    return {"status": "error", "message": f"Unknown mode: {mode}"}
async def _search_existing(
    query: str,
    state_filter: str | None,
    sector_filter: str | None,
    config,
) -> dict:
    """Search through already-crawled scheme data."""
    index_path = Path(config.output_dir) / "reports" / "scheme_index.json"
    if not index_path.exists():
        return {
            "status": "error",
            "message": "No crawl data found. Run with mode='full' first.",
        }
    index = json.loads(index_path.read_text())
    results = []
    query_lower = query.lower()
    for scheme in index:
        name_match = query_lower in scheme["name"].lower()
        sector_match = not sector_filter or scheme["sector"] == sector_filter
        state_match = not state_filter or scheme.get("state") == state_filter
        if name_match and sector_match and state_match:
            results.append(scheme)
    return {
        "status": "success",
        "query": query,
        "results_count": len(results),
        "results": results[:50],  # Limit response size
    }
# â”€â”€â”€ OpenClaw Heartbeat Handler â”€â”€â”€
async def heartbeat() -> dict:
    """
    Called periodically by OpenClaw to check skill health.
    Can also be used for scheduled re-crawls.
    """
    output_dir = os.getenv("GOVSCHEME_OUTPUT_DIR", "./output")
    summary_path = Path(output_dir) / "reports" / "crawl_summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text())
        return {
            "status": "healthy",
            "last_crawl": summary.get("generated_at"),
            "total_schemes": summary.get("total_schemes", 0),
        }
    return {"status": "healthy", "last_crawl": None, "total_schemes": 0}
