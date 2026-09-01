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

    # Seed real government schemes and their form templates from the curated
    # catalog (data/gov_forms.py). Idempotent and non-destructive: existing
    # templates are left alone, so live-refreshed or user-uploaded forms
    # survive a restart.
    try:
        from services.form_seeder import seed_from_catalog
        report = await seed_from_catalog(overwrite=False)
        logger.info(
            "Government form catalog seeded: %d created, %d updated, %d already present",
            report["created"], report["updated"], report["skipped"],
        )
        if report["errors"]:
            logger.warning("Catalog seed errors: %s", report["errors"])
    except Exception as e:
        logger.error(f"Catalog seed failed: {e}\n{traceback.format_exc()}")

    try:
        scheme_count = await prisma.scheme.count()
        template_count = await prisma.formtemplate.count()
        logger.info(
            f"Ready: {scheme_count} schemes, {template_count} form templates"
        )
    except Exception as e:
        logger.error(f"Startup count failed: {e}")


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
