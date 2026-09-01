"""Real government form routes — catalog, live extraction, and link health."""
import logging

from fastapi import HTTPException, BackgroundTasks, Request

from routes import api_router
from config import ADMIN_SECRET
from data.gov_forms import get_catalog, get_by_name
from services import form_seeder

logger = logging.getLogger(__name__)

# Progress for the most recent live refresh, polled by the admin UI.
_refresh_state = {
    "status": "idle",   # idle | running | completed | failed
    "scheme": None,
    "processed": 0,
    "total": 0,
    "results": [],
    "error": None,
}


def _require_admin(request: Request) -> None:
    """Gate destructive/expensive operations behind the X-Admin-Secret header."""
    supplied = request.headers.get("X-Admin-Secret", "")
    if not ADMIN_SECRET or supplied != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Admin secret required")


@api_router.get("/forms/catalog")
async def form_catalog():
    """List the curated real-government-form catalog.

    Serves from bundled data, so it works with no database, network, or LLM key.
    """
    entries = []
    for e in get_catalog():
        entries.append({
            "schemeName": e["schemeName"],
            "schemeNameHindi": e.get("schemeNameHindi", ""),
            "category": e.get("category", "general"),
            "description": e.get("description", ""),
            "descriptionHindi": e.get("descriptionHindi", ""),
            "officialWebsite": e.get("officialWebsite", ""),
            "officialPdfUrl": e.get("official_pdf_url", ""),
            # Scheme literature (booklet/guidelines) where no fillable form is
            # published — useful to link, but never used for field extraction.
            "referencePdfUrl": e.get("reference_pdf_url", ""),
            "hasLivePdf": bool(e.get("official_pdf_url")),
            "isScanned": e.get("is_scanned", False),
            "sourceVerified": e.get("source_verified", ""),
            "totalFields": e.get("totalFields", 0),
            "sections": e.get("sections", []),
            "eligibility": e.get("eligibilityCriteria", {}),
        })
    return {"forms": entries, "count": len(entries)}


@api_router.get("/forms/catalog/{scheme_name}")
async def form_catalog_detail(scheme_name: str):
    """Full field definitions for one catalog scheme."""
    entry = get_by_name(scheme_name)
    if not entry:
        raise HTTPException(status_code=404, detail=f"'{scheme_name}' not in catalog")
    return entry


@api_router.post("/forms/seed")
async def seed_catalog(request: Request, req: dict | None = None):
    """Seed FormTemplate + Scheme tables from the curated catalog."""
    req = req or {}
    overwrite = bool(req.get("overwrite", False))
    if overwrite:
        # Overwriting can discard live-refreshed or user-uploaded templates.
        _require_admin(request)
    try:
        return await form_seeder.seed_from_catalog(overwrite=overwrite)
    except Exception as e:
        logger.error(f"Catalog seed failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/forms/link-health")
async def form_link_health():
    """Check which catalog government PDF URLs are still live.

    Government links rot frequently; this makes breakage visible instead of
    letting live extraction silently fall back to curated data forever.
    """
    try:
        return await form_seeder.verify_catalog_urls()
    except Exception as e:
        logger.error(f"Link health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/forms/refresh-status")
async def refresh_status():
    """Progress of the most recent live refresh run."""
    return _refresh_state


async def _run_refresh(scheme_names: list[str]) -> None:
    """Background task: re-extract the given schemes from their live PDFs."""
    _refresh_state.update({
        "status": "running", "processed": 0, "total": len(scheme_names),
        "results": [], "error": None, "scheme": None,
    })
    try:
        for name in scheme_names:
            _refresh_state["scheme"] = name
            try:
                result = await form_seeder.refresh_from_live_pdf(name)
            except Exception as e:
                logger.error(f"Refresh of {name} failed: {e}")
                result = {"success": False, "scheme": name, "error": str(e)}
            _refresh_state["results"].append(result)
            _refresh_state["processed"] += 1
        _refresh_state["status"] = "completed"
        _refresh_state["scheme"] = None
    except Exception as e:
        logger.error(f"Refresh run failed: {e}")
        _refresh_state["status"] = "failed"
        _refresh_state["error"] = str(e)


@api_router.post("/forms/refresh")
async def refresh_forms(
    request: Request,
    background_tasks: BackgroundTasks,
    req: dict | None = None,
):
    """Re-extract form fields from live government PDFs (admin, backgrounded).

    Body: {"schemes": ["PM-KISAN Samman Nidhi", ...]} — omit to refresh every
    catalog scheme that publishes a PDF.
    """
    req = req or {}
    _require_admin(request)

    if _refresh_state["status"] == "running":
        raise HTTPException(status_code=409, detail="A refresh is already running")

    requested = req.get("schemes")
    if requested:
        names = []
        for n in requested:
            entry = get_by_name(n)
            if not entry:
                raise HTTPException(status_code=404, detail=f"'{n}' not in catalog")
            names.append(entry["schemeName"])
    else:
        names = [e["schemeName"] for e in get_catalog() if e.get("official_pdf_url")]

    if not names:
        raise HTTPException(status_code=400, detail="No catalog schemes have a PDF URL")

    background_tasks.add_task(_run_refresh, names)
    return {"status": "started", "schemes": names, "count": len(names)}


@api_router.post("/forms/extract-live")
async def extract_live(req: dict):
    """Extract form fields from any government PDF URL, on demand.

    Body: {"pdf_url": "...", "scheme_hint": "...", "save_to_db": false}

    This is the real-time path: it downloads the PDF, OCRs it if scanned, and
    returns typed fields. Works without an LLM key via the rule-based extractor.
    """
    pdf_url = (req.get("pdf_url") or "").strip()
    if not pdf_url:
        raise HTTPException(status_code=400, detail="pdf_url is required")
    if not pdf_url.lower().startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="pdf_url must be an http(s) URL")

    from form_extractor import extract_form_fields

    try:
        result = await extract_form_fields(
            pdf_url=pdf_url, scheme_hint=req.get("scheme_hint", "")
        )
    except Exception as e:
        logger.error(f"Live extraction failed for {pdf_url}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    if result.get("error"):
        raise HTTPException(status_code=422, detail=result["error"])

    if req.get("save_to_db") and result.get("schemeName"):
        try:
            data = form_seeder._template_data(result, pdf_url=pdf_url)
            result["_saved"] = await form_seeder._upsert_template(data)
        except Exception as e:
            logger.error(f"Saving extracted template failed: {e}")
            result["_save_error"] = str(e)

    return result
