"""Route registration — combines all route modules into a single APIRouter."""
from fastapi import APIRouter

api_router = APIRouter(prefix="/api")


def register_all_routes():
    """Import and include all route sub-modules."""
    from routes import auth, chat, profile, schemes, pdf, demo, v2
    # Routes are registered via decorators on api_router at import time
    return api_router
