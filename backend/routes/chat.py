"""Chat and voice transcription routes."""
import os
import uuid
import json
import logging
import tempfile
import traceback
import time as _time
from datetime import datetime, timezone
from fastapi import UploadFile, File, Form, HTTPException
from database import prisma
from config import AGNOST_WRITE_KEY, AUDIO_DIR, DEMO_MODE, sanitize_input
from models import ChatMessageRequest
from services.chat import save_chat_prisma, get_chat_history_prisma
from services.profiler import profiler_agent_respond
from services.demo import is_demo_trigger, demo_stage_response
from services.search import search_schemes_sync, SCHEMES_SEED, SCHEME_KEYWORDS, STOPWORDS
from routes import api_router

logger = logging.getLogger(__name__)

BOT_RESPONSES = {
    "greeting": {"hi": "नमस्ते! मैं नागरिक सहायक हूँ। मैं आपकी सरकारी योजनाओं और सेवाओं में मदद कर सकता हूँ।"},
    "schemes": {"hi": "हमारे पास 3 प्रमुख योजनाएं उपलब्ध हैं:\n\n1. पीएम-किसान सम्मान निधि\n2. आयुष्मान भारत (पीएम-जय)\n3. सुकन्या समृद्धि योजना\n\nकिसी योजना के बारे में जानने के लिए उसका नाम लिखें।"},
    "default": {"hi": "धन्यवाद! कृपया 'योजनाएं' टाइप करें सभी उपलब्ध योजनाओं को देखने के लिए।"},
}


def get_bot_response_with_mcp(content: str, language: str = "hi") -> dict:
    low = content.lower().strip()
    is_greeting = any(w in low for w in ["hello", "hi", "namaste", "नमस्ते", "हैलो", "start"])
    is_scheme_query = any(w in low for w in ["योजना", "scheme", "yojana", "plan"])
    needs_tool = any(w in low for w in [
        "kisan", "किसान", "farmer", "ayushman", "आयुष्मान", "health", "hospital", "स्वास्थ्य",
        "sukanya", "सुकन्या", "girl", "बेटी", "eligib", "पात्र", "benefit", "लाभ",
    ])

    if is_greeting:
        return {"content": BOT_RESPONSES["greeting"]["hi"], "tool_calls": []}
    if is_scheme_query and not needs_tool:
        return {"content": BOT_RESPONSES["schemes"]["hi"], "tool_calls": []}

    if needs_tool:
        t0 = _time.time()
        tool_result = search_schemes_sync(content, language)
        latency = int((_time.time() - t0) * 1000)
        if AGNOST_WRITE_KEY:
            try:
                import agnost
                agnost.track(user_id="chat", agent_name="nagarik_tool", input=content,
                             output=str(tool_result.get("match_found", False)),
                             properties={"tool": "search_schemes", "language": language},
                             success=tool_result.get("match_found", False), latency=latency)
            except Exception:
                pass

        if tool_result["match_found"]:
            if language == "hi":
                resp = f"Document scanned: {tool_result['matched_schemes'][0]['scheme_title']}\n\n"
                for ms in tool_result["matched_schemes"]:
                    resp += f"• {ms['scheme_title']}\n  पात्रता: {ms['eligibility']}\n  लाभ: {ms['benefits']}\n\n"
            else:
                resp = tool_result["result_text"]
        else:
            resp = "मुझे जानकारी नहीं मिली — कृपया अलग शब्दों में पूछें।"
        return {
            "content": resp,
            "tool_calls": [{
                "tool_name": "search_schemes", "tool_input": tool_result["tool_input"],
                "documents_scanned": tool_result["documents_scanned"],
                "match_found": tool_result["match_found"],
                "results": tool_result.get("matched_schemes", []),
            }],
        }

    return {"content": BOT_RESPONSES["default"]["hi"], "tool_calls": []}


@api_router.post("/chat")
async def send_chat_message(req: ChatMessageRequest):
    req.content = sanitize_input(req.content, max_length=5000)
    if not req.content:
        raise HTTPException(status_code=400, detail="Message content is required")

    now = datetime.now(timezone.utc).isoformat()
    user_msg = {
        "id": str(uuid.uuid4()), "user_id": req.user_id, "role": "user",
        "content": req.content, "status": "sent", "created_at": now, "tool_calls": [],
    }
    await save_chat_prisma(req.user_id, user_msg, "user")

    if DEMO_MODE and is_demo_trigger(req.content):
        demo = demo_stage_response(req.user_id)
        bot_msg = {
            "id": str(uuid.uuid4()), "user_id": req.user_id, "role": "assistant",
            "content": demo["content"], "status": "delivered",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "tool_calls": demo.get("tool_calls", []), "type": demo.get("type", "profiler_complete"),
            "profiler_field": "", "eligibility_results": demo.get("eligibility_results", []),
            "pdf_url": demo.get("pdf_url", ""), "pdf_urls": demo.get("pdf_urls", []),
            "tool_progress": demo.get("tool_progress", []),
        }
        await save_chat_prisma(req.user_id, bot_msg, "agent")
        user_msg["status"] = "read"
        return {"user_message": user_msg, "bot_message": bot_msg}

    profiler_result = await profiler_agent_respond(req.user_id, req.content)
    if profiler_result:
        bot_msg = {
            "id": str(uuid.uuid4()), "user_id": req.user_id, "role": "assistant",
            "content": profiler_result["content"], "status": "delivered",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "tool_calls": profiler_result.get("tool_calls", []),
            "type": profiler_result.get("type", "profiler"),
            "profiler_field": profiler_result.get("profiler_field", ""),
            "eligibility_results": profiler_result.get("eligibility_results", []),
            "pdf_url": profiler_result.get("pdf_url", ""),
            "pdf_urls": profiler_result.get("pdf_urls", []),
            "tool_progress": profiler_result.get("tool_progress", []),
        }
        await save_chat_prisma(req.user_id, bot_msg, "agent")
        user_msg["status"] = "read"
        return {"user_message": user_msg, "bot_message": bot_msg}

    mcp_result = get_bot_response_with_mcp(req.content, req.language)
    bot_msg = {
        "id": str(uuid.uuid4()), "user_id": req.user_id, "role": "assistant",
        "content": mcp_result["content"], "status": "delivered",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tool_calls": mcp_result["tool_calls"],
    }
    await save_chat_prisma(req.user_id, bot_msg, "agent")
    user_msg["status"] = "read"
    return {"user_message": user_msg, "bot_message": bot_msg}


@api_router.get("/chat/history/{user_id}")
async def get_chat_history(user_id: str):
    return await get_chat_history_prisma(user_id)


@api_router.post("/transcribe")
async def transcribe_audio(audio: UploadFile = File(...), user_id: str = Form(""), language: str = Form("hi")):
    audio_bytes = await audio.read()
    audio_msg_id = str(uuid.uuid4())
    audio_path = AUDIO_DIR / f"{audio_msg_id}.webm"
    with open(audio_path, "wb") as af:
        af.write(audio_bytes)

    transcript_hi = ""
    transcript_en = ""
    sarvam_key = os.environ.get("SARVAM_API_KEY", "")
    if sarvam_key:
        tmp_path = None
        try:
            from sarvamai import SarvamAI
            sarvam_client = SarvamAI(api_subscription_key=sarvam_key)
            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            with open(tmp_path, "rb") as f:
                resp_orig = sarvam_client.speech_to_text.transcribe(file=f, model="saaras:v3", mode="transcribe")
            original_text = resp_orig.transcript or ""

            if language == "en":
                transcript_en = original_text
                with open(tmp_path, "rb") as f:
                    resp_hi = sarvam_client.speech_to_text.transcribe(file=f, model="saaras:v3", mode="transcribe", language_code="hi-IN")
                transcript_hi = resp_hi.transcript or original_text
            else:
                transcript_hi = original_text
                with open(tmp_path, "rb") as f:
                    resp_en = sarvam_client.speech_to_text.transcribe(file=f, model="saaras:v3", mode="translate")
                transcript_en = resp_en.transcript or ""

            logger.info(f"Sarvam STT success: lang={language}")
        except Exception as e:
            logger.error(f"Sarvam STT failed: {e}\n{traceback.format_exc()}")
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    is_mock = False
    if not transcript_hi and not transcript_en:
        if DEMO_MODE:
            is_mock = True
            transcript_hi = "मेरा बेटा 10th पास है, कॉलेज के लिए पैसा चाहिए"
            transcript_en = "My son passed 10th, need money for college"
        else:
            return {"success": False, "error": "Speech transcription failed. Please try again or type your message.",
                    "transcript_hi": "", "transcript_en": "", "is_mock": False,
                    "user_message": None, "bot_message": None}

    audio_url = f"/api/audio/{audio_msg_id}"
    display = f"[Hindi] {transcript_hi}" if transcript_hi else ""
    if transcript_en:
        display += f"\n[English] {transcript_en}" if display else f"[English] {transcript_en}"

    user_msg = {
        "id": audio_msg_id, "user_id": user_id, "role": "user", "content": display,
        "status": "read", "created_at": datetime.now(timezone.utc).isoformat(),
        "tool_calls": [], "type": "transcription",
        "transcript_hi": transcript_hi, "transcript_en": transcript_en, "audio_url": audio_url,
    }
    if user_id:
        await save_chat_prisma(user_id, user_msg, "user")

    query_text = transcript_hi or transcript_en
    profiler_result = await profiler_agent_respond(user_id, query_text) if user_id else None
    if profiler_result:
        bot_msg = {
            "id": str(uuid.uuid4()), "user_id": user_id, "role": "assistant",
            "content": profiler_result["content"], "status": "delivered",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "tool_calls": profiler_result.get("tool_calls", []),
            "type": profiler_result.get("type", "profiler"),
            "profiler_field": profiler_result.get("profiler_field", ""),
            "eligibility_results": profiler_result.get("eligibility_results", []),
            "pdf_url": profiler_result.get("pdf_url", ""),
            "pdf_urls": profiler_result.get("pdf_urls", []),
            "tool_progress": profiler_result.get("tool_progress", []),
        }
    else:
        mcp = get_bot_response_with_mcp(query_text, language)
        bot_msg = {
            "id": str(uuid.uuid4()), "user_id": user_id, "role": "assistant",
            "content": mcp["content"], "status": "delivered",
            "created_at": datetime.now(timezone.utc).isoformat(), "tool_calls": mcp["tool_calls"],
        }
    if user_id:
        await save_chat_prisma(user_id, bot_msg, "agent")

    if AGNOST_WRITE_KEY:
        try:
            import agnost
            agnost.track(user_id=user_id or "api", agent_name="nagarik_tool",
                         input=f"audio_{len(audio_bytes)}bytes", output=query_text[:100],
                         properties={"tool": "sarvam_stt", "is_mock": is_mock, "language": language},
                         success=not is_mock, latency=0)
        except Exception:
            pass

    return {"success": True, "transcript_hi": transcript_hi, "transcript_en": transcript_en,
            "is_mock": is_mock, "user_message": user_msg, "bot_message": bot_msg}


@api_router.post("/chat/voice")
async def voice_to_text(audio: UploadFile = File(...), user_id: str = Form(""), language: str = Form("hi")):
    return await transcribe_audio(audio=audio, user_id=user_id, language=language)


@api_router.post("/chat/reset")
async def reset_chat(req: dict = {}):
    user_id = req.get("user_id", "")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id required")
    try:
        await prisma.user.update(where={"id": user_id}, data={"profile": json.dumps({})})
    except Exception as e:
        logger.error(f"Profile reset failed: {e}")
    try:
        await prisma.chatlog.delete_many(where={"userId": user_id})
    except Exception as e:
        logger.error(f"Chat history clear failed: {e}")
    logger.info(f"Chat reset for user {user_id}")
    return {"success": True, "message": "Chat reset. Profile cleared."}
