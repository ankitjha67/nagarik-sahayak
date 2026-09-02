"""PDF serving, generation, upload, and download routes."""
import re
import os
import uuid
import json
import logging
import time as _time
from fastapi import UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from database import prisma
from config import PDF_DIR, AGNOST_WRITE_KEY, validate_path_within, validate_pdf_content, AUDIO_DIR
from models import GeneratePDFRequest, FilledFormRequest
from services.eligibility import eligibility_matcher_sync
from services.profiler import generate_filled_form
from routes import api_router

logger = logging.getLogger(__name__)


@api_router.post("/generate-filled-form")
async def generate_filled_form_endpoint(req: FilledFormRequest):
    result = await generate_filled_form(req.user_id, req.scheme_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Form generation failed"))
    return result


@api_router.post("/generate-pdf")
async def generate_pdf_endpoint(req: GeneratePDFRequest):
    from pdf_generator import generate_eligibility_pdf
    profile = req.profile
    if req.user_id and not profile:
        user = await prisma.user.find_unique(where={"id": req.user_id})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        profile = json.loads(user.profile) if isinstance(user.profile, str) and user.profile else (user.profile or {})
    if not profile or not profile.get("name"):
        raise HTTPException(status_code=400, detail="Profile incomplete")
    t0 = _time.time()
    matcher = eligibility_matcher_sync(profile)
    results = matcher.get("results", [])
    if not results:
        raise HTTPException(status_code=400, detail="No eligibility results")
    pdf_id = str(uuid.uuid4())
    generate_eligibility_pdf(profile=profile, eligibility_results=results, output_path=str(PDF_DIR / f"{pdf_id}.pdf"))
    pdf_url = f"/api/pdf/{pdf_id}"
    if AGNOST_WRITE_KEY:
        try:
            import agnost
            agnost.track(user_id=req.user_id or "api", agent_name="nagarik_tool", input=str(profile),
                         output=pdf_url, properties={"tool": "generate_pdf", "pdf_id": pdf_id},
                         success=True, latency=int((_time.time() - t0) * 1000))
        except Exception:
            pass
    return {"success": True, "pdf_url": pdf_url, "pdf_id": pdf_id,
            "eligible_count": sum(1 for r in results if r["eligible"]),
            "total_schemes": len(results), "results": results}


@api_router.get("/pdf/{pdf_id}")
async def serve_pdf(pdf_id: str):
    safe_id = re.sub(r'[^a-zA-Z0-9\-]', '', pdf_id)
    pdf_path = PDF_DIR / f"{safe_id}.pdf"
    if not validate_path_within(pdf_path, PDF_DIR):
        raise HTTPException(status_code=400, detail="Invalid PDF ID")
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(path=str(pdf_path), media_type="application/pdf",
                        filename=f"Nagarik_Sahayak_Report_{safe_id[:8]}.pdf")


@api_router.get("/audio/{msg_id}")
async def serve_audio(msg_id: str):
    safe_id = re.sub(r'[^a-zA-Z0-9\-]', '', msg_id)
    audio_path = AUDIO_DIR / f"{safe_id}.webm"
    if not validate_path_within(audio_path, AUDIO_DIR):
        raise HTTPException(status_code=400, detail="Invalid audio ID")
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio not found")
    return FileResponse(path=str(audio_path), media_type="audio/webm")


@api_router.get("/download-all")
async def download_all_pdfs(user_id: str = "", count: int = 0):
    """Track multi-PDF download event via Agnost."""
    if AGNOST_WRITE_KEY:
        try:
            import agnost
            agnost.track(user_id=user_id or "api", agent_name="nagarik_tool",
                         input="multi_pdf_download_success", output=str(count),
                         properties={"tool": "multi_pdf_download", "scheme_count": count, "user_id": user_id},
                         success=True, latency=0)
        except Exception:
            pass
    return {"tracked": True, "count": count}


@api_router.get("/download-all-zip")
async def download_all_zip(pdf_ids: str = "", user_id: str = ""):
    """Generate a zip bundle of PDFs."""
    import zipfile as zf
    if not pdf_ids:
        raise HTTPException(status_code=400, detail="No pdf_ids provided")
    ids = [x.strip() for x in pdf_ids.split(",") if x.strip()]
    zip_id = str(uuid.uuid4())
    zip_path = PDF_DIR / f"{zip_id}.zip"
    count = 0
    with zf.ZipFile(zip_path, "w", zf.ZIP_DEFLATED) as z:
        for pdf_id in ids:
            clean_id = re.sub(r'[^a-zA-Z0-9\-]', '', pdf_id.replace(".pdf", ""))
            pdf_file = PDF_DIR / f"{clean_id}.pdf"
            if not validate_path_within(pdf_file, PDF_DIR):
                continue
            if pdf_file.exists():
                z.write(pdf_file, f"Form_{count + 1}.pdf")
                count += 1
    if count == 0:
        raise HTTPException(status_code=404, detail="No PDFs found for given IDs")
    if AGNOST_WRITE_KEY:
        try:
            import agnost
            agnost.track(user_id=user_id or "api", agent_name="nagarik_tool",
                         input="download_all_zip", output=str(count),
                         properties={"tool": "multi_pdf_download", "scheme_count": count, "format": "zip"},
                         success=True, latency=0)
        except Exception:
            pass
    return FileResponse(path=str(zip_path), media_type="application/zip",
                        filename="Nagarik_Sahayak_Forms.zip")


UPLOADS_DIR = PDF_DIR


@api_router.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...), user_id: str = Form("")):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")
    if file.content_type and file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDF files are accepted.")
    file_bytes = await file.read()
    if len(file_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")
    if not validate_pdf_content(file_bytes):
        raise HTTPException(status_code=400, detail="Invalid PDF file content")
    pdf_id = str(uuid.uuid4())
    safe_name = re.sub(r'[^a-zA-Z0-9._\-]', '_', file.filename)
    pdf_path = UPLOADS_DIR / f"{pdf_id}.pdf"
    with open(pdf_path, "wb") as f:
        f.write(file_bytes)
    pdf_url = f"/api/pdf/{pdf_id}"
    logger.info(f"PDF uploaded: {safe_name} -> {pdf_id[:8]}")
    if AGNOST_WRITE_KEY:
        try:
            import agnost
            agnost.track(user_id=user_id or "api", agent_name="nagarik_tool",
                         input=safe_name, output=pdf_url,
                         properties={"tool": "upload_pdf", "filename": safe_name, "size": len(file_bytes)},
                         success=True, latency=0)
        except Exception:
            pass
    return {"success": True, "pdf_id": pdf_id, "pdf_url": pdf_url, "filename": safe_name,
            "size": len(file_bytes)}


@api_router.post("/upload-and-extract")
async def upload_and_extract_pdf(
    file: UploadFile = File(...), user_id: str = Form(""),
    scheme_hint: str = Form(""), save_to_db: bool = Form(True),
):
    """Upload a PDF and immediately extract form fields."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")
    if file.content_type and file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDF files are accepted.")
    file_bytes = await file.read()
    if len(file_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")
    if not validate_pdf_content(file_bytes):
        raise HTTPException(status_code=400, detail="Invalid PDF file content")

    pdf_id = str(uuid.uuid4())
    safe_name = re.sub(r'[^a-zA-Z0-9._\-]', '_', file.filename)
    pdf_path = UPLOADS_DIR / f"{pdf_id}.pdf"
    with open(pdf_path, "wb") as f:
        f.write(file_bytes)

    from form_extractor import extract_form_fields
    t0 = _time.time()
    result = await extract_form_fields(pdf_path=str(pdf_path), scheme_hint=scheme_hint)
    latency = int((_time.time() - t0) * 1000)

    if "error" in result:
        logger.warning(f"Extraction failed for {safe_name}: {result['error']}")
        return {
            "success": False, "pdf_id": pdf_id, "pdf_url": f"/api/pdf/{pdf_id}",
            "filename": safe_name, "error": result["error"],
            "extraction_method": result.get("extraction_method", "unknown"),
        }

    saved_to_db = False
    if save_to_db and result.get("schemeName"):
        try:
            from prisma import Json
            scheme_name = result["schemeName"]
            existing = await prisma.formtemplate.find_first(where={"schemeName": scheme_name})
            data = {
                "schemeName": scheme_name,
                "schemeNameHindi": result.get("schemeNameHindi", ""),
                "officialPdfUrl": f"/api/pdf/{pdf_id}",
                "category": result.get("category", "general"),
                "totalFields": result.get("totalFields", len(result.get("extractedFields", []))),
                "extractedFields": Json(result.get("extractedFields", [])),
                "sections": Json(result.get("sections", [])),
            }
            if existing:
                await prisma.formtemplate.update(where={"id": existing.id}, data=data)
            else:
                await prisma.formtemplate.create(data=data)
            saved_to_db = True
            logger.info(f"FormTemplate saved for '{scheme_name}' ({result.get('totalFields', 0)} fields)")
        except Exception as e:
            logger.error(f"Failed to save FormTemplate: {e}")

    if AGNOST_WRITE_KEY:
        try:
            import agnost
            agnost.track(user_id=user_id or "api", agent_name="nagarik_tool",
                         input=f"upload_extract:{safe_name}", output=str(result.get("totalFields", 0)),
                         properties={"tool": "upload_and_extract", "filename": safe_name,
                                     "scheme": result.get("schemeName", ""), "fields": result.get("totalFields", 0),
                                     "method": result.get("_extraction_method", "")},
                         success=True, latency=latency)
        except Exception:
            pass

    return {
        "success": True, "pdf_id": pdf_id, "pdf_url": f"/api/pdf/{pdf_id}",
        "filename": safe_name, "saved_to_db": saved_to_db,
        "extraction_method": result.get("_extraction_method", "unknown"),
        "acroform_fields_found": result.get("_acroform_field_count", 0),
        "text_length": result.get("_text_length", 0),
        "scheme": result.get("schemeName", ""),
        "totalFields": result.get("totalFields", 0),
        "extractedFields": result.get("extractedFields", []),
        "sections": result.get("sections", []),
        "category": result.get("category", "general"),
    }
