"""V2.0 API routes — real form templates, smart profiler, filled PDF generation."""
import json
import logging
import time as _time
from datetime import datetime, timezone
from fastapi import HTTPException
from database import prisma
from config import PDF_DIR, AGNOST_WRITE_KEY
from routes import api_router

logger = logging.getLogger(__name__)


@api_router.get("/v2/schemes")
async def get_all_schemes_v2():
    """Return all 4 real schemes with metadata."""
    schemes = await prisma.scheme.find_many()
    result = []
    for s in schemes:
        result.append({
            "id": s.id, "name": s.name, "nameHindi": s.nameHindi,
            "category": s.category, "description": s.description,
            "descriptionHindi": s.descriptionHindi,
            "officialWebsite": s.officialWebsite,
            "eligibilityCriteriaText": s.eligibilityCriteriaText,
        })
    return {"schemes": result, "count": len(result)}


@api_router.get("/v2/form-template/{scheme_name}")
async def get_form_template(scheme_name: str):
    """Return the full form template with all extracted fields for a scheme."""
    ft = await prisma.formtemplate.find_first(where={"schemeName": scheme_name})
    if not ft:
        raise HTTPException(status_code=404, detail=f"Form template not found for: {scheme_name}")
    fields = ft.extractedFields if isinstance(ft.extractedFields, list) else json.loads(ft.extractedFields) if isinstance(ft.extractedFields, str) else []
    sections = ft.sections if isinstance(ft.sections, list) else json.loads(ft.sections) if isinstance(ft.sections, str) else []
    eligibility = ft.eligibilityCriteria if isinstance(ft.eligibilityCriteria, dict) else json.loads(ft.eligibilityCriteria) if isinstance(ft.eligibilityCriteria, str) else {}
    return {
        "id": ft.id, "schemeName": ft.schemeName, "schemeNameHindi": ft.schemeNameHindi,
        "officialPdfUrl": ft.officialPdfUrl, "officialWebsite": ft.officialWebsite,
        "description": ft.description, "descriptionHindi": ft.descriptionHindi,
        "category": ft.category, "totalFields": ft.totalFields,
        "sections": sections, "eligibilityCriteria": eligibility,
        "extractedFields": fields,
    }


@api_router.get("/v2/form-templates")
async def get_all_form_templates():
    """Return summary of all form templates."""
    templates = await prisma.formtemplate.find_many()
    result = []
    for ft in templates:
        result.append({
            "id": ft.id, "schemeName": ft.schemeName,
            "schemeNameHindi": ft.schemeNameHindi, "category": ft.category,
            "totalFields": ft.totalFields, "description": ft.description,
            "descriptionHindi": ft.descriptionHindi,
        })
    return {"templates": result, "count": len(result)}


@api_router.get("/v2/user-profile/{user_id}")
async def get_user_full_profile(user_id: str):
    """Return persistent full profile for a user."""
    try:
        user = await prisma.user.find_unique(where={"id": user_id})
    except Exception:
        raise HTTPException(status_code=404, detail="User not found")
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    full_profile = {}
    if user.fullProfile:
        full_profile = user.fullProfile if isinstance(user.fullProfile, dict) else json.loads(user.fullProfile) if isinstance(user.fullProfile, str) else {}
    return {
        "user_id": user.id, "phone": user.phone, "fullProfile": full_profile,
        "profileLastUpdated": user.profileLastUpdated.isoformat() if user.profileLastUpdated else None,
        "schemeHistory": user.schemeHistory if isinstance(user.schemeHistory, list) else json.loads(user.schemeHistory) if isinstance(user.schemeHistory, str) and user.schemeHistory else [],
    }


@api_router.post("/v2/user-profile/{user_id}")
async def update_user_full_profile(user_id: str, req: dict = {}):
    """Update persistent full profile with new field values. Merges, never overwrites."""
    fields = req.get("fields", {})
    if not fields:
        raise HTTPException(status_code=400, detail="No fields provided")
    try:
        user = await prisma.user.find_unique(where={"id": user_id})
    except Exception:
        raise HTTPException(status_code=404, detail="User not found")
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    existing = {}
    if user.fullProfile:
        existing = user.fullProfile if isinstance(user.fullProfile, dict) else json.loads(user.fullProfile) if isinstance(user.fullProfile, str) else {}
    existing.update(fields)
    from prisma import Json
    await prisma.user.update(where={"id": user_id}, data={
        "fullProfile": Json(existing),
        "profileLastUpdated": datetime.now(timezone.utc),
    })
    return {"success": True, "fullProfile": existing, "fieldsUpdated": list(fields.keys())}


@api_router.post("/v2/smart-profiler")
async def smart_profiler(req: dict = {}):
    """Intelligent profiler: given selected schemes, return which fields are needed,
    which are already filled, and the next question to ask."""
    user_id = req.get("user_id", "")
    scheme_names = req.get("scheme_names", [])
    if not user_id or not scheme_names:
        raise HTTPException(status_code=400, detail="user_id and scheme_names required")

    user = await prisma.user.find_unique(where={"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    full_profile = {}
    if user.fullProfile:
        full_profile = user.fullProfile if isinstance(user.fullProfile, dict) else json.loads(user.fullProfile) if isinstance(user.fullProfile, str) else {}

    all_fields = []
    seen_keys = set()
    for sname in scheme_names:
        ft = await prisma.formtemplate.find_first(where={"schemeName": sname})
        if not ft:
            continue
        fields = ft.extractedFields if isinstance(ft.extractedFields, list) else json.loads(ft.extractedFields) if isinstance(ft.extractedFields, str) else []
        for f in fields:
            pk = f.get("profileKey", f.get("fieldName", ""))
            if pk not in seen_keys:
                seen_keys.add(pk)
                all_fields.append(f)

    filled = []
    missing = []
    for f in all_fields:
        pk = f.get("profileKey", f.get("fieldName", ""))
        if pk in full_profile and full_profile[pk]:
            filled.append({**f, "currentValue": full_profile[pk]})
        else:
            if f.get("required", False):
                missing.append(f)

    next_question = None
    if missing:
        nf = missing[0]
        label_hi = nf.get("labelHindi", "")
        label_en = nf.get("labelEnglish", "")
        q_text = f"{label_hi}"
        if label_en:
            q_text += f" ({label_en})"
        if nf.get("type") == "select" and nf.get("options"):
            q_text += f"\nOptions: {', '.join(nf['options'])}"
        next_question = {
            "field": nf,
            "questionHindi": f"कृपया बताएं: {label_hi}",
            "questionEnglish": f"Please provide: {label_en}",
            "questionText": q_text,
            "profileKey": nf.get("profileKey", nf.get("fieldName", "")),
        }

    return {
        "totalFields": len(all_fields), "filledCount": len(filled),
        "missingCount": len(missing),
        "progress": round(len(filled) / max(len(all_fields), 1) * 100, 1),
        "filled": filled, "missing": missing,
        "nextQuestion": next_question, "allComplete": len(missing) == 0,
    }


@api_router.post("/v2/generate-filled-forms")
async def generate_real_filled_forms(req: dict = {}):
    """Generate pre-filled PDFs for selected schemes."""
    import uuid
    from pdf_generator import generate_real_filled_form_pdf
    from pdf_filler import fill_pdf_form
    from prisma import Json

    user_id = req.get("user_id", "")
    scheme_names = req.get("scheme_names", [])
    if not user_id or not scheme_names:
        raise HTTPException(status_code=400, detail="user_id and scheme_names required")

    user = await prisma.user.find_unique(where={"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    full_profile = {}
    if user.fullProfile:
        full_profile = user.fullProfile if isinstance(user.fullProfile, dict) else json.loads(user.fullProfile) if isinstance(user.fullProfile, str) else {}
    if user.profile:
        basic = user.profile if isinstance(user.profile, dict) else json.loads(user.profile) if isinstance(user.profile, str) else {}
        for k, v in basic.items():
            if k not in full_profile or not full_profile[k]:
                full_profile[k] = v

    t0 = _time.time()
    pdf_urls = []
    for sname in scheme_names:
        ft = await prisma.formtemplate.find_first(where={"schemeName": sname})
        if not ft:
            continue
        fields = ft.extractedFields if isinstance(ft.extractedFields, list) else json.loads(ft.extractedFields) if isinstance(ft.extractedFields, str) else []
        sections = ft.sections if isinstance(ft.sections, list) else json.loads(ft.sections) if isinstance(ft.sections, str) else []

        pid = str(uuid.uuid4())
        out_path = str(PDF_DIR / f"{pid}.pdf")
        fill_method = "generated"

        original_pdf_url = ft.officialPdfUrl or ""
        source_pdf_path = ""
        if original_pdf_url.startswith("/api/pdf/"):
            local_id = original_pdf_url.replace("/api/pdf/", "").strip("/")
            candidate = PDF_DIR / f"{local_id}.pdf"
            if candidate.exists():
                source_pdf_path = str(candidate)

        if source_pdf_path:
            fill_result = fill_pdf_form(
                source_pdf_path=source_pdf_path, output_path=out_path,
                field_values=full_profile, form_fields=fields,
            )
            if fill_result.get("success"):
                fill_method = fill_result.get("method", "filled")
                logger.info(f"PDF filled via {fill_method} for '{sname}': {fill_result.get('filled_count', 0)} fields")

        if fill_method == "generated":
            is_draft = not bool(original_pdf_url)
            generate_real_filled_form_pdf(
                filled_fields=full_profile, scheme_name=sname,
                scheme_name_hindi=ft.schemeNameHindi or "",
                sections=sections, form_fields=fields,
                output_path=out_path, is_draft=is_draft,
            )

        pdf_urls.append({
            "pdf_url": f"/api/pdf/{pid}", "scheme_name": sname,
            "scheme_name_hindi": ft.schemeNameHindi or "",
            "fill_method": fill_method,
        })

        scheme = await prisma.scheme.find_first(where={"name": sname})
        if scheme:
            await prisma.application.create(data={
                "userId": user_id, "schemeId": scheme.id,
                "status": "form_generated", "formUrl": f"/api/pdf/{pid}",
                "filledFields": Json(full_profile),
            })

    if AGNOST_WRITE_KEY:
        try:
            import agnost
            agnost.track(user_id=user_id, agent_name="nagarik_tool",
                         input="generate_real_filled_forms", output=str(len(pdf_urls)),
                         properties={"tool": "v2_pdf_gen", "schemes": scheme_names, "pdf_count": len(pdf_urls)},
                         success=True, latency=int((_time.time() - t0) * 1000))
        except Exception:
            pass

    return {"pdf_urls": pdf_urls, "count": len(pdf_urls), "profile_fields_used": len(full_profile)}


@api_router.post("/v2/extract-form-fields")
async def api_extract_form_fields(req: dict = {}):
    """Extract form fields from a PDF URL using Claude Sonnet 4.5."""
    from form_extractor import extract_form_fields

    pdf_url = req.get("pdf_url", "")
    scheme_hint = req.get("scheme_hint", "")
    if not pdf_url:
        raise HTTPException(status_code=400, detail="pdf_url is required")

    t0 = _time.time()
    result = await extract_form_fields(pdf_url=pdf_url, scheme_hint=scheme_hint)

    if "error" in result:
        if AGNOST_WRITE_KEY:
            try:
                import agnost
                agnost.track(user_id="system", agent_name="nagarik_tool",
                             input="extract_form_fields", output=result["error"],
                             properties={"tool": "form_extractor", "pdf_url": pdf_url},
                             success=False, latency=int((_time.time() - t0) * 1000))
            except Exception:
                pass
        raise HTTPException(status_code=422, detail=result["error"])

    if result.get("schemeName") and req.get("save_to_db", True):
        from prisma import Json
        existing = await prisma.formtemplate.find_first(where={"schemeName": result["schemeName"]})
        data = {
            "schemeName": result["schemeName"],
            "schemeNameHindi": result.get("schemeNameHindi", ""),
            "officialPdfUrl": pdf_url,
            "category": result.get("category", "general"),
            "totalFields": result.get("totalFields", len(result.get("extractedFields", []))),
            "extractedFields": Json(result.get("extractedFields", [])),
            "sections": Json(result.get("sections", [])),
        }
        if existing:
            await prisma.formtemplate.update(where={"id": existing.id}, data=data)
        else:
            await prisma.formtemplate.create(data=data)

    if AGNOST_WRITE_KEY:
        try:
            import agnost
            agnost.track(user_id="system", agent_name="nagarik_tool",
                         input="extract_form_fields", output=str(result.get("totalFields", 0)),
                         properties={"tool": "form_extractor", "scheme": result.get("schemeName", ""),
                                     "fields": result.get("totalFields", 0)},
                         success=True, latency=int((_time.time() - t0) * 1000))
        except Exception:
            pass

    return result
