"""Nagarik Sahayak — FastAPI Application Entry Point.

This is the slim app entry that wires up:
- Database connections (Prisma + Motor)
- CORS middleware
- All route modules (auth, chat, profile, schemes, pdf, demo, v2)
- Startup seeding and shutdown cleanup
"""
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
import logging
import traceback

from config import AGNOST_WRITE_KEY, CORS_ORIGINS
from database import prisma, motor_client

# Initialize Agnost tracking
if AGNOST_WRITE_KEY:
    import agnost
    agnost.init(AGNOST_WRITE_KEY)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI()


# --- Startup / Shutdown ---

@app.on_event("startup")
async def startup():
    await prisma.connect()
    logger.info("Prisma connected")
    # Seed Prisma Scheme table (idempotent)
    count = await prisma.scheme.count()
    if count == 0:
        try:
            for s in [
                {"name": "Pradhan Mantri Awas Yojana",
                 "eligibilityCriteriaText": "Family income < ₹3 lakh per annum, no pucca house owned, rural or urban BPL category.",
                 "pdfUrl": "https://pmaymis.gov.in/pdf/pmay_guidelines.pdf"},
                {"name": "Vidyasiri Scholarship",
                 "eligibilityCriteriaText": "Karnataka resident, passed 10th or equivalent, family income < ₹1.5 lakh, studying in Karnataka.",
                 "pdfUrl": "https://karnataka.gov.in/scholarship/vidyasiri.pdf"},
                {"name": "Vidya Lakshmi Education Loan",
                 "eligibilityCriteriaText": "Indian citizen, 12th pass, pursuing higher education in approved institution.",
                 "pdfUrl": "https://www.vidyalakshmi.co.in/files/guidelines.pdf"},
            ]:
                existing = await prisma.scheme.find_first(where={"name": s["name"]})
                if not existing:
                    await prisma.scheme.create(data=s)
        except Exception as e:
            logger.error(f"Seed failed: {e}\n{traceback.format_exc()}")
    scheme_count = await prisma.scheme.count()
    logger.info(f"Prisma Scheme table: {scheme_count} records")


@app.on_event("shutdown")
async def shutdown():
    if AGNOST_WRITE_KEY:
        import agnost
        agnost.shutdown()
    await prisma.disconnect()
    if motor_client:
        motor_client.close()


# --- Register Routes ---

from routes import register_all_routes
api_router = register_all_routes()

# Health / root
@api_router.get("/")
async def root():
    return {"message": "Nagarik Sahayak API", "version": "2.0.0"}

@api_router.get("/analytics/status")
async def analytics_status():
    return {"enabled": bool(AGNOST_WRITE_KEY), "dashboard_url": "https://app.agnost.ai"}

app.include_router(api_router)

# CORS: explicit origins only, never wildcard with credentials
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-User-Id", "X-Admin-Secret"],
)
