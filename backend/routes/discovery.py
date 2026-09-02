"""Scheme Discovery routes — integrates the V3 crawler pipeline into the web app."""
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from fastapi import HTTPException, BackgroundTasks
from routes import api_router
from services import v3_bridge

logger = logging.getLogger(__name__)

# In-memory crawl state (lightweight — single instance app)
_crawl_state = {
    "status": "idle",  # idle | starting | running | completed | failed
    "started_at": None,
    "completed_at": None,
    "schemes_found": 0,
    "schemes_new": 0,
    "schemes_updated": 0,
    "portals_crawled": 0,
    "portals_failed": 0,
    "current_portal": None,
    "error": None,
}


async def _run_discovery_crawl(portal_names: list[str] | None = None):
    """Background task: run the V3 discovery pipeline.

    Pipeline: crawl → dedup → classify → change-detect (persists to DB) → store.
    """
    global _crawl_state
    _crawl_state["status"] = "running"
    _crawl_state["started_at"] = datetime.now(timezone.utc).isoformat()
    _crawl_state["error"] = None

    mods = v3_bridge.get_v3_modules()
    if not mods:
        _crawl_state["status"] = "failed"
        _crawl_state["error"] = "V3 crawler dependencies not installed"
        return

    try:
        from src.crawlers.discovery_crawler import DiscoveryCrawler
        from src.classifiers.classify_agent import ClassificationAgent
        from src.agents.dedup_agent import DeduplicationAgent
        from src.agents.change_agent import ChangeDetectionAgent
        from src.agents.models import ChangeType
        from src.storage.storage_agent import StorageAgent

        config = mods["AgentConfig"]()
        sources = list(mods["PORTAL_SOURCES"])
        if portal_names:
            sources = [s for s in sources if s.name in portal_names]

        db = await asyncio.to_thread(mods["SchemeDatabase"], config.db_path)
        crawler = DiscoveryCrawler(config)
        classifier = ClassificationAgent(config)
        dedup = DeduplicationAgent(config)
        change_agent = ChangeDetectionAgent(db)
        storage = StorageAgent(config)
        run_id = f"web_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

        # Phase 1: Crawl each portal (per-source so we can report progress)
        raw_schemes = []
        for source in sources:
            _crawl_state["current_portal"] = source.name
            try:
                batch = await crawler._crawl_source_safe(source)
                raw_schemes.extend(batch)
                _crawl_state["portals_crawled"] += 1
            except Exception as e:
                logger.error(f"Portal {source.name} failed: {e}")
                _crawl_state["portals_failed"] += 1
            _crawl_state["schemes_found"] = len(raw_schemes)

        # Phase 2: Dedup
        unique_schemes = await asyncio.to_thread(dedup.deduplicate_batch, raw_schemes)

        # Phase 3: Classify (LLM with rule-based fallback)
        classified = await classifier.classify_batch(unique_schemes)

        # Phase 4: Change detection — upserts each scheme into the DB and
        # annotates change_type on each ClassifiedScheme
        annotated = await asyncio.to_thread(
            change_agent.process_classified_batch, classified, run_id
        )
        new_count = sum(1 for s in annotated if s.change_type == ChangeType.NEW)
        updated_count = sum(1 for s in annotated if s.change_type == ChangeType.UPDATED)

        # Phase 5: Folder storage (metadata.json, markdown, PDFs)
        try:
            await storage.store_batch(annotated)
        except Exception as e:
            logger.warning(f"Folder storage partially failed: {e}")

        _crawl_state["schemes_new"] = new_count
        _crawl_state["schemes_updated"] = updated_count
        _crawl_state["status"] = "completed"
        _crawl_state["completed_at"] = datetime.now(timezone.utc).isoformat()
        _crawl_state["current_portal"] = None

    except Exception as e:
        logger.error(f"Discovery crawl failed: {e}", exc_info=True)
        _crawl_state["status"] = "failed"
        _crawl_state["error"] = str(e)
        _crawl_state["completed_at"] = datetime.now(timezone.utc).isoformat()


@api_router.get("/discovery/status")
async def discovery_status():
    """Return current crawl status and stats."""
    return _crawl_state


@api_router.post("/discovery/crawl")
async def trigger_discovery_crawl(
    background_tasks: BackgroundTasks, req: dict | None = None
):
    """Trigger a scheme discovery crawl (runs in background)."""
    if _crawl_state["status"] == "running":
        raise HTTPException(status_code=409, detail="Crawl already in progress")
    if not v3_bridge.get_v3_modules():
        raise HTTPException(status_code=503, detail="V3 crawler not available")

    _crawl_state.update({
        "status": "starting",
        "schemes_found": 0,
        "schemes_new": 0,
        "schemes_updated": 0,
        "portals_crawled": 0,
        "portals_failed": 0,
        "current_portal": None,
        "error": None,
    })

    portal_names = (req or {}).get("portal_names")
    background_tasks.add_task(_run_discovery_crawl, portal_names)

    return {"status": "started", "message": "Discovery crawl initiated"}


@api_router.get("/discovery/portals")
async def list_portals():
    """List all configured portal sources."""
    mods = v3_bridge.get_v3_modules()
    if not mods:
        return {"portals": [], "count": 0, "error": "V3 modules not available"}

    portals = []
    for s in mods["PORTAL_SOURCES"]:
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
    def _work():
        monitor = v3_bridge.get_health_monitor()
        if not monitor:
            return None
        return monitor.get_health_summary()

    try:
        summary = await asyncio.to_thread(_work)
        if summary is None:
            return {"portals": [], "count": 0, "error": "V3 modules not available"}

        portals = []
        for r in summary.get("portals", []):
            portals.append({
                "portal_name": r.get("portal_name"),
                "domain": r.get("domain"),
                "circuit_state": r.get("circuit_state"),
                "consecutive_failures": r.get("consecutive_failures", 0),
                "total_requests": r.get("total_requests", 0),
                "total_successes": r.get("total_successes", 0),
                "total_failures": r.get("total_failures", 0),
                "avg_response_time_ms": r.get("avg_response_time_ms", 0) or 0,
                "last_success_at": r.get("last_success_at"),
                "last_failure_at": r.get("last_failure_at"),
                "last_failure_reason": r.get("last_failure_reason"),
                "schemes_extracted": r.get("schemes_extracted", 0),
            })

        return {
            "portals": portals,
            "count": summary.get("total_portals", len(portals)),
            "healthy": summary.get("healthy", 0),
            "failing": summary.get("failing", 0),
            "selector_issues": summary.get("selector_issues", 0),
        }
    except Exception as e:
        logger.error(f"Portal health failed: {e}")
        return {"portals": [], "count": 0, "error": str(e)}


@api_router.post("/discovery/portal-health/{portal_name}/reset")
async def reset_portal_circuit(portal_name: str):
    """Reset a portal's circuit breaker after fixing the underlying issue."""
    def _work():
        monitor = v3_bridge.get_health_monitor()
        if not monitor:
            return False
        monitor.reset_portal(portal_name)
        return True

    ok = await asyncio.to_thread(_work)
    if not ok:
        raise HTTPException(status_code=503, detail="V3 modules not available")
    return {"success": True, "portal": portal_name}


@api_router.get("/discovery/stats")
async def discovery_stats():
    """Get aggregated scheme discovery statistics from the V3 database."""
    def _work():
        db = v3_bridge.get_scheme_db()
        if not db:
            return None
        stats = db.get_stats()
        runs = db.get_run_history(limit=5)
        return stats, runs

    try:
        result = await asyncio.to_thread(_work)
        if result is None:
            return {"total_schemes": 0, "error": "V3 modules not available"}
        stats, runs = result
        return {
            "total_schemes": stats.get("total", 0),
            "active_schemes": stats.get("active", 0),
            "by_sector": stats.get("by_sector", {}),
            "by_level": stats.get("by_level", {}),
            "by_status": stats.get("by_status", {}),
            "by_type": stats.get("by_type", {}),
            "by_state": stats.get("by_state", {}),
            "recent_runs": runs,
        }
    except Exception as e:
        logger.error(f"Discovery stats failed: {e}")
        return {"total_schemes": 0, "error": str(e)}


@api_router.get("/discovery/schemes")
async def list_discovered_schemes(
    sector: str = "",
    level: str = "",
    state: str = "",
    status: str = "",
    search: str = "",
    limit: int = 50,
    offset: int = 0,
):
    """List schemes discovered by the V3 crawler, with filtering."""
    def _work():
        db = v3_bridge.get_scheme_db()
        if not db:
            return None
        return db.get_all_schemes()

    try:
        schemes = await asyncio.to_thread(_work)
        if schemes is None:
            return {"schemes": [], "count": 0, "error": "V3 modules not available"}

        # Python-side filtering (V3 DB has no combined-filter query)
        def _match(s):
            if sector and s.get("sector") != sector:
                return False
            if level and s.get("level") != level:
                return False
            if state and s.get("state") != state:
                return False
            if status and s.get("scheme_status") != status:
                return False
            if search:
                q = search.lower()
                hay = f"{s.get('clean_name', '')} {s.get('summary', '')} {s.get('sector', '')}".lower()
                if q not in hay:
                    return False
            return True

        filtered = [s for s in schemes if _match(s)]
        total = len(filtered)
        limit = max(1, min(limit, 200))
        offset = max(0, offset)
        page = filtered[offset:offset + limit]

        results = [{
            "scheme_id": s.get("scheme_id"),
            "name": s.get("clean_name"),
            "level": s.get("level"),
            "state": s.get("state"),
            "sector": s.get("sector"),
            "scheme_type": s.get("scheme_type"),
            "status": s.get("scheme_status"),
            "summary": s.get("summary"),
            "eligibility": s.get("eligibility"),
            "benefit_amount": s.get("benefit_amount"),
            "application_deadline": s.get("application_deadline"),
            "official_website": s.get("official_website"),
            "source_portal": s.get("source_portal"),
            "detail_url": s.get("detail_url"),
        } for s in page]

        return {"schemes": results, "count": total, "limit": limit, "offset": offset}
    except Exception as e:
        logger.error(f"List discovered schemes failed: {e}")
        return {"schemes": [], "count": 0, "error": str(e)}
