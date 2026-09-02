"""Profiler Agent — collects user profile one question at a time, then runs eligibility + PDF generation."""
import re
import json
import logging
import traceback
from typing import Optional
from database import prisma
from services.chat import save_chat_prisma
from services.search import search_schemes_prisma
from services.eligibility import eligibility_matcher_prisma

logger = logging.getLogger(__name__)

PROFILE_FIELDS = ["name", "age", "income", "state"]
PROFILER_QUESTIONS = {
    "name": "आपका नाम क्या है?",
    "age": "आपकी उम्र कितनी है?",
    "income": "आपकी सालाना घरेलू आय कितनी है? (रुपये में)",
    "state": "आप किस राज्य में रहते हैं?",
}


def get_next_missing_field(profile: dict) -> Optional[str]:
    for f in PROFILE_FIELDS:
        val = profile.get(f)
        if val is None or val == "" or val == 0:
            return f
    return None


def parse_profile_answer(field: str, text: str):
    text = text.strip()
    if field == "name":
        name = re.sub(r'[^a-zA-Z\u0900-\u097F\s]', '', text).strip()
        if len(name) < 2:
            return None, "कृपया अपना पूरा नाम बताएं।"
        return name, None
    elif field == "age":
        nums = re.findall(r'\d+', text)
        if not nums:
            return None, "कृपया अपनी उम्र संख्या में बताएं।"
        age = int(nums[0])
        if age < 1 or age > 120:
            return None, "कृपया सही उम्र बताएं (1-120)।"
        return age, None
    elif field == "income":
        nums = re.findall(r'\d+', text.replace(",", ""))
        if not nums:
            return None, "कृपया आय राशि संख्या में बताएं।"
        income = int(nums[0])
        if income < 0:
            return None, "कृपया सही आय बताएं।"
        return income, None
    elif field == "state":
        state = text.strip()
        if len(state) < 2:
            return None, "कृपया अपने राज्य का नाम बताएं।"
        return state, None
    return None, "Invalid field"


async def generate_filled_form(user_id: str, scheme_id: str) -> dict:
    """MCP Tool 3: Generate a filled application form PDF with Hindi fields."""
    import uuid
    import time as _time
    from config import PDF_DIR, AGNOST_WRITE_KEY

    t0 = _time.time()
    user = await prisma.user.find_unique(where={"id": user_id})
    scheme = await prisma.scheme.find_unique(where={"id": scheme_id})
    if not user or not scheme:
        return {"success": False, "error": "User or Scheme not found"}

    profile = json.loads(user.profile) if isinstance(user.profile, str) and user.profile else (user.profile or {})
    from pdf_generator import generate_filled_form_pdf

    pdf_id = str(uuid.uuid4())
    pdf_path = str(PDF_DIR / f"{pdf_id}.pdf")

    generate_filled_form_pdf(
        profile=profile, scheme_name=scheme.name,
        scheme_criteria=scheme.eligibilityCriteriaText,
        output_path=pdf_path,
    )
    pdf_url = f"/api/pdf/{pdf_id}"

    try:
        await prisma.application.create(data={
            "userId": user_id, "schemeId": scheme_id,
            "status": "generated", "formUrl": pdf_url,
        })
    except Exception as e:
        logger.error(f"Application create failed: {e}\n{traceback.format_exc()}")

    latency = int((_time.time() - t0) * 1000)
    if AGNOST_WRITE_KEY:
        try:
            import agnost
            agnost.track(
                user_id=user_id, agent_name="nagarik_tool",
                input=scheme.name, output=pdf_url,
                properties={"tool": "generate_filled_form", "scheme_id": scheme_id, "pdf_id": pdf_id},
                success=True, latency=latency,
            )
        except Exception:
            pass

    return {"success": True, "pdf_url": pdf_url, "pdf_id": pdf_id,
            "scheme_name": scheme.name, "user_name": profile.get("name", "")}


async def profiler_agent_respond(user_id: str, content: str) -> Optional[dict]:
    """Profiler Agent via Prisma: checks User.profile, asks ONE question at a time.
    Returns None if profile is complete."""
    user = await prisma.user.find_unique(where={"id": user_id})
    if not user:
        return None

    profile = user.profile or {}
    if isinstance(profile, str):
        profile = json.loads(profile)

    if profile.get("_complete"):
        return None

    pending = get_next_missing_field(profile)
    if not pending:
        await prisma.user.update(where={"id": user_id}, data={
            "profile": json.dumps({**profile, "_complete": True}, ensure_ascii=False)
        })
        return None

    low = content.lower().strip()
    is_greeting = any(w in low for w in ["hello", "hi", "namaste", "नमस्ते", "हैलो", "start"])

    last_bot_logs = await prisma.chatlog.find_many(
        where={"userId": user_id, "sender": "agent"},
        order={"timestamp": "desc"}, take=1,
    )
    asked_field = ""
    if last_bot_logs:
        try:
            last_msg = json.loads(last_bot_logs[0].message)
            asked_field = last_msg.get("profiler_field", "")
        except (json.JSONDecodeError, TypeError, KeyError):
            pass

    if is_greeting or not asked_field:
        greeting = "नमस्ते! मैं नागरिक सहायक हूँ।\nआपकी पात्रता जांचने के लिए मुझे कुछ जानकारी चाहिए।\n\n"
        return {
            "content": greeting + PROFILER_QUESTIONS[pending],
            "tool_calls": [], "type": "profiler", "profiler_field": pending,
        }

    if asked_field in PROFILE_FIELDS:
        value, error = parse_profile_answer(asked_field, content)
        if error:
            return {
                "content": error + "\n\n" + PROFILER_QUESTIONS[asked_field],
                "tool_calls": [], "type": "profiler", "profiler_field": asked_field,
            }

        profile[asked_field] = value
        await prisma.user.update(where={"id": user_id}, data={
            "profile": json.dumps(profile, ensure_ascii=False)
        })

        next_field = get_next_missing_field(profile)
        if not next_field:
            profile["_complete"] = True
            await prisma.user.update(where={"id": user_id}, data={
                "profile": json.dumps(profile, ensure_ascii=False)
            })

            await search_schemes_prisma("scholarship eligibility")
            matcher_result = await eligibility_matcher_prisma(user_id)

            pdf_urls = []
            eligible_results = [r for r in matcher_result.get("results", []) if r["eligible"]]
            for er in eligible_results:
                if er.get("scheme_id"):
                    form_result = await generate_filled_form(user_id, er["scheme_id"])
                    if form_result.get("success"):
                        pdf_urls.append({"pdf_url": form_result["pdf_url"], "scheme_name": er["scheme"]})

            reply = "प्रोफाइल पूरी हो गई!\n\n"
            reply += f"नाम: {profile.get('name', '')} | उम्र: {profile.get('age', '')} वर्ष\n"
            reply += f"सालाना आय: ₹{profile.get('income', 0):,} | राज्य: {profile.get('state', '')}\n\n"
            reply += "पात्रता जांच पूरी हुई!\n\n"
            for r in matcher_result.get("results", []):
                icon = "+" if r["eligible"] else "-"
                reply += f"[{icon}] {r['scheme']}: {'पात्र' if r['eligible'] else 'अपात्र'}\n"
                reply += f"    कारण: {r['reason']}\n"
                if r["eligible"] and r.get("benefit"):
                    reply += f"    लाभ: {r['benefit']}\n"
                reply += "\n"
            if pdf_urls:
                reply += f"{len(pdf_urls)} भरे हुए आवेदन फॉर्म तैयार हैं! नीचे डाउनलोड करें।"

            tool_progress = [
                {"step": "reading_pdf", "text_hi": "विद्यासिरी छात्रवृत्ति PDF पढ़ रहे हैं...", "text_en": "Reading Vidyasiri Scholarship PDF..."},
                {"step": "checking_eligibility", "text_hi": "पात्रता मानदंड जांच रहे हैं...", "text_en": "Checking eligibility criteria..."},
                {"step": "generating_form", "text_hi": "भरा हुआ आवेदन फॉर्म तैयार कर रहे हैं...", "text_en": "Generating filled application form..."},
            ]

            return {
                "content": reply,
                "tool_calls": [{
                    "tool_name": "eligibility_matcher",
                    "tool_input": matcher_result.get("tool_input", {}),
                    "documents_scanned": matcher_result.get("documents_scanned", []),
                    "match_found": matcher_result.get("match_found", False),
                    "results": matcher_result.get("results", []),
                }],
                "type": "profiler_complete", "profiler_field": "",
                "eligibility_results": matcher_result.get("results", []),
                "pdf_url": pdf_urls[0]["pdf_url"] if pdf_urls else "",
                "pdf_urls": pdf_urls, "tool_progress": tool_progress,
            }
        else:
            confirm = ""
            if asked_field == "name":
                confirm = f"धन्यवाद, {value}!\n\n"
            elif asked_field == "age":
                confirm = f"उम्र: {value} वर्ष। ठीक है।\n\n"
            elif asked_field == "income":
                confirm = f"सालाना आय: ₹{value:,}। ठीक है।\n\n"
            return {
                "content": confirm + PROFILER_QUESTIONS[next_field],
                "tool_calls": [], "type": "profiler", "profiler_field": next_field,
            }

    return {
        "content": PROFILER_QUESTIONS[pending],
        "tool_calls": [], "type": "profiler", "profiler_field": pending,
    }
