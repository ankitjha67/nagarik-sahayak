"""V3 Bridge — single point of contact between the FastAPI app and the
GovScheme V3 crawler/exam pipeline (SQLite-backed, lives under /src).

All V3 SQLite calls are synchronous; callers must wrap them with
asyncio.to_thread() to avoid blocking the event loop. Helpers here that
end in `_sync` are blocking; the async wrappers do the thread hop.
"""
import asyncio
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Make `src.*` imports resolvable (project root is one level above backend/)
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

_modules_cache = None


def get_v3_modules():
    """Lazy-import V3 modules. Returns None if dependencies are missing."""
    global _modules_cache
    if _modules_cache is not None:
        return _modules_cache
    try:
        from src.config.settings import AgentConfig, PORTAL_SOURCES
        from src.storage.database import SchemeDatabase
        from src.exams.exam_database import ExamDatabase
        from src.resilience.portal_health import PortalHealthMonitor
        _modules_cache = {
            "AgentConfig": AgentConfig,
            "PORTAL_SOURCES": PORTAL_SOURCES,
            "SchemeDatabase": SchemeDatabase,
            "ExamDatabase": ExamDatabase,
            "PortalHealthMonitor": PortalHealthMonitor,
        }
        return _modules_cache
    except ImportError as e:
        logger.warning(f"V3 modules not available: {e}")
        return None


def get_config():
    """Return an AgentConfig instance, or None if V3 is unavailable."""
    mods = get_v3_modules()
    if not mods:
        return None
    return mods["AgentConfig"]()


def get_scheme_db():
    """Blocking: return a SchemeDatabase bound to the configured db_path."""
    mods = get_v3_modules()
    if not mods:
        return None
    config = mods["AgentConfig"]()
    return mods["SchemeDatabase"](config.db_path)


def get_exam_db():
    """Blocking: return an ExamDatabase bound to the configured exam_db_path."""
    mods = get_v3_modules()
    if not mods:
        return None
    config = mods["AgentConfig"]()
    return mods["ExamDatabase"](config.exam_db_path)


def get_health_monitor():
    """Blocking: return a PortalHealthMonitor on the scheme db."""
    mods = get_v3_modules()
    if not mods:
        return None
    config = mods["AgentConfig"]()
    return mods["PortalHealthMonitor"](config.db_path)


# ── Async wrappers (run blocking SQLite work in a thread) ──────────────

async def run_blocking(fn, *args, **kwargs):
    """Run a blocking callable in a worker thread."""
    return await asyncio.to_thread(fn, *args, **kwargs)


async def scheme_stats() -> dict:
    """Async: aggregated scheme stats from the V3 database."""
    def _work():
        db = get_scheme_db()
        if not db:
            return None
        return db.get_stats()
    return await asyncio.to_thread(_work)


async def exam_stats() -> dict:
    """Async: aggregated exam stats from the V3 exam database."""
    def _work():
        db = get_exam_db()
        if not db:
            return None
        return db.get_stats()
    return await asyncio.to_thread(_work)
