"""Seed and refresh real government form templates.

Two data paths feed FormTemplate:

* **Catalog seed** (default, always safe) — writes the curated, hand-verified
  field definitions from `data/gov_forms.py`. Needs no network and no LLM key,
  so a fresh deployment is immediately usable.
* **Live refresh** (opt-in) — downloads the scheme's real government PDF and
  re-extracts its fields (OCR + LLM or rule-based). Used to pick up changes when
  a ministry republishes a form.

Live refresh never destroys a good template: if extraction yields fewer fields
than the curated baseline, the curated version is kept. Government PDFs go
missing or get replaced by scanned-at-90-DPI versions often enough that trusting
a live extraction unconditionally would degrade the app.
"""
from __future__ import annotations

import logging

from data.gov_forms import get_catalog, get_by_name

# NOTE: the Prisma client is imported lazily inside the functions that need it.
# Link verification and live extraction are useful as standalone smoke tests on
# a machine with no database (and no generated Prisma client), so importing it
# at module scope would break those for no benefit.

logger = logging.getLogger(__name__)


def _template_data(entry: dict, pdf_url: str | None = None) -> dict:
    """Build the Prisma FormTemplate payload from a catalog/extraction dict."""
    from prisma import Json

    fields = entry.get("extractedFields", []) or []
    return {
        "schemeName": entry["schemeName"],
        "schemeNameHindi": entry.get("schemeNameHindi", ""),
        "officialPdfUrl": pdf_url if pdf_url is not None else entry.get("official_pdf_url", ""),
        "officialWebsite": entry.get("officialWebsite", ""),
        "description": entry.get("description", ""),
        "descriptionHindi": entry.get("descriptionHindi", ""),
        "category": entry.get("category", "general"),
        "totalFields": len(fields),
        "extractedFields": Json(fields),
        "sections": Json(entry.get("sections", []) or []),
        "eligibilityCriteria": Json(entry.get("eligibilityCriteria", {}) or {}),
    }


async def _upsert_template(data: dict) -> str:
    """Insert or update a FormTemplate by schemeName. Returns 'created'/'updated'."""
    from database import prisma

    existing = await prisma.formtemplate.find_first(
        where={"schemeName": data["schemeName"]}
    )
    if existing:
        await prisma.formtemplate.update(where={"id": existing.id}, data=data)
        return "updated"
    await prisma.formtemplate.create(data=data)
    return "created"


async def _upsert_scheme(entry: dict) -> None:
    """Mirror the catalog entry into the Scheme table used by search/eligibility."""
    from database import prisma

    elig = entry.get("eligibilityCriteria", {}) or {}
    data = {
        "name": entry["schemeName"],
        "nameHindi": entry.get("schemeNameHindi", ""),
        "category": entry.get("category", "general"),
        "eligibilityCriteriaText": elig.get("summary", "") or entry.get("description", ""),
        "description": entry.get("description", ""),
        "descriptionHindi": entry.get("descriptionHindi", ""),
        "officialWebsite": entry.get("officialWebsite", ""),
        "pdfUrl": entry.get("official_pdf_url", "") or entry.get("officialWebsite", ""),
    }
    existing = await prisma.scheme.find_first(where={"name": data["name"]})
    if existing:
        await prisma.scheme.update(where={"id": existing.id}, data=data)
    else:
        await prisma.scheme.create(data=data)


async def seed_from_catalog(overwrite: bool = False) -> dict:
    """Seed FormTemplate + Scheme from the curated catalog.

    With overwrite=False (default) existing templates are left untouched, so a
    live-refreshed or user-uploaded template is never clobbered on restart.
    """
    from database import prisma

    created = updated = skipped = 0
    errors: list[str] = []

    for entry in get_catalog():
        try:
            existing = await prisma.formtemplate.find_first(
                where={"schemeName": entry["schemeName"]}
            )
            if existing and not overwrite:
                skipped += 1
            else:
                action = await _upsert_template(entry)
                created += action == "created"
                updated += action == "updated"
            await _upsert_scheme(entry)
        except Exception as e:
            logger.error(f"Seeding {entry['schemeName']} failed: {e}")
            errors.append(f"{entry['schemeName']}: {e}")

    result = {
        "created": created, "updated": updated, "skipped": skipped,
        "total_catalog": len(get_catalog()), "errors": errors,
    }
    logger.info(
        "Catalog seed complete: %d created, %d updated, %d skipped",
        created, updated, skipped,
    )
    return result


async def refresh_from_live_pdf(scheme_name: str) -> dict:
    """Re-extract one scheme's fields from its live government PDF.

    Returns a report describing what happened, including whether the freshly
    extracted fields were accepted or the curated baseline was kept.
    """
    entry = get_by_name(scheme_name)
    if not entry:
        return {"success": False, "error": f"'{scheme_name}' is not in the form catalog"}

    pdf_url = entry.get("official_pdf_url")
    if not pdf_url:
        return {
            "success": False,
            "error": f"'{entry['schemeName']}' has no published PDF form URL; "
                     "using curated fields only",
            "scheme": entry["schemeName"],
        }

    from form_extractor import extract_form_fields

    extracted = await extract_form_fields(pdf_url=pdf_url, scheme_hint=entry["schemeName"])
    baseline = len(entry.get("extractedFields", []))

    if extracted.get("error"):
        return {
            "success": False, "scheme": entry["schemeName"], "pdf_url": pdf_url,
            "error": extracted["error"], "kept_curated": True,
            "curated_field_count": baseline,
        }

    live_fields = extracted.get("extractedFields", []) or []

    # Guard against regression: a live extraction that finds materially fewer
    # fields than the curated baseline is a worse form, not a newer one.
    if len(live_fields) < baseline:
        return {
            "success": True, "scheme": entry["schemeName"], "pdf_url": pdf_url,
            "kept_curated": True,
            "reason": f"live extraction found {len(live_fields)} fields vs "
                      f"{baseline} curated — keeping curated",
            "live_field_count": len(live_fields),
            "curated_field_count": baseline,
            "extraction_method": extracted.get("_extraction_method"),
        }

    merged = dict(entry)
    merged["extractedFields"] = live_fields
    if extracted.get("sections"):
        merged["sections"] = extracted["sections"]

    action = await _upsert_template(_template_data(merged, pdf_url=pdf_url))
    return {
        "success": True, "scheme": entry["schemeName"], "pdf_url": pdf_url,
        "kept_curated": False, "action": action,
        "live_field_count": len(live_fields),
        "curated_field_count": baseline,
        "extraction_method": extracted.get("_extraction_method"),
        "extraction_engine": extracted.get("_extraction_engine"),
    }


async def verify_catalog_urls() -> dict:
    """HEAD/GET every catalog PDF URL to report which government links still work.

    Government URLs rot constantly; this powers an admin health view so a broken
    link is visible rather than silently degrading extraction.
    """
    import httpx
    from form_extractor import _BROWSER_UA, PDF_MAGIC

    results = []
    headers = {"User-Agent": _BROWSER_UA, "Accept": "application/pdf,*/*"}

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(30.0, connect=10.0),
        follow_redirects=True, headers=headers,
    ) as client:
        for entry in get_catalog():
            url = entry.get("official_pdf_url")
            if not url:
                results.append({
                    "scheme": entry["schemeName"], "url": None,
                    "status": "no_url", "ok": False,
                })
                continue
            try:
                # Range request keeps this cheap — we only need the magic bytes.
                resp = await client.get(url, headers={**headers, "Range": "bytes=0-1023"})
                is_pdf = resp.content[:4].startswith(PDF_MAGIC)
                results.append({
                    "scheme": entry["schemeName"], "url": url,
                    "http_status": resp.status_code,
                    "is_pdf": is_pdf,
                    "ok": resp.status_code < 400 and is_pdf,
                    "status": "ok" if (resp.status_code < 400 and is_pdf) else "bad_response",
                })
            except Exception as e:
                results.append({
                    "scheme": entry["schemeName"], "url": url,
                    "status": "unreachable", "ok": False, "error": str(e),
                })

    healthy = sum(1 for r in results if r["ok"])
    return {
        "results": results,
        "healthy": healthy,
        "total": len(results),
        "with_url": sum(1 for r in results if r.get("url")),
    }
