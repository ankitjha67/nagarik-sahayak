"""Scheme listing, search, and eligibility check routes."""
import json
from fastapi import HTTPException
from database import prisma
from config import DEMO_MODE
from models import SearchSchemesRequest, EligibilityCheckRequest
from services.search import search_schemes_prisma, SCHEMES_SEED
from services.eligibility import eligibility_matcher_prisma, eligibility_matcher_sync
from services.demo import is_demo_trigger, VIDYASIRI_RESULT
from routes import api_router


@api_router.get("/schemes")
async def get_schemes():
    schemes = await prisma.scheme.find_many()
    return [
        {
            "id": s.id, "name": s.name, "title": s.name, "title_hi": s.name,
            "eligibility": s.eligibilityCriteriaText, "pdfUrl": s.pdfUrl,
            "description": s.eligibilityCriteriaText,
            **({k: v for k, v in SCHEMES_SEED[i].items() if k not in ("id",)} if i < len(SCHEMES_SEED) else {})
        }
        for i, s in enumerate(schemes)
    ]


@api_router.post("/search-schemes")
async def search_schemes_endpoint(req: SearchSchemesRequest):
    if DEMO_MODE and is_demo_trigger(req.query):
        return {
            "tool_name": "search_schemes", "tool_input": {"query": req.query},
            "documents_scanned": ["Vidyasiri Scholarship Guidelines"], "match_found": True,
            "matched_schemes": [{
                "scheme_title": "विद्यासिरी छात्रवृत्ति", "scheme_title_en": "Vidyasiri Scholarship",
                "eligibility": "10th pass student, Karnataka domicile",
                "benefits": VIDYASIRI_RESULT["benefit"],
                "pdf_url": "https://sw.kar.nic.in/vidyasiri", "category": "education",
            }],
            "result_text": f"Vidyasiri Scholarship: {VIDYASIRI_RESULT['benefit']}",
        }
    return await search_schemes_prisma(req.query)


@api_router.post("/eligibility-check")
async def eligibility_check_endpoint(req: EligibilityCheckRequest):
    if req.user_id:
        return await eligibility_matcher_prisma(req.user_id)
    profile = req.profile
    if not profile:
        raise HTTPException(status_code=400, detail="Provide user_id or profile object")
    return eligibility_matcher_sync(profile, req.query)
