from fastapi import FastAPI, APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from prisma import Prisma
import os
import json
import logging
import tempfile
import uuid
import re
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import time as _time
import agnost

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Initialize Agnost tracking
_agnost_key = os.environ.get("AGNOST_WRITE_KEY", "")
if _agnost_key:
    agnost.init(_agnost_key)

DEMO_MODE = os.environ.get("DEMO_MODE", "").lower() in ("true", "1", "yes")

AUDIO_DIR = ROOT_DIR / "audio_files"
AUDIO_DIR.mkdir(exist_ok=True)
PDF_DIR = ROOT_DIR / "pdf_reports"
PDF_DIR.mkdir(exist_ok=True)

# Prisma client (connected on startup)
prisma = Prisma()

# Motor — only for otp_sessions (not in Prisma schema)
mongo_url = os.environ['MONGO_URL']
motor_client = AsyncIOMotorClient(mongo_url)
motor_db = motor_client[os.environ['DB_NAME']]

# FastAPI app
app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# --- Pydantic Models ---

class SendOTPRequest(BaseModel):
    phone: str

class VerifyOTPRequest(BaseModel):
    phone: str
    otp: str

class AuthResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    success: bool
    message: str
    user_id: Optional[str] = None
    phone: Optional[str] = None

class ChatMessageRequest(BaseModel):
    user_id: str
    content: str
    language: str = "hi"

class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    language: Optional[str] = None
    profile_data: Optional[Dict[str, Any]] = None

class SearchSchemesRequest(BaseModel):
    query: str

class EligibilityCheckRequest(BaseModel):
    user_id: Optional[str] = None
    profile: Optional[Dict[str, Any]] = None
    query: Optional[str] = ""

class GeneratePDFRequest(BaseModel):
    user_id: Optional[str] = None
    profile: Optional[Dict[str, Any]] = None
    scheme_id: Optional[str] = None


# --- Helpers: save/load rich chat messages via Prisma ChatLog ---

async def save_chat_prisma(user_id: str, msg_dict: dict, sender: str):
    """Save a rich message dict to Prisma ChatLog."""
    try:
        await prisma.chatlog.create(data={
            "userId": user_id,
            "message": json.dumps(msg_dict, ensure_ascii=False, default=str),
            "sender": sender,
        })
    except Exception as e:
        logger.error(f"Prisma ChatLog save failed: {e}")


async def get_chat_history_prisma(user_id: str) -> list:
    """Read chat history for a user from Prisma ChatLog."""
    try:
        logs = await prisma.chatlog.find_many(
            where={"userId": user_id},
            order={"timestamp": "asc"},
            take=500,
        )
        messages = []
        for log in logs:
            try:
                msg = json.loads(log.message)
            except (json.JSONDecodeError, TypeError):
                msg = {"content": log.message, "role": log.sender}
            msg.setdefault("id", log.id)
            msg.setdefault("created_at", log.timestamp.isoformat() if log.timestamp else "")
            messages.append(msg)
        return messages
    except Exception as e:
        logger.error(f"Prisma ChatLog read failed: {e}")
        return []


# --- Profiler Agent ---

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


async def profiler_agent_respond(user_id: str, content: str) -> Optional[dict]:
    """
    Profiler Agent via Prisma: checks User.profile, asks ONE question at a time.
    Returns None if profile is complete.
    """
    user = await prisma.user.find_unique(where={"id": user_id})
    if not user:
        return None

    profile = user.profile or {}
    if isinstance(profile, str):
        profile = json.loads(profile)

    # Check if complete
    if profile.get("_complete"):
        return None

    pending = get_next_missing_field(profile)
    if not pending:
        await prisma.user.update(where={"id": user_id}, data={
            "profile": json.dumps({**profile, "_complete": True}, ensure_ascii=False)
        })
        return None

    # Is this a greeting?
    low = content.lower().strip()
    is_greeting = any(w in low for w in ["hello", "hi", "namaste", "नमस्ते", "हैलो", "start"])

    # Find last bot profiler message to know which field was asked
    last_bot_logs = await prisma.chatlog.find_many(
        where={"userId": user_id, "sender": "agent"},
        order={"timestamp": "desc"},
        take=1,
    )
    asked_field = ""
    if last_bot_logs:
        try:
            last_msg = json.loads(last_bot_logs[0].message)
            asked_field = last_msg.get("profiler_field", "")
        except Exception:
            pass

    if is_greeting or not asked_field:
        greeting = "नमस्ते! मैं नागरिक सहायक हूँ।\nआपकी पात्रता जांचने के लिए मुझे कुछ जानकारी चाहिए।\n\n"
        return {
            "content": greeting + PROFILER_QUESTIONS[pending],
            "tool_calls": [],
            "type": "profiler",
            "profiler_field": pending,
        }

    # Parse answer for the asked field
    if asked_field in PROFILE_FIELDS:
        value, error = parse_profile_answer(asked_field, content)
        if error:
            return {
                "content": error + "\n\n" + PROFILER_QUESTIONS[asked_field],
                "tool_calls": [],
                "type": "profiler",
                "profiler_field": asked_field,
            }

        profile[asked_field] = value
        await prisma.user.update(where={"id": user_id}, data={
            "profile": json.dumps(profile, ensure_ascii=False)
        })

        next_field = get_next_missing_field(profile)
        if not next_field:
            # Profile complete!
            profile["_complete"] = True
            await prisma.user.update(where={"id": user_id}, data={
                "profile": json.dumps(profile, ensure_ascii=False)
            })

            # Step 1: search_schemes (scan documents for Agnost tracking)
            await search_schemes_prisma("scholarship eligibility")

            # Step 2: eligibility_matcher_prisma
            matcher_result = await eligibility_matcher_prisma(user_id)

            # Step 3: Generate filled forms for ALL eligible schemes
            pdf_urls = []
            eligible_results = [r for r in matcher_result.get("results", []) if r["eligible"]]
            for er in eligible_results:
                if er.get("scheme_id"):
                    form_result = await generate_filled_form(user_id, er["scheme_id"])
                    if form_result.get("success"):
                        pdf_urls.append({"pdf_url": form_result["pdf_url"], "scheme_name": er["scheme"]})

            # Build Hindi reply with progress steps
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

            # Tool progress steps for frontend streaming bullets
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
                "type": "profiler_complete",
                "profiler_field": "",
                "eligibility_results": matcher_result.get("results", []),
                "pdf_url": pdf_urls[0]["pdf_url"] if pdf_urls else "",
                "pdf_urls": pdf_urls,
                "tool_progress": tool_progress,
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
                "tool_calls": [],
                "type": "profiler",
                "profiler_field": next_field,
            }

    return {
        "content": PROFILER_QUESTIONS[pending],
        "tool_calls": [],
        "type": "profiler",
        "profiler_field": pending,
    }


# --- Scheme Data (in-memory for MCP tools) ---

SCHEMES_SEED = [
    {
        "id": "pmkisan", "title": "PM-KISAN Samman Nidhi", "title_hi": "पीएम-किसान सम्मान निधि",
        "description": "Financial benefit of Rs 6,000/- per year to eligible farmer families.",
        "description_hi": "पात्र किसान परिवारों को प्रति वर्ष 6,000 रुपये की वित्तीय सहायता।",
        "eligibility": "All landholding farmer families with cultivable land.",
        "eligibility_hi": "खेती योग्य भूमि वाले सभी भूमिधारक किसान परिवार।",
        "benefits": "Rs 2,000 every 4 months directly into bank account via DBT.",
        "benefits_hi": "हर 4 महीने में 2,000 रुपये सीधे बैंक खाते में।",
        "pdf_url": "https://pmkisan.gov.in", "icon": "sprout", "category": "agriculture",
    },
    {
        "id": "ayushman", "title": "Ayushman Bharat (PM-JAY)", "title_hi": "आयुष्मान भारत (पीएम-जय)",
        "description": "Health cover of Rs 5 lakh per family per year.",
        "description_hi": "प्रति परिवार प्रति वर्ष 5 लाख रुपये का स्वास्थ्य कवर।",
        "eligibility": "Families identified based on SECC 2011.",
        "eligibility_hi": "SECC 2011 के आधार पर चयनित परिवार।",
        "benefits": "Rs 5 Lakh health cover. Cashless treatment at empanelled hospitals.",
        "benefits_hi": "5 लाख रुपये स्वास्थ्य कवर। सूचीबद्ध अस्पतालों में कैशलेस उपचार।",
        "pdf_url": "https://pmjay.gov.in", "icon": "heart-pulse", "category": "health",
    },
    {
        "id": "sukanya", "title": "Sukanya Samriddhi Yojana", "title_hi": "सुकन्या समृद्धि योजना",
        "description": "Small savings scheme for the girl child.",
        "description_hi": "बालिकाओं के लिए लघु बचत योजना।",
        "eligibility": "Girl child below 10 years. Max 2 accounts per family.",
        "eligibility_hi": "10 वर्ष से कम आयु की बालिका। प्रति परिवार अधिकतम 2 खाते।",
        "benefits": "~8.2% interest. Tax deduction under 80C up to Rs 1.5 lakh.",
        "benefits_hi": "~8.2% ब्याज। धारा 80C के तहत 1.5 लाख रुपये तक कर कटौती।",
        "pdf_url": "https://static.pib.gov.in/WriteReadData/specificdocs/documents/2026/jan/doc2026121762801.pdf", "icon": "baby", "category": "savings",
    },
]

BOT_RESPONSES = {
    "greeting": {"hi": "नमस्ते! मैं नागरिक सहायक हूँ। मैं आपकी सरकारी योजनाओं और सेवाओं में मदद कर सकता हूँ।"},
    "schemes": {"hi": "हमारे पास 3 प्रमुख योजनाएं उपलब्ध हैं:\n\n1. पीएम-किसान सम्मान निधि\n2. आयुष्मान भारत (पीएम-जय)\n3. सुकन्या समृद्धि योजना\n\nकिसी योजना के बारे में जानने के लिए उसका नाम लिखें।"},
    "default": {"hi": "धन्यवाद! कृपया 'योजनाएं' टाइप करें सभी उपलब्ध योजनाओं को देखने के लिए।"},
}


# --- DEMO MODE ---

DEMO_PROFILE = {"name": "Rajesh Kumar", "age": 42, "income": 18000, "state": "Karnataka", "child": "Son, 10th pass"}

VIDYASIRI_RESULT = {
    "scheme": "Vidyasiri Scholarship", "scheme_hi": "विद्यासिरी छात्रवृत्ति", "eligible": True,
    "reasons": ["Child passed 10th — eligible for Post-Matric scholarship", "Family income ₹18,000/month within ₹2,50,000/year ceiling", "Karnataka domicile verified"],
    "reason": "Child passed 10th — eligible for Post-Matric scholarship; Family income ₹18,000/month within ₹2,50,000/year ceiling; Karnataka domicile verified",
    "benefit": "₹12,000–₹24,000/year tuition + hostel allowance for post-10th students",
}
PMKISAN_DEMO_RESULT = {
    "scheme": "PM-KISAN Samman Nidhi", "scheme_hi": "पीएम-किसान सम्मान निधि", "eligible": True,
    "reasons": ["Family income ₹18,000/month within ₹2,00,000/year limit"],
    "reason": "Family income ₹18,000/month within ₹2,00,000/year limit",
    "benefit": "₹6,000/year (₹2,000 every 4 months via DBT)",
}

DEMO_EXACT_TRIGGERS = ["mera beta 10th pass hai", "mera beta 10th pass", "मेरा बेटा 10th पास है", "मेरा बेटा दसवीं पास है"]
DEMO_SIGNALS = ["scholarship", "छात्रवृत्ति", "vidyasiri", "विद्यासिरी", "student", "education", "शिक्षा",
    "10th", "10वीं", "दसवीं", "pass", "पास", "beta", "बेटा", "college", "tuition", "पढ़ाई",
    "scholarship", "beta"]


def _is_demo_trigger(text: str) -> bool:
    if not DEMO_MODE:
        return False
    low = text.lower().strip()
    if low in DEMO_EXACT_TRIGGERS:
        return True
    return any(sig in low for sig in DEMO_SIGNALS)


def demo_stage_response(user_id: str = "demo") -> dict:
    from pdf_generator import generate_filled_form_pdf
    t0 = _time.time()
    results = [VIDYASIRI_RESULT, PMKISAN_DEMO_RESULT]

    # Generate PDFs for ALL eligible schemes
    pdf_urls = []
    demo_schemes = [
        ("Vidyasiri Scholarship", "Karnataka resident, passed 10th or equivalent, family income < 1.5 lakh, studying in Karnataka."),
        ("PM-KISAN Samman Nidhi", "Indian farmer, family income < 2 lakh/year, owns cultivable land."),
    ]
    for scheme_name, scheme_criteria in demo_schemes:
        pid = str(uuid.uuid4())
        generate_filled_form_pdf(
            profile=DEMO_PROFILE, scheme_name=scheme_name,
            scheme_criteria=scheme_criteria,
            output_path=str(PDF_DIR / f"{pid}.pdf"),
        )
        pdf_urls.append({"pdf_url": f"/api/pdf/{pid}", "scheme_name": scheme_name})

    try:
        if _agnost_key:
            agnost.track(user_id=user_id, agent_name="nagarik_tool", input="mera beta 10th pass hai",
                output=str(len(pdf_urls)), properties={"tool": "demo_stage", "pdf_count": len(pdf_urls)},
                success=True, latency=int((_time.time() - t0) * 1000))
    except Exception:
        pass
    summary = (
        "प्रोफाइल पूरी हो गई!\n"
        f"नाम: {DEMO_PROFILE['name']} | उम्र: {DEMO_PROFILE['age']} वर्ष\n"
        f"मासिक आय: ₹{DEMO_PROFILE['income']:,} | राज्य: {DEMO_PROFILE['state']}\n"
        f"बच्चा: {DEMO_PROFILE['child']}\n\n"
        "पात्रता जांच पूरी हुई!\n\n"
        f"[+] विद्यासिरी छात्रवृत्ति: पात्र\n    कारण: {VIDYASIRI_RESULT['reason']}\n    लाभ: {VIDYASIRI_RESULT['benefit']}\n\n"
        f"[+] पीएम-किसान सम्मान निधि: पात्र\n    कारण: {PMKISAN_DEMO_RESULT['reason']}\n    लाभ: {PMKISAN_DEMO_RESULT['benefit']}\n\n"
        f"{len(pdf_urls)} भरे हुए आवेदन फॉर्म तैयार हैं! नीचे डाउनलोड करें।"
    )
    return {
        "content": summary,
        "tool_calls": [{"tool_name": "eligibility_matcher", "tool_input": {"profile": DEMO_PROFILE},
            "documents_scanned": ["Vidyasiri Scholarship Guidelines", "PM-KISAN Operational Guidelines"],
            "match_found": True, "results": results}],
        "type": "profiler_complete", "profiler_field": "", "eligibility_results": results,
        "pdf_url": pdf_urls[0]["pdf_url"] if pdf_urls else "",
        "pdf_urls": pdf_urls,
        "tool_progress": [
            {"step": "reading_pdf", "text_hi": "विद्यासिरी छात्रवृत्ति PDF पढ़ रहे हैं...", "text_en": "Reading Vidyasiri Scholarship PDF..."},
            {"step": "checking_eligibility", "text_hi": "पात्रता मानदंड जांच रहे हैं...", "text_en": "Checking eligibility criteria..."},
            {"step": "generating_form", "text_hi": "भरा हुआ आवेदन फॉर्म तैयार कर रहे हैं...", "text_en": "Generating filled application form..."},
        ],
    }


# --- MCP Tools: Prisma-backed search_schemes + eligibility_matcher + generateFilledForm ---

SCHEME_KEYWORDS = {
    0: ["kisan", "farmer", "किसान", "pmkisan", "agriculture", "कृषि", "खेती", "land", "भूमि"],
    1: ["ayushman", "आयुष्मान", "health", "hospital", "स्वास्थ्य", "insurance", "बीमा", "pmjay"],
    2: ["sukanya", "सुकन्या", "girl", "बेटी", "beti", "daughter", "बालिका", "savings", "बचत"],
}
STOPWORDS = {"eligibility", "eligible", "criteria", "benefit", "benefits", "scheme", "yojana", "योजना",
    "how", "who", "what", "can", "get", "help", "tell", "about", "kya", "kaun", "kaise", "batao"}


async def search_schemes_prisma(query: str) -> dict:
    """MCP Tool 1: Query Prisma Scheme table."""
    t0 = _time.time()
    schemes = await prisma.scheme.find_many()
    query_lower = query.lower().strip()
    tokens = [t for t in re.split(r'[\s,;.!?\-/]+', query_lower) if len(t) > 2]
    specific = [t for t in tokens if t not in STOPWORDS]

    matched = []
    for scheme in schemes:
        searchable = f"{scheme.name.lower()} {scheme.eligibilityCriteriaText.lower()}"
        score = sum(1 for t in specific if t in searchable)
        # Also check SCHEME_KEYWORDS for legacy compat
        for kw_list in SCHEME_KEYWORDS.values():
            score += sum(1 for t in specific if any(t in kw or kw in t for kw in kw_list))
        if score >= 1:
            matched.append((scheme, score))
    matched.sort(key=lambda x: x[1], reverse=True)

    latency = int((_time.time() - t0) * 1000)
    if _agnost_key:
        try:
            agnost.track(user_id="tool", agent_name="nagarik_tool", input=query,
                output=str(bool(matched)), properties={"tool": "search_schemes"},
                success=bool(matched), latency=latency)
        except Exception:
            pass

    if not matched:
        return {"tool_name": "search_schemes", "tool_input": {"query": query},
            "documents_scanned": [s.name for s in schemes], "match_found": False,
            "result_text": "I don't know — criteria not explicitly stated in government PDFs."}

    results = []
    for scheme, _ in matched:
        results.append({
            "scheme_id": scheme.id, "scheme_title": scheme.name, "scheme_title_en": scheme.name,
            "eligibility": scheme.eligibilityCriteriaText,
            "benefits": scheme.eligibilityCriteriaText,
            "pdf_url": scheme.pdfUrl, "category": "government",
        })
    top = matched[0][0]
    return {"tool_name": "search_schemes", "tool_input": {"query": query},
        "documents_scanned": [s.name for s, _ in matched],
        "match_found": True, "matched_schemes": results,
        "result_text": f"Document scanned: {top.name}\n\n{top.eligibilityCriteriaText}"}


async def eligibility_matcher_prisma(user_id: str, scheme_name: str = "") -> dict:
    """MCP Tool 2: Fetch User profile + Schemes from Prisma, compare eligibility.
    Income in profile is YEARLY (सालाना). Defaults to Vidyasiri Scholarship."""
    t0 = _time.time()
    user = await prisma.user.find_unique(where={"id": user_id})
    if not user:
        return {"match_found": False, "results": [], "summary": "User not found"}
    profile = json.loads(user.profile) if isinstance(user.profile, str) and user.profile else (user.profile or {})
    name = profile.get("name", "")
    income_yearly = profile.get("income") or 0
    state = (profile.get("state") or "").lower()

    # First call search_schemes to scan documents (for Agnost tracking)
    await search_schemes_prisma("scholarship eligibility")

    # Default to Vidyasiri, then check all schemes
    vidyasiri = await prisma.scheme.find_first(where={"name": {"contains": "Vidyasiri"}})
    if scheme_name:
        schemes = await prisma.scheme.find_many(where={"name": {"contains": scheme_name}})
    else:
        schemes = await prisma.scheme.find_many()
    # Ensure Vidyasiri is first in the list
    if vidyasiri:
        schemes = [vidyasiri] + [s for s in schemes if s.id != vidyasiri.id]

    documents_scanned = [s.name for s in schemes]
    results = []

    for scheme in schemes:
        criteria_text = scheme.eligibilityCriteriaText.lower()
        eligible = True
        reasons = []

        # Parse yearly income limit from criteria text (e.g., "income < ₹1.5 lakh")
        income_matches = re.findall(r'(?:income\s*[<>]?\s*₹?|income\s*<?)\s*([\d,.]+)\s*(?:lakh|lac)', criteria_text)
        if income_matches:
            limit_lakh = float(income_matches[0].replace(",", ""))
            limit_yearly = int(limit_lakh * 100000)
            if income_yearly > limit_yearly:
                eligible = False
                reasons.append(f"सालाना आय ₹{income_yearly:,} — सीमा ₹{limit_yearly:,}/वर्ष (₹{limit_lakh} लाख) से अधिक")
            else:
                reasons.append(f"सालाना आय ₹{income_yearly:,} — सीमा ₹{limit_yearly:,}/वर्ष के अंदर — पात्र")

        # State check
        if "karnataka" in criteria_text:
            if state and "karnataka" not in state:
                eligible = False
                reasons.append(f"राज्य {profile.get('state', '')} — कर्नाटक निवासी आवश्यक")
            else:
                reasons.append("कर्नाटक निवासी — पात्र")

        # Education checks
        if "10th" in criteria_text or "10th pass" in criteria_text:
            reasons.append("10वीं पास या समकक्ष — आवश्यक")
        if "12th pass" in criteria_text:
            reasons.append("12वीं पास — आवश्यक")
        if "bpl" in criteria_text:
            reasons.append("बीपीएल श्रेणी — आवश्यक")
        if "no pucca house" in criteria_text:
            reasons.append("कोई पक्का मकान नहीं — आवश्यक")

        if not reasons:
            reasons.append("मानदंड मैच — विस्तार के लिए कार्यालय से संपर्क करें")

        results.append({
            "scheme": scheme.name, "scheme_hi": scheme.name, "scheme_id": scheme.id,
            "eligible": eligible, "reasons": reasons,
            "reason": "; ".join(reasons),
            "benefit": scheme.eligibilityCriteriaText,
        })

    latency = int((_time.time() - t0) * 1000)
    if _agnost_key:
        try:
            agnost.track(user_id=user_id, agent_name="nagarik_tool",
                input=json.dumps(profile, ensure_ascii=False, default=str),
                output=str(any(r["eligible"] for r in results)),
                properties={"tool": "eligibility_matcher"},
                success=any(r["eligible"] for r in results), latency=latency)
        except Exception:
            pass

    summary_lines = [f"नमस्ते {name}! प्रोफाइल आधारित पात्रता जांच:", ""]
    for r in results:
        icon = "+" if r["eligible"] else "-"
        summary_lines.append(f"[{icon}] {r['scheme']}: {'पात्र' if r['eligible'] else 'अपात्र'}")
        summary_lines.append(f"    कारण: {r['reason']}")
        if r["eligible"] and r.get("benefit"):
            summary_lines.append(f"    लाभ: {r['benefit']}")
        summary_lines.append("")

    return {"tool_name": "eligibility_matcher", "tool_input": {"user_id": user_id},
        "documents_scanned": documents_scanned, "match_found": len(results) > 0,
        "results": results, "summary": "\n".join(summary_lines)}


async def generate_filled_form(user_id: str, scheme_id: str) -> dict:
    """MCP Tool 3: Generate a filled application form PDF with Hindi fields."""
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
        profile=profile,
        scheme_name=scheme.name,
        scheme_criteria=scheme.eligibilityCriteriaText,
        output_path=pdf_path,
    )
    pdf_url = f"/api/pdf/{pdf_id}"

    # Create Application record
    try:
        await prisma.application.create(data={
            "userId": user_id, "schemeId": scheme_id,
            "status": "generated", "formUrl": pdf_url,
        })
    except Exception as e:
        logger.error(f"Application create failed: {e}")

    latency = int((_time.time() - t0) * 1000)
    if _agnost_key:
        try:
            agnost.track(user_id=user_id, agent_name="nagarik_tool",
                input=scheme.name, output=pdf_url,
                properties={"tool": "generate_filled_form", "scheme_id": scheme_id, "pdf_id": pdf_id},
                success=True, latency=latency)
        except Exception:
            pass

    return {"success": True, "pdf_url": pdf_url, "pdf_id": pdf_id,
        "scheme_name": scheme.name, "user_name": profile.get("name", "")}


# --- Legacy sync wrappers (for demo mode + bot response) ---

def search_schemes(query: str, language: str = "hi") -> dict:
    """Sync search using in-memory SCHEMES_SEED (for non-async contexts)."""
    query_lower = query.lower().strip()
    tokens = [t for t in re.split(r'[\s,;.!?\-/]+', query_lower) if len(t) > 2]
    specific = [t for t in tokens if t not in STOPWORDS]

    scores = {0: 0, 1: 0, 2: 0}
    for token in specific:
        for idx, keywords in SCHEME_KEYWORDS.items():
            if any(token in kw or kw in token for kw in keywords):
                scores[idx] += 1
    for idx, scheme in enumerate(SCHEMES_SEED):
        searchable = f"{scheme['title'].lower()} {scheme['title_hi']} {scheme['eligibility'].lower()} {scheme['eligibility_hi']}"
        for token in specific:
            if token in searchable:
                scores[idx] += 1

    matched = sorted([i for i, s in scores.items() if s >= 2], key=lambda i: scores[i], reverse=True)
    if not matched:
        return {"tool_name": "search_schemes", "tool_input": {"query": query},
            "documents_scanned": [s["title"] for s in SCHEMES_SEED], "match_found": False,
            "result_text": "I don't know — criteria not explicitly stated in government PDFs."}

    is_hi = language == "hi"
    results = []
    for idx in matched:
        s = SCHEMES_SEED[idx]
        results.append({"scheme_title": s["title_hi"] if is_hi else s["title"], "scheme_title_en": s["title"],
            "eligibility": s["eligibility_hi"] if is_hi else s["eligibility"],
            "benefits": s["benefits_hi"] if is_hi else s["benefits"],
            "pdf_url": s["pdf_url"], "category": s["category"]})
    top = SCHEMES_SEED[matched[0]]
    return {"tool_name": "search_schemes", "tool_input": {"query": query},
        "documents_scanned": [SCHEMES_SEED[i]["title"] for i in matched],
        "match_found": True, "matched_schemes": results,
        "result_text": f"Document scanned: {top['title']}\n\n{top['eligibility']}\n\nBenefits: {top['benefits']}"}


def eligibility_matcher(profile_data: dict, query: str = "") -> dict:
    """Sync eligibility matcher using in-memory rules."""
    age = profile_data.get("age", 0) or 0
    income = profile_data.get("income", 0) or 0
    name = profile_data.get("name", "")
    scheme_indices = [0, 1, 2]

    SCHEME_RULES = {
        0: {"scheme": "PM-KISAN Samman Nidhi", "scheme_hi": "पीएम-किसान सम्मान निधि",
            "criteria": {"income_limit": 200000, "min_age": 18, "requires": "cultivable_land"},
            "benefit": "₹6,000/year (₹2,000 every 4 months via DBT)"},
        1: {"scheme": "Ayushman Bharat (PM-JAY)", "scheme_hi": "आयुष्मान भारत (पीएम-जय)",
            "criteria": {"income_limit": 50000, "min_age": 0, "requires": "secc_2011_listing"},
            "benefit": "₹5,00,000/year health cover per family"},
        2: {"scheme": "Sukanya Samriddhi Yojana", "scheme_hi": "सुकन्या समृद्धि योजना",
            "criteria": {"income_limit": None, "min_age": 18, "requires": "girl_child_under_10"},
            "benefit": "~8.2% interest p.a., ₹1.5L tax deduction under 80C"},
    }

    results = []
    for idx in scheme_indices:
        rule = SCHEME_RULES[idx]
        criteria = rule["criteria"]
        reasons, eligible = [], True
        if criteria["min_age"] > 0 and age < criteria["min_age"]:
            eligible = False
            reasons.append(f"Age {age} below minimum {criteria['min_age']}")
        if criteria["income_limit"] is not None:
            if income > criteria["income_limit"]:
                eligible = False
                reasons.append(f"Income ₹{income:,}/month exceeds ₹{criteria['income_limit']:,}/month limit")
            else:
                reasons.append(f"Income ₹{income:,}/month within ₹{criteria['income_limit']:,}/month limit")
        req = criteria.get("requires", "")
        if req == "cultivable_land": reasons.append("Requires cultivable agricultural land")
        elif req == "secc_2011_listing": reasons.append("Requires SECC 2011 listing")
        elif req == "girl_child_under_10": reasons.append("Requires girl child below 10 years")
        results.append({"scheme": rule["scheme"], "scheme_hi": rule["scheme_hi"],
            "eligible": eligible, "reasons": reasons, "reason": "; ".join(reasons), "benefit": rule["benefit"]})

    summary_parts = [f"नमस्ते {name}! प्रोफाइल आधारित पात्रता:", ""]
    for r in results:
        summary_parts.append(f"[{'+' if r['eligible'] else '-'}] {r['scheme_hi']}: {'पात्र' if r['eligible'] else 'अपात्र'}")
        summary_parts.append(f"    कारण: {r['reason']}")
        if r["eligible"]: summary_parts.append(f"    लाभ: {r['benefit']}")
        summary_parts.append("")

    return {"tool_name": "eligibility_matcher", "tool_input": {"profile": profile_data},
        "documents_scanned": [r["scheme"] for r in results], "match_found": len(results) > 0,
        "results": results, "summary": "\n".join(summary_parts)}


# --- Bot response with MCP ---

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
        tool_result = search_schemes(content, language)
        latency = int((_time.time() - t0) * 1000)
        if _agnost_key:
            try:
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
        return {"content": resp, "tool_calls": [{"tool_name": "search_schemes", "tool_input": tool_result["tool_input"],
            "documents_scanned": tool_result["documents_scanned"], "match_found": tool_result["match_found"],
            "results": tool_result.get("matched_schemes", [])}]}

    return {"content": BOT_RESPONSES["default"]["hi"], "tool_calls": []}


# --- Startup / Shutdown ---

@app.on_event("startup")
async def startup():
    await prisma.connect()
    logger.info("Prisma connected")
    # Seed Prisma Scheme table (idempotent)
    count = await prisma.scheme.count()
    if count == 0:
        from prisma.seed import main as seed_main
        try:
            import asyncio
            # Seed inline
            for s in [
                {"name": "Pradhan Mantri Awas Yojana", "eligibilityCriteriaText": "Family income < ₹3 lakh per annum, no pucca house owned, rural or urban BPL category.", "pdfUrl": "https://pmaymis.gov.in/pdf/pmay_guidelines.pdf"},
                {"name": "Vidyasiri Scholarship", "eligibilityCriteriaText": "Karnataka resident, passed 10th or equivalent, family income < ₹1.5 lakh, studying in Karnataka.", "pdfUrl": "https://karnataka.gov.in/scholarship/vidyasiri.pdf"},
                {"name": "Vidya Lakshmi Education Loan", "eligibilityCriteriaText": "Indian citizen, 12th pass, pursuing higher education in approved institution.", "pdfUrl": "https://www.vidyalakshmi.co.in/files/guidelines.pdf"},
            ]:
                existing = await prisma.scheme.find_first(where={"name": s["name"]})
                if not existing:
                    await prisma.scheme.create(data=s)
        except Exception as e:
            logger.error(f"Seed failed: {e}")
    scheme_count = await prisma.scheme.count()
    logger.info(f"Prisma Scheme table: {scheme_count} records")


@app.on_event("shutdown")
async def shutdown():
    if _agnost_key:
        agnost.shutdown()
    await prisma.disconnect()
    motor_client.close()


# --- AUTH ROUTES ---

@api_router.post("/auth/send-otp", response_model=AuthResponse)
async def send_otp(req: SendOTPRequest):
    if not req.phone or len(req.phone) < 10:
        raise HTTPException(status_code=400, detail="Invalid phone number")
    await motor_db.otp_sessions.update_one(
        {"phone": req.phone},
        {"$set": {"phone": req.phone, "otp": "1234", "verified": False,
            "created_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True)
    return AuthResponse(success=True, message="OTP sent successfully")


@api_router.post("/auth/verify-otp", response_model=AuthResponse)
async def verify_otp(req: VerifyOTPRequest):
    if req.otp != "1234":
        return AuthResponse(success=False, message="Invalid OTP")
    session = await motor_db.otp_sessions.find_one({"phone": req.phone}, {"_id": 0})
    if not session:
        return AuthResponse(success=False, message="OTP session not found. Please request OTP first.")
    await motor_db.otp_sessions.update_one({"phone": req.phone}, {"$set": {"verified": True}})

    # Prisma User — find or create
    user = await prisma.user.find_unique(where={"phone": req.phone})
    if not user:
        user = await prisma.user.create(data={
            "phone": req.phone,
            "language": "hi",
            "profile": json.dumps({"name": "", "age": None, "income": None, "state": ""}, ensure_ascii=False),
        })
    return AuthResponse(success=True, message="OTP verified successfully", user_id=user.id, phone=req.phone)


# --- PROFILE ROUTES ---

@api_router.get("/profile/{user_id}")
async def get_profile(user_id: str):
    user = await prisma.user.find_unique(where={"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    profile = {}
    if user.profile:
        profile = json.loads(user.profile) if isinstance(user.profile, str) else user.profile
    return {
        "id": user.id, "phone": user.phone, "language": user.language,
        "name": profile.get("name", ""), "profile_data": profile,
        "profile_complete": profile.get("_complete", False),
        "created_at": user.createdAt.isoformat() if user.createdAt else "",
    }


@api_router.put("/profile/{user_id}")
async def update_profile(user_id: str, update: ProfileUpdate):
    user = await prisma.user.find_unique(where={"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    data = {}
    if update.language:
        data["language"] = update.language
    if update.profile_data:
        data["profile"] = json.dumps(update.profile_data, ensure_ascii=False)
    if data:
        user = await prisma.user.update(where={"id": user_id}, data=data)
    profile = json.loads(user.profile) if isinstance(user.profile, str) and user.profile else (user.profile or {})
    return {"id": user.id, "phone": user.phone, "language": user.language,
        "name": profile.get("name", ""), "profile_data": profile,
        "created_at": user.createdAt.isoformat() if user.createdAt else ""}


# --- SCHEMES ROUTES ---

@api_router.get("/schemes")
async def get_schemes():
    schemes = await prisma.scheme.find_many()
    return [{"id": s.id, "name": s.name, "title": s.name, "title_hi": s.name,
        "eligibility": s.eligibilityCriteriaText, "pdfUrl": s.pdfUrl,
        "description": s.eligibilityCriteriaText,
        **({k: v for k, v in SCHEMES_SEED[i].items() if k not in ("id",)} if i < len(SCHEMES_SEED) else {})}
        for i, s in enumerate(schemes)]


# --- CHAT ROUTES ---

@api_router.post("/chat")
async def send_chat_message(req: ChatMessageRequest):
    now = datetime.now(timezone.utc).isoformat()
    user_msg = {
        "id": str(uuid.uuid4()), "user_id": req.user_id, "role": "user",
        "content": req.content, "status": "sent", "created_at": now, "tool_calls": [],
    }
    await save_chat_prisma(req.user_id, user_msg, "user")

    # DEMO_MODE fast-path
    if DEMO_MODE and _is_demo_trigger(req.content):
        demo = demo_stage_response(req.user_id)
        bot_msg = {
            "id": str(uuid.uuid4()), "user_id": req.user_id, "role": "assistant",
            "content": demo["content"], "status": "delivered",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "tool_calls": demo.get("tool_calls", []), "type": demo.get("type", "profiler_complete"),
            "profiler_field": "", "eligibility_results": demo.get("eligibility_results", []),
            "pdf_url": demo.get("pdf_url", ""),
            "pdf_urls": demo.get("pdf_urls", []),
            "tool_progress": demo.get("tool_progress", []),
        }
        await save_chat_prisma(req.user_id, bot_msg, "agent")
        user_msg["status"] = "read"
        return {"user_message": user_msg, "bot_message": bot_msg}

    # Profiler agent
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

    # Normal MCP response
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


# --- VOICE / TRANSCRIBE ---

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
        try:
            from sarvamai import SarvamAI
            sarvam_client = SarvamAI(api_subscription_key=sarvam_key)
            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            # Transcribe in original language (auto-detect Hindi/English)
            with open(tmp_path, "rb") as f:
                resp_orig = sarvam_client.speech_to_text.transcribe(
                    file=f, model="saaras:v3", mode="transcribe"
                )
            original_text = resp_orig.transcript or ""

            # Translate to English if user prefers English, or get both
            if language == "en":
                transcript_en = original_text
                with open(tmp_path, "rb") as f:
                    resp_hi = sarvam_client.speech_to_text.transcribe(
                        file=f, model="saaras:v3", mode="transcribe", language_code="hi-IN"
                    )
                transcript_hi = resp_hi.transcript or original_text
            else:
                transcript_hi = original_text
                with open(tmp_path, "rb") as f:
                    resp_en = sarvam_client.speech_to_text.transcribe(
                        file=f, model="saaras:v3", mode="translate"
                    )
                transcript_en = resp_en.transcript or ""

            os.unlink(tmp_path)
            logger.info(f"Sarvam STT success: hi='{transcript_hi[:50]}' en='{transcript_en[:50]}'")
        except Exception as e:
            logger.error(f"Sarvam STT failed: {e}")

    # Mock fallback only if Sarvam produced nothing
    is_mock = False
    if not transcript_hi and not transcript_en:
        is_mock = True
        transcript_hi = "मेरा बेटा 10th पास है, कॉलेज के लिए पैसा चाहिए"
        transcript_en = "My son passed 10th, need money for college"

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

    # Use Hindi transcript for profiler (primary language), fall back to English
    query_text = transcript_hi or transcript_en
    profiler_result = await profiler_agent_respond(user_id, query_text) if user_id else None
    if profiler_result:
        bot_msg = {"id": str(uuid.uuid4()), "user_id": user_id, "role": "assistant",
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
        bot_msg = {"id": str(uuid.uuid4()), "user_id": user_id, "role": "assistant",
            "content": mcp["content"], "status": "delivered",
            "created_at": datetime.now(timezone.utc).isoformat(), "tool_calls": mcp["tool_calls"]}
    if user_id:
        await save_chat_prisma(user_id, bot_msg, "agent")

    if _agnost_key:
        try:
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


# --- MCP Tool Endpoints ---

@api_router.post("/search-schemes")
async def search_schemes_endpoint(req: SearchSchemesRequest):
    if DEMO_MODE and _is_demo_trigger(req.query):
        return {"tool_name": "search_schemes", "tool_input": {"query": req.query},
            "documents_scanned": ["Vidyasiri Scholarship Guidelines"], "match_found": True,
            "matched_schemes": [{"scheme_title": "विद्यासिरी छात्रवृत्ति", "scheme_title_en": "Vidyasiri Scholarship",
                "eligibility": "10th pass student, Karnataka domicile", "benefits": VIDYASIRI_RESULT["benefit"],
                "pdf_url": "https://sw.kar.nic.in/vidyasiri", "category": "education"}],
            "result_text": f"Vidyasiri Scholarship: {VIDYASIRI_RESULT['benefit']}"}
    # Use Prisma-backed search
    return await search_schemes_prisma(req.query)


@api_router.post("/eligibility-check")
async def eligibility_check_endpoint(req: EligibilityCheckRequest):
    if req.user_id:
        return await eligibility_matcher_prisma(req.user_id)
    # Fallback to sync matcher with inline profile
    profile = req.profile
    if not profile:
        raise HTTPException(status_code=400, detail="Provide user_id or profile object")
    result = eligibility_matcher(profile, req.query)
    return result


class FilledFormRequest(BaseModel):
    user_id: str
    scheme_id: str

@api_router.post("/generate-filled-form")
async def generate_filled_form_endpoint(req: FilledFormRequest):
    result = await generate_filled_form(req.user_id, req.scheme_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Form generation failed"))
    return result


# --- PDF ---

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
    matcher = eligibility_matcher(profile)
    results = matcher.get("results", [])
    if not results:
        raise HTTPException(status_code=400, detail="No eligibility results")
    pdf_id = str(uuid.uuid4())
    generate_eligibility_pdf(profile=profile, eligibility_results=results, output_path=str(PDF_DIR / f"{pdf_id}.pdf"))
    pdf_url = f"/api/pdf/{pdf_id}"
    if _agnost_key:
        try:
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
    pdf_path = PDF_DIR / f"{pdf_id}.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(path=str(pdf_path), media_type="application/pdf",
        filename=f"Nagarik_Sahayak_Report_{pdf_id[:8]}.pdf")


@api_router.get("/audio/{msg_id}")
async def serve_audio(msg_id: str):
    audio_path = AUDIO_DIR / f"{msg_id}.webm"
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio not found")
    return FileResponse(path=str(audio_path), media_type="audio/webm")


# --- Health / Analytics / Demo ---

@api_router.get("/")
async def root():
    return {"message": "Nagarik Sahayak API", "version": "2.0.0"}

@api_router.get("/analytics/status")
async def analytics_status():
    return {"enabled": bool(_agnost_key), "dashboard_url": "https://app.agnost.ai"}

@api_router.get("/demo/status")
async def demo_status():
    return {"demo_mode": DEMO_MODE}

@api_router.post("/demo/toggle")
async def demo_toggle():
    global DEMO_MODE
    DEMO_MODE = not DEMO_MODE
    return {"demo_mode": DEMO_MODE}


# --- Download All PDFs ---

@api_router.get("/download-all")
async def download_all_pdfs(user_id: str = ""):
    """Return list of all generated PDF URLs for a user, or generate a zip bundle."""
    apps = await prisma.application.find_many(
        where={"userId": user_id, "status": "generated"},
        order={"createdAt": "desc"},
    ) if user_id else []
    urls = []
    for app in apps:
        if app.formUrl:
            scheme = await prisma.scheme.find_unique(where={"id": app.schemeId}) if app.schemeId else None
            urls.append({"pdf_url": app.formUrl, "scheme_name": scheme.name if scheme else "Scheme"})
    if _agnost_key:
        try:
            agnost.track(user_id=user_id or "api", agent_name="nagarik_tool",
                input="download_all", output=str(len(urls)),
                properties={"tool": "multi_pdf_download", "scheme_count": len(urls), "user_id": user_id},
                success=True, latency=0)
        except Exception:
            pass
    return {"urls": urls, "count": len(urls)}


@api_router.get("/download-all-zip")
async def download_all_zip(user_id: str = ""):
    """Generate a zip of all generated PDFs for a user."""
    import zipfile as zf
    apps = await prisma.application.find_many(
        where={"userId": user_id, "status": "generated"},
        order={"createdAt": "desc"},
    ) if user_id else []
    zip_id = str(uuid.uuid4())
    zip_path = PDF_DIR / f"{zip_id}.zip"
    with zf.ZipFile(zip_path, "w", zf.ZIP_DEFLATED) as z:
        for app in apps:
            if app.formUrl:
                pdf_id = app.formUrl.split("/")[-1]
                pdf_file = PDF_DIR / f"{pdf_id}.pdf"
                if pdf_file.exists():
                    scheme = await prisma.scheme.find_unique(where={"id": app.schemeId}) if app.schemeId else None
                    name = (scheme.name if scheme else "Scheme").replace(" ", "_")
                    z.write(pdf_file, f"{name}_Form.pdf")
    if _agnost_key:
        try:
            agnost.track(user_id=user_id or "api", agent_name="nagarik_tool",
                input="download_all_zip", output=str(len(apps)),
                properties={"tool": "multi_pdf_download", "scheme_count": len(apps), "user_id": user_id, "format": "zip"},
                success=True, latency=0)
        except Exception:
            pass
    return FileResponse(path=str(zip_path), media_type="application/zip",
        filename="Nagarik_Sahayak_Forms.zip")


# --- PDF Upload for RAG ---

UPLOADS_DIR = PDF_DIR  # reuse the same directory

@api_router.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...), user_id: str = Form("")):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")
    file_bytes = await file.read()
    if len(file_bytes) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")
    pdf_id = str(uuid.uuid4())
    safe_name = file.filename.replace(" ", "_")
    pdf_path = UPLOADS_DIR / f"{pdf_id}.pdf"
    with open(pdf_path, "wb") as f:
        f.write(file_bytes)
    pdf_url = f"/api/pdf/{pdf_id}"
    logger.info(f"PDF uploaded: {safe_name} -> {pdf_id} by user {user_id}")
    if _agnost_key:
        try:
            agnost.track(user_id=user_id or "api", agent_name="nagarik_tool",
                input=safe_name, output=pdf_url,
                properties={"tool": "upload_pdf", "filename": safe_name, "size": len(file_bytes)},
                success=True, latency=0)
        except Exception:
            pass
    return {"success": True, "pdf_id": pdf_id, "pdf_url": pdf_url, "filename": safe_name,
        "size": len(file_bytes)}


# --- New Chat / Reset Profiler ---

@api_router.post("/chat/reset")
async def reset_chat(req: dict = {}):
    user_id = req.get("user_id", "")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id required")
    # Reset user profile (clear profiler progress)
    try:
        await prisma.user.update(where={"id": user_id}, data={
            "profile": json.dumps({})
        })
    except Exception as e:
        logger.error(f"Profile reset failed: {e}")
    # Delete chat logs for this user
    try:
        await prisma.chatlog.delete_many(where={"userId": user_id})
    except Exception as e:
        logger.error(f"Chat history clear failed: {e}")
    logger.info(f"Chat reset for user {user_id}")
    return {"success": True, "message": "Chat reset. Profile cleared."}


# --- Mount ---

app.include_router(api_router)
app.add_middleware(CORSMiddleware, allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"], allow_headers=["*"])
