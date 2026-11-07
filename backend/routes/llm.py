"""LLM routes.

  GET  /llm/providers     what text-generation engines this deployment has (public)
  POST /llm/complete      run a prompt through the registry (admin - spends tokens)

The LLM is optional: the app's form extraction and chat work without it. This
surface lets an operator plug in NVIDIA NIM or any major provider and confirm
the key before relying on it.
"""
from __future__ import annotations

import logging

from fastapi import HTTPException, Request
from pydantic import BaseModel

from auth.deps import require_role
from llm import registry
from llm.base import LlmError
from routes import api_router

logger = logging.getLogger(__name__)


@api_router.get("/llm/providers")
async def llm_providers():
    return registry.describe()


class CompleteRequest(BaseModel):
    prompt: str
    system: str = ""
    provider: str = ""
    temperature: float = 0.2
    max_tokens: int = 1024
    json_mode: bool = False


@api_router.post("/llm/complete")
async def llm_complete(req: CompleteRequest, request: Request):
    # Running a model spends money/quota, so this is admin-only; it is the way
    # to test a newly configured key.
    await require_role("admin")(request)
    if req.provider and registry.get(req.provider) is None:
        raise HTTPException(status_code=400, detail=f"Unknown provider '{req.provider}'.")
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt is required")
    try:
        completion, attempts = await registry.complete(
            req.prompt, req.system, requested=req.provider,
            temperature=req.temperature, max_tokens=req.max_tokens, json_mode=req.json_mode)
    except LlmError as e:
        logger.warning("LLM complete failed: %s", e)
        raise HTTPException(status_code=503, detail="No LLM provider is configured or reachable.")
    return {"success": True, "completion": completion.as_dict(), "attempts": attempts}
