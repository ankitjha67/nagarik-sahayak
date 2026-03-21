"""Demo mode status and toggle routes."""
import config
from fastapi import Request, HTTPException
from routes import api_router


@api_router.get("/demo/status")
async def demo_status():
    return {"demo_mode": config.DEMO_MODE}


@api_router.post("/demo/toggle")
async def demo_toggle(request: Request):
    admin_secret = request.headers.get("X-Admin-Secret", "")
    if not config.ADMIN_SECRET or admin_secret != config.ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Admin authentication required")
    async with config.demo_lock:
        config.DEMO_MODE = not config.DEMO_MODE
    return {"demo_mode": config.DEMO_MODE}
