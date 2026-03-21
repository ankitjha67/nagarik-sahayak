"""Scheme Discovery routes — integrates V3 crawler into the web app."""
import asyncio
import logging
from datetime import datetime, timezone
from fastapi import HTTPException, BackgroundTasks
from routes import api_router

logger = logging.getLogger(__name__)

# In-memory crawl state (lightweight — single instance app)
_crawl_state = {
    "status": "idle",  # idle | running | completed | failed
    "started_at": None,
    "completed_at": None,
    "schemes_found": 0,
    "schemes_new": 0,
    "schemes_updated": 0,
    "portals_crawled": 0,
    "portals_failed": 0,
    "current_portal": None,
    "error": None,
    "last_run_report": None,
}


def _get_v3_modules():
    """Lazy-import V3 modules to avoid import errors if deps missing."""
    try:
        import sys
        from pathlib import Path
        # Add project root to path so src.* imports work
        project_root = str(Path(__file__).resolve().parent.parent.parent)
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        from src.config.settings import AgentConfig, PORTAL_SOURCES
        from src.crawlers.discovery_crawler import DiscoveryCrawler
        from src.classifiers.classify_agent import ClassificationAgent
        from src.agents.dedup_agent import DeduplicationAgent
        from src.agents.change_agent import ChangeDetectionAgent
        from src.storage.database import SchemeDatabase
        from src.storage.storage_agent import StorageAgent
        from src.resilience.portal_health import PortalHealthMonitor
        return {
            "AgentConfig": AgentConfig,
            "PORTAL_SOURCES": PORTAL_SOURCES,
            "DiscoveryCrawler": DiscoveryCrawler,
            "ClassificationAgent": ClassificationAgent,
            "DeduplicationAgent": DeduplicationAgent,
            "ChangeDetectionAgent": ChangeDetectionAgent,
            "SchemeDatabase": SchemeDatabase,
            "StorageAgent": StorageAgent,
            "PortalHealthMonitor": PortalHealthMonitor,
        }
    except ImportError as e:
        logger.warning(f"V3 modules not available: {e}")
        return None


async def _run_discovery_crawl(portal_names: list[str] | None = None):
    """Background task: run the V3 discovery pipeline."""
    global _crawl_state
    _crawl_state["status"] = "running"
    _crawl_state["started_at"] = datetime.now(timezone.utc).isoformat()
    _crawl_state["error"] = None

    mods = _get_v3_modules()
    if not mods:
        _crawl_state["status"] = "failed"
        _crawl_state["error"] = "V3 crawler dependencies not installed"
        return

    try:
        config = mods["AgentConfig"]()
        sources = mods["PORTAL_SOURCES"]

        # Filter to requested portals if specified
        if portal_names:
            sources = [s for s in sources if s.name in portal_names]

        db = mods["SchemeDatabase"](config.output_dir / "schemes.db")
        crawler = mods["DiscoveryCrawler"](config)
        classifier = mods["ClassificationAgent"](config)
        dedup = mods["DeduplicationAgent"]()
        change_agent = mods["ChangeDetectionAgent"](db)
        storage = mods["StorageAgent"](config)

        # Phase 1: Crawl
        raw_schemes = []
        for source in sources:
            _crawl_state["current_portal"] = source.name
            try:
                batch = await crawler.crawl_portal(source)
                raw_schemes.extend(batch)
                _crawl_state["portals_crawled"] += 1
            except Exception as e:
                logger.error(f"Portal {source.name} failed: {e}")
                _crawl_state["portals_failed"] += 1

        _crawl_state["schemes_found"] = len(raw_schemes)

        # Phase 2: Dedup
        unique_schemes = dedup.deduplicate(raw_schemes)

        # Phase 3: Classify
        classified = []
        for scheme in unique_schemes:
            try:
                result = await classifier.classify(scheme)
                classified.append(result)
            except Exception:
                pass

        # Phase 4: Change detection
        new_count = 0
        updated_count = 0
        for scheme in classified:
            change = change_agent.detect_change(scheme)
            if change and change.name == "NEW":
                new_count += 1
            elif change and change.name == "UPDATED":
                updated_count += 1

        # Phase 5: Storage
        for scheme in classified:
            try:
                storage.store(scheme)
                db.upsert(scheme)
            except Exception:
                pass

        _crawl_state["schemes_new"] = new_count
        _crawl_state["schemes_updated"] = updated_count
        _crawl_state["status"] = "completed"
        _crawl_state["completed_at"] = datetime.now(timezone.utc).isoformat()
        _crawl_state["current_portal"] = None

    except Exception as e:
        logger.error(f"Discovery crawl failed: {e}")
        _crawl_state["status"] = "failed"
        _crawl_state["error"] = str(e)
        _crawl_state["completed_at"] = datetime.now(timezone.utc).isoformat()


@api_router.get("/discovery/status")
async def discovery_status():
    """Return current crawl status and stats."""
    return _crawl_state


@api_router.post("/discovery/crawl")
async def trigger_discovery_crawl(
    background_tasks: BackgroundTasks, req: dict = {}
):
    """Trigger a scheme discovery crawl (runs in background)."""
    if _crawl_state["status"] == "running":
        raise HTTPException(status_code=409, detail="Crawl already in progress")

    # Reset state
    _crawl_state.update({
        "status": "starting",
        "schemes_found": 0,
        "schemes_new": 0,
        "schemes_updated": 0,
        "portals_crawled": 0,
        "portals_failed": 0,
        "current_portal": None,
        "error": None,
        "last_run_report": None,
    })

    portal_names = req.get("portal_names")  # Optional filter
    background_tasks.add_task(_run_discovery_crawl, portal_names)

    return {"status": "started", "message": "Discovery crawl initiated"}


@api_router.get("/discovery/portals")
async def list_portals():
    """List all configured portal sources with health status."""
    mods = _get_v3_modules()
    if not mods:
        return {"portals": [], "error": "V3 modules not available"}

    sources = mods["PORTAL_SOURCES"]
    portals = []
    for s in sources:
        portals.append({
            "name": s.name,
            "base_url": s.base_url,
            "level": s.level.value if hasattr(s.level, "value") else str(s.level),
            "state": getattr(s, "state", None),
            "crawl_strategy": s.crawl_strategy,
            "priority": s.priority,
        })

    return {"portals": portals, "count": len(portals)}


@api_router.get("/discovery/portal-health")
async def portal_health():
    """Get portal health/circuit breaker status for all portals."""
    mods = _get_v3_modules()
    if not mods:
        return {"portals": [], "error": "V3 modules not available"}

    try:
        config = mods["AgentConfig"]()
        db_path = config.output_dir / "schemes.db"
        monitor = mods["PortalHealthMonitor"](db_path)
        records = monitor.get_all_health_records()

        health = []
        for r in records:
            health.append({
                "portal_name": r.portal_name,
                "domain": r.domain,
                "circuit_state": r.circuit_state.value,
                "consecutive_failures": r.consecutive_failures,
                "total_requests": r.total_requests,
                "total_successes": r.total_successes,
                "total_failures": r.total_failures,
                "avg_response_time_ms": r.avg_response_time_ms,
                "last_success_at": r.last_success_at,
                "last_failure_at": r.last_failure_at,
                "last_failure_reason": r.last_failure_reason,
                "schemes_extracted": r.schemes_extracted,
            })

        return {"portals": health, "count": len(health)}
    except Exception as e:
        return {"portals": [], "error": str(e)}


@api_router.get("/discovery/stats")
async def discovery_stats():
    """Get aggregated scheme discovery statistics from V3 database."""
    mods = _get_v3_modules()
    if not mods:
        return {"error": "V3 modules not available"}

    try:
        config = mods["AgentConfig"]()
        db = mods["SchemeDatabase"](config.output_dir / "schemes.db")

        total = db.get_scheme_count()
        by_sector = db.get_count_by_field("sector")
        by_level = db.get_count_by_field("level")
        by_status = db.get_count_by_field("scheme_status")
        recent_runs = db.get_recent_runs(limit=5)

        return {
            "total_schemes": total,
            "by_sector": by_sector,
            "by_level": by_level,
            "by_status": by_status,
            "recent_runs": recent_runs,
        }
    except Exception as e:
        return {"total_schemes": 0, "error": str(e)}
