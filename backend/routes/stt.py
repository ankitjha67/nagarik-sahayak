"""Speech-to-text routes.

  GET  /stt/providers           what engines this deployment has (public)
  POST /stt/transcribe          audio in, transcript out (signed-in caller)

The chat route (/transcribe) uses the same registry and adds the chat turn;
this endpoint is the plain building block for any client, native or web.
"""
from __future__ import annotations

import logging

from fastapi import File, Form, HTTPException, Request, UploadFile

from auth.deps import subject_for
from routes import api_router
from stt import registry
from stt.base import SttError, Transcript

logger = logging.getLogger(__name__)

MAX_AUDIO_BYTES = 15 * 1024 * 1024


@api_router.get("/stt/providers")
async def stt_providers(language: str = "hi"):
    return registry.describe(language)


@api_router.post("/stt/transcribe")
async def stt_transcribe(request: Request, audio: UploadFile | None = File(None),
                         text: str = Form(""), language: str = Form("hi"),
                         provider: str = Form(""), translate: bool = Form(False),
                         user_id: str = Form("")):
    """Transcribe an upload, or record a transcript the browser produced.

    `provider` names an engine key from /stt/providers; "client" (or a `text`
    field) means the browser already transcribed and only the text is sent.
    `translate` asks for an English rendering too, where the engine can.
    """
    subject_for(request, user_id)   # 401/403 before any audio is read

    if text.strip() and (provider in ("", "client") or not audio):
        t = Transcript(text=text.strip()[:5000], language=language.split("-")[0], provider="client",
                       model="web-speech")
        return {"success": True, "transcript": t.as_dict(), "attempts": [{"provider": "client", "ok": True}]}

    if audio is None:
        raise HTTPException(status_code=400, detail="Send an audio file, or text from on-device recognition.")
    data = await audio.read()
    if not data:
        raise HTTPException(status_code=400, detail="The audio file is empty.")
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio too large (limit 15 MB).")
    if provider and registry.get(provider) is None:
        raise HTTPException(status_code=400, detail=f"Unknown provider '{provider}'.")

    try:
        t, attempts = await registry.transcribe(
            data, mime=audio.content_type or "", language=language,
            translate_to="en" if translate else "", requested=provider)
    except SttError as e:
        logger.warning("STT failed: %s", e)
        raise HTTPException(status_code=503, detail="Speech could not be transcribed right now. "
                                                    "Please try again or type your message.")
    return {"success": True, "transcript": t.as_dict(), "attempts": attempts}
