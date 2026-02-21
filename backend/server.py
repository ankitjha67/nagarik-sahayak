from fastapi import FastAPI, APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import tempfile
import uuid
import re
import base64
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

AUDIO_DIR = ROOT_DIR / "audio_files"
AUDIO_DIR.mkdir(exist_ok=True)

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app
app = FastAPI()
api_router = APIRouter(prefix="/api")

# LLM Configuration Placeholders
LLM_PROVIDERS = {
    "openai": {
        "name": "OpenAI",
        "models": ["gpt-5.2", "gpt-4o", "gpt-4o-mini"],
        "api_key_env": "OPENAI_API_KEY",
        "status": "placeholder"
    },
    "anthropic": {
        "name": "Anthropic",
        "models": ["claude-sonnet-4.5", "claude-opus-4.5", "claude-haiku-4.5"],
        "api_key_env": "ANTHROPIC_API_KEY",
        "status": "placeholder"
    },
    "google": {
        "name": "Google",
        "models": ["gemini-3-flash", "gemini-3-pro"],
        "api_key_env": "GOOGLE_API_KEY",
        "status": "placeholder"
    },
    "mistral": {
        "name": "Mistral AI",
        "models": ["mistral-large", "mistral-medium", "mistral-small"],
        "api_key_env": "MISTRAL_API_KEY",
        "status": "placeholder"
    },
    "meta": {
        "name": "Meta (Open Source)",
        "models": ["llama-3.3-70b", "llama-3.1-405b"],
        "api_key_env": "META_API_KEY",
        "status": "placeholder"
    },
    "cohere": {
        "name": "Cohere",
        "models": ["command-r-plus", "command-r"],
        "api_key_env": "COHERE_API_KEY",
        "status": "placeholder"
    }
}

# STT Configuration
STT_PROVIDERS = {
    "openai_whisper": {
        "name": "OpenAI Whisper",
        "model": "whisper-1",
        "status": "active",
        "api_key_env": "EMERGENT_LLM_KEY"
    },
    "sarvam": {
        "name": "Sarvam AI",
        "model": "saaras:v3",
        "status": "placeholder",
        "api_key_env": "SARVAM_API_KEY"
    }
}

# Logging
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

class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    user_id: str
    role: str
    content: str
    status: str
    created_at: str

class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    language: Optional[str] = None
    profile_data: Optional[Dict[str, Any]] = None

class ProfileResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    phone: str
    name: str
    language: str
    created_at: str

class SchemeResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    title: str
    title_hi: str
    description: str
    description_hi: str
    eligibility: str
    eligibility_hi: str
    benefits: str
    benefits_hi: str
    pdf_url: str
    icon: str
    category: str

class SearchSchemesRequest(BaseModel):
    query: str

# --- MCP Tool Registry (Simulated) ---

MCP_TOOLS = [
    {
        "name": "search_schemes",
        "description": "Search government scheme PDFs/documents for eligibility criteria and scheme details. Scans seeded document text and returns matching eligibility information.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural-language search query about a government scheme, eligibility, or benefit"
                }
            },
            "required": ["query"]
        }
    }
]

# --- Seed Data ---

SCHEMES_SEED = [
    {
        "id": str(uuid.uuid4()),
        "title": "PM-KISAN Samman Nidhi",
        "title_hi": "पीएम-किसान सम्मान निधि",
        "description": "Financial benefit of Rs 6,000/- per year to eligible farmer families, payable in three equal installments of Rs 2,000.",
        "description_hi": "पात्र किसान परिवारों को प्रति वर्ष 6,000 रुपये की वित्तीय सहायता, 2,000 रुपये की तीन समान किस्तों में देय।",
        "eligibility": "All landholding farmer families with cultivable land. Excludes institutional landholders, former/present holders of constitutional posts, serving/retired officers and employees of Central/State Government Ministries, current Members of Parliament/State Legislatures, professionals registered with professional bodies, and income tax payers in the last assessment year.",
        "eligibility_hi": "खेती योग्य भूमि वाले सभी भूमिधारक किसान परिवार। संस्थागत भूमिधारक, संवैधानिक पदों के पूर्व/वर्तमान धारक, केंद्र/राज्य सरकार के सेवारत/सेवानिवृत्त अधिकारी, वर्तमान सांसद/विधायक, पेशेवर निकायों में पंजीकृत पेशेवर और पिछले मूल्यांकन वर्ष में आयकर दाता इस योजना से बाहर हैं।",
        "benefits": "Rs 2,000 every 4 months directly into bank account via Direct Benefit Transfer (DBT). Total Rs 6,000 per year.",
        "benefits_hi": "प्रत्यक्ष लाभ हस्तांतरण (DBT) के माध्यम से हर 4 महीने में सीधे बैंक खाते में 2,000 रुपये। कुल 6,000 रुपये प्रति वर्ष।",
        "pdf_url": "https://pmkisan.gov.in/Documents/RevisedPM-KISANOperationalGuidelines.pdf",
        "icon": "sprout",
        "category": "agriculture"
    },
    {
        "id": str(uuid.uuid4()),
        "title": "Ayushman Bharat (PM-JAY)",
        "title_hi": "आयुष्मान भारत (पीएम-जय)",
        "description": "World's largest health insurance scheme providing health cover of Rs 5 lakh per family per year for secondary and tertiary care hospitalization.",
        "description_hi": "विश्व की सबसे बड़ी स्वास्थ्य बीमा योजना जो प्रति परिवार प्रति वर्ष 5 लाख रुपये का स्वास्थ्य कवर द्वितीयक और तृतीयक देखभाल अस्पताल में भर्ती के लिए प्रदान करती है।",
        "eligibility": "Families identified based on deprivation and occupational criteria of Socio-Economic Caste Census 2011 (SECC 2011). No cap on family size, age, or gender. Covers pre-existing conditions from day one.",
        "eligibility_hi": "सामाजिक-आर्थिक जाति जनगणना 2011 (SECC 2011) के वंचन और व्यावसायिक मानदंडों के आधार पर पहचाने गए परिवार। परिवार के आकार, उम्र या लिंग पर कोई सीमा नहीं। पहले दिन से पहले से मौजूद बीमारियों को कवर करता है।",
        "benefits": "Rs 5 Lakh health cover per family per year. Cashless and paperless treatment at empanelled hospitals. Covers 1,929 procedures including surgeries, medical and day care treatments.",
        "benefits_hi": "प्रति परिवार प्रति वर्ष 5 लाख रुपये का स्वास्थ्य कवर। सूचीबद्ध अस्पतालों में कैशलेस और पेपरलेस उपचार। सर्जरी, चिकित्सा और डे केयर उपचार सहित 1,929 प्रक्रियाओं को कवर करता है।",
        "pdf_url": "https://pmjay.gov.in/sites/default/files/2019-09/Guideline-English.pdf",
        "icon": "heart-pulse",
        "category": "health"
    },
    {
        "id": str(uuid.uuid4()),
        "title": "Sukanya Samriddhi Yojana",
        "title_hi": "सुकन्या समृद्धि योजना",
        "description": "Small savings scheme for the girl child, launched as part of the 'Beti Bachao Beti Padhao' campaign, offering high interest rates and tax benefits.",
        "description_hi": "बालिकाओं के लिए लघु बचत योजना, 'बेटी बचाओ बेटी पढ़ाओ' अभियान के तहत शुरू की गई, उच्च ब्याज दरें और कर लाभ प्रदान करती है।",
        "eligibility": "Parents or legal guardians can open account for a girl child below 10 years of age. Maximum two accounts allowed per family (one per girl child). A third account is permitted only in case of twins/triplets.",
        "eligibility_hi": "माता-पिता या कानूनी अभिभावक 10 वर्ष से कम आयु की बालिका के लिए खाता खोल सकते हैं। प्रति परिवार अधिकतम दो खाते (प्रति बालिका एक) की अनुमति है। तीसरा खाता केवल जुड़वां/तीन बच्चों के मामले में अनुमति है।",
        "benefits": "Current interest rate ~8.2% per annum (Q1 FY 2024-25). Tax deduction under Section 80C up to Rs 1.5 lakh. Minimum deposit Rs 250, maximum Rs 1.5 lakh per year. Account matures when the girl turns 21.",
        "benefits_hi": "वर्तमान ब्याज दर ~8.2% प्रति वर्ष (Q1 FY 2024-25)। धारा 80C के तहत 1.5 लाख रुपये तक कर कटौती। न्यूनतम जमा 250 रुपये, अधिकतम 1.5 लाख रुपये प्रति वर्ष। बालिका के 21 वर्ष की होने पर खाता परिपक्व होता है।",
        "pdf_url": "https://www.india.gov.in/sukanya-samriddhi-yojna",
        "icon": "baby",
        "category": "savings"
    }
]

# Bot response templates
BOT_RESPONSES = {
    "greeting": {
        "hi": "नमस्ते! मैं नागरिक सहायक हूँ। मैं आपकी सरकारी योजनाओं और सेवाओं में मदद कर सकता हूँ। आप मुझसे किसी भी योजना के बारे में पूछ सकते हैं।",
        "en": "Namaste! I am Nagarik Sahayak. I can help you with government schemes and services. You can ask me about any scheme."
    },
    "schemes": {
        "hi": "हमारे पास 3 प्रमुख योजनाएं उपलब्ध हैं:\n\n1. पीएम-किसान सम्मान निधि - किसानों के लिए 6,000 रुपये/वर्ष\n2. आयुष्मान भारत (पीएम-जय) - 5 लाख रुपये स्वास्थ्य बीमा\n3. सुकन्या समृद्धि योजना - बालिकाओं के लिए बचत योजना\n\nकिसी योजना के बारे में विस्तार से जानने के लिए उसका नाम लिखें।",
        "en": "We have 3 major schemes available:\n\n1. PM-KISAN Samman Nidhi - Rs 6,000/year for farmers\n2. Ayushman Bharat (PM-JAY) - Rs 5 Lakh health insurance\n3. Sukanya Samriddhi Yojana - Savings scheme for girl child\n\nType the scheme name to know more."
    },
    "default": {
        "hi": "धन्यवाद! मैं आपकी बात समझ रहा हूँ। अभी मैं सीमित जानकारी दे सकता हूँ। कृपया 'योजनाएं' टाइप करें सभी उपलब्ध योजनाओं को देखने के लिए, या किसी विशिष्ट योजना का नाम लिखें।",
        "en": "Thank you! I understand. Currently I can provide limited information. Please type 'schemes' to see all available schemes, or type a specific scheme name."
    },
    "pmkisan": {
        "hi": "पीएम-किसान सम्मान निधि:\n\nलाभ: प्रति वर्ष 6,000 रुपये, हर 4 महीने में 2,000 रुपये सीधे बैंक खाते में।\n\nपात्रता: खेती योग्य भूमि वाले सभी किसान परिवार।\n\nआवेदन: pmkisan.gov.in पर जाएं या नजदीकी CSC केंद्र पर जाएं।",
        "en": "PM-KISAN Samman Nidhi:\n\nBenefit: Rs 6,000 per year, Rs 2,000 every 4 months directly to bank account.\n\nEligibility: All farmer families with cultivable land.\n\nApply: Visit pmkisan.gov.in or nearest CSC center."
    },
    "ayushman": {
        "hi": "आयुष्मान भारत (पीएम-जय):\n\nलाभ: प्रति परिवार प्रति वर्ष 5 लाख रुपये का स्वास्थ्य कवर।\n\nपात्रता: SECC 2011 के आधार पर चयनित परिवार।\n\nआवेदन: mera.pmjay.gov.in पर पात्रता जांचें या 14555 पर कॉल करें।",
        "en": "Ayushman Bharat (PM-JAY):\n\nBenefit: Rs 5 Lakh health cover per family per year.\n\nEligibility: Families selected based on SECC 2011.\n\nApply: Check eligibility at mera.pmjay.gov.in or call 14555."
    },
    "sukanya": {
        "hi": "सुकन्या समृद्धि योजना:\n\nलाभ: ~8.2% ब्याज दर, धारा 80C के तहत कर लाभ।\n\nपात्रता: 10 वर्ष से कम आयु की बालिका।\n\nआवेदन: किसी भी पोस्ट ऑफिस या बैंक में खाता खोलें।",
        "en": "Sukanya Samriddhi Yojana:\n\nBenefit: ~8.2% interest rate, tax benefits under Section 80C.\n\nEligibility: Girl child below 10 years.\n\nApply: Open account at any post office or bank."
    }
}


def search_schemes(query: str, language: str = "hi") -> dict:
    """
    MCP Tool: search_schemes
    Scans seeded scheme document text for matching eligibility & criteria.
    Returns structured result with document scan info.
    """
    query_lower = query.lower().strip()
    # Tokenize query — remove Hindi stopwords and short tokens
    tokens = re.split(r'[\s,;.!?\-/]+', query_lower)
    tokens = [t for t in tokens if len(t) > 2]

    # Generic stopwords that appear in all schemes — don't use for scoring
    STOPWORDS = {
        "eligibility", "eligible", "eligib", "criteria", "benefit", "benefits",
        "apply", "application", "document", "pdf", "scheme", "yojana", "योजना",
        "पात्र", "पात्रता", "लाभ", "आवेदन", "दस्तावेज", "मापदंड",
        "how", "who", "what", "can", "get", "help", "tell", "about",
        "kya", "kaun", "kaise", "batao", "bataiye",
    }
    # Scheme-specific tokens (after removing stopwords)
    specific_tokens = [t for t in tokens if t not in STOPWORDS]

    # Search keywords mapped to schemes
    SCHEME_KEYWORDS = {
        0: ["kisan", "farmer", "किसान", "pm-kisan", "pmkisan", "agriculture",
            "कृषि", "खेती", "land", "भूमि", "6000", "dbt", "किस्त"],
        1: ["ayushman", "आयुष्मान", "health", "hospital", "स्वास्थ्य",
            "insurance", "बीमा", "pmjay", "pm-jay", "lakh", "लाख",
            "treatment", "इलाज", "surgery", "अस्पताल", "secc", "cashless"],
        2: ["sukanya", "सुकन्या", "girl", "बेटी", "beti", "daughter",
            "बालिका", "savings", "बचत", "interest", "ब्याज", "80c",
            "samriddhi", "समृद्धि", "child", "बच्ची"],
    }

    # Score each scheme using SPECIFIC tokens only (no stopwords)
    scores = {0: 0, 1: 0, 2: 0}
    for token in specific_tokens:
        for idx, keywords in SCHEME_KEYWORDS.items():
            for kw in keywords:
                if token in kw or kw in token:
                    scores[idx] += 1

    # Also check against actual scheme text fields — but only with specific tokens
    for idx, scheme in enumerate(SCHEMES_SEED):
        searchable = " ".join([
            scheme["title"].lower(),
            scheme["title_hi"],
            scheme["description"].lower(),
            scheme["description_hi"],
            scheme["eligibility"].lower(),
            scheme["eligibility_hi"],
            scheme["benefits"].lower(),
            scheme["benefits_hi"],
        ])
        for token in specific_tokens:
            if token in searchable:
                scores[idx] += 1

    # Require at least 2 score to count as a match (avoids false positives)
    matched_indices = [i for i, s in scores.items() if s >= 2]
    # Sort by score descending
    matched_indices.sort(key=lambda i: scores[i], reverse=True)

    if not matched_indices:
        return {
            "tool_name": "search_schemes",
            "tool_input": {"query": query},
            "documents_scanned": [s["title"] for s in SCHEMES_SEED],
            "match_found": False,
            "result_text": "I don't know — criteria not explicitly stated in PDFs.",
            "result_text_hi": "मुझे जानकारी नहीं मिली — पीडीएफ दस्तावेजों में यह मापदंड स्पष्ट रूप से नहीं बताया गया है।",
        }

    # Build response from top match(es)
    results = []
    for idx in matched_indices:
        scheme = SCHEMES_SEED[idx]
        is_hi = language == "hi"
        results.append({
            "scheme_title": scheme["title_hi"] if is_hi else scheme["title"],
            "scheme_title_en": scheme["title"],
            "eligibility": scheme["eligibility_hi"] if is_hi else scheme["eligibility"],
            "benefits": scheme["benefits_hi"] if is_hi else scheme["benefits"],
            "pdf_url": scheme["pdf_url"],
            "category": scheme["category"],
        })

    return {
        "tool_name": "search_schemes",
        "tool_input": {"query": query},
        "documents_scanned": [s["title"] for s in SCHEMES_SEED],
        "match_found": True,
        "matched_schemes": results,
        "result_text": _format_mcp_result(results, language),
    }


def _format_mcp_result(results: list, language: str) -> str:
    """Format MCP search results into readable text."""
    parts = []
    for r in results:
        name = r["scheme_title"]
        if language == "hi":
            parts.append(
                f"Document scanned: {r['scheme_title_en']}\n\n"
                f"{name}:\n"
                f"पात्रता: {r['eligibility']}\n\n"
                f"लाभ: {r['benefits']}\n"
                f"PDF: {r['pdf_url']}"
            )
        else:
            parts.append(
                f"Document scanned: {r['scheme_title_en']}\n\n"
                f"Eligibility: {r['eligibility']}\n\n"
                f"Benefits: {r['benefits']}\n"
                f"PDF: {r['pdf_url']}"
            )
    return "\n\n---\n\n".join(parts)


def get_bot_response_with_mcp(content: str, language: str = "hi") -> dict:
    """
    Enhanced bot response that simulates MCP tool calling.
    Returns dict with response text + optional tool_calls trace.
    """
    content_lower = content.lower().strip()

    # Pure greetings — no tool needed
    if any(w in content_lower for w in ["hello", "hi", "namaste", "नमस्ते", "हैलो", "हेलो"]):
        return {
            "content": BOT_RESPONSES["greeting"].get(language, BOT_RESPONSES["greeting"]["hi"]),
            "tool_calls": [],
        }

    # Listing all schemes — no document scan needed
    if content_lower in ["scheme", "schemes", "योजना", "योजनाएं", "yojana", "योजनाएं दिखाओ"]:
        return {
            "content": BOT_RESPONSES["schemes"].get(language, BOT_RESPONSES["schemes"]["hi"]),
            "tool_calls": [],
        }

    # Check if query is about a scheme / eligibility / benefits → invoke MCP tool
    scheme_signals = [
        "kisan", "farmer", "किसान", "pm-kisan", "pmkisan", "agriculture", "कृषि", "खेती",
        "ayushman", "आयुष्मान", "health", "hospital", "स्वास्थ्य", "insurance", "बीमा", "pmjay",
        "sukanya", "सुकन्या", "girl", "बेटी", "beti", "daughter", "बालिका", "savings", "बचत",
        "eligib", "पात्र", "benefit", "लाभ", "apply", "आवेदन", "criteria", "मापदंड",
        "document", "pdf", "दस्तावेज", "scheme", "योजना", "yojana",
        "who can", "kaun", "कौन", "how to", "kaise", "कैसे",
    ]

    needs_tool = any(sig in content_lower for sig in scheme_signals)

    if needs_tool:
        tool_result = search_schemes(content, language)
        tool_call_trace = {
            "tool_name": "search_schemes",
            "tool_input": tool_result["tool_input"],
            "documents_scanned": tool_result["documents_scanned"],
            "match_found": tool_result["match_found"],
        }

        if tool_result["match_found"]:
            response_text = tool_result["result_text"]
        else:
            if language == "hi":
                response_text = tool_result["result_text_hi"]
            else:
                response_text = tool_result["result_text"]

        return {
            "content": response_text,
            "tool_calls": [tool_call_trace],
        }

    # Default fallback — no tool needed
    return {
        "content": BOT_RESPONSES["default"].get(language, BOT_RESPONSES["default"]["hi"]),
        "tool_calls": [],
    }


# --- PROFILER AGENT ---

PROFILE_FIELDS = ["name", "age", "income", "state"]

PROFILER_QUESTIONS = {
    "name": "आपका नाम क्या है?",
    "age": "आपकी उम्र क्या है? (संख्या में बताएं)",
    "income": "आपकी मासिक आय कितनी है? (रुपये में, जैसे 15000)",
    "state": "आपका राज्य कौन सा है? (जैसे उत्तर प्रदेश, बिहार, महाराष्ट्र)",
}

INDIAN_STATES = [
    "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh",
    "goa", "gujarat", "haryana", "himachal pradesh", "jharkhand", "karnataka",
    "kerala", "madhya pradesh", "maharashtra", "manipur", "meghalaya", "mizoram",
    "nagaland", "odisha", "punjab", "rajasthan", "sikkim", "tamil nadu",
    "telangana", "tripura", "uttar pradesh", "uttarakhand", "west bengal",
    "delhi", "jammu and kashmir", "ladakh", "chandigarh", "puducherry",
    # Hindi names
    "आंध्र प्रदेश", "अरुणाचल प्रदेश", "असम", "बिहार", "छत्तीसगढ़",
    "गोवा", "गुजरात", "हरियाणा", "हिमाचल प्रदेश", "झारखंड", "कर्नाटक",
    "केरल", "मध्य प्रदेश", "महाराष्ट्र", "मणिपुर", "मेघालय", "मिजोरम",
    "नागालैंड", "ओडिशा", "पंजाब", "राजस्थान", "सिक्किम", "तमिलनाडु",
    "तेलंगाना", "त्रिपुरा", "उत्तर प्रदेश", "उत्तराखंड", "पश्चिम बंगाल",
    "दिल्ली", "जम्मू और कश्मीर", "लद्दाख", "चंडीगढ़", "पुडुचेरी",
]


def get_next_missing_field(profile_data: dict) -> str:
    """Returns the first incomplete profile field, or '' if all complete."""
    if not profile_data:
        return "name"
    for field in PROFILE_FIELDS:
        val = profile_data.get(field)
        if val is None or val == "" or val == 0:
            return field
    return ""


def parse_profile_answer(field: str, answer: str) -> tuple:
    """Parse user's answer for a profile field. Returns (value, error_msg)."""
    answer = answer.strip()
    if not answer:
        return None, "कृपया उत्तर दें।"

    if field == "name":
        # Accept any non-empty string
        cleaned = re.sub(r'[^\w\s\u0900-\u097F]', '', answer).strip()
        if len(cleaned) < 2:
            return None, "कृपया अपना पूरा नाम बताएं।"
        return cleaned, None

    if field == "age":
        # Extract number
        nums = re.findall(r'\d+', answer)
        if nums:
            age = int(nums[0])
            if 1 <= age <= 120:
                return age, None
        return None, "कृपया अपनी उम्र संख्या में बताएं (जैसे 35)।"

    if field == "income":
        # Extract number, handle lakhs
        answer_lower = answer.lower().replace(',', '').replace('₹', '').replace('rs', '').replace('रुपये', '').replace('रू', '').strip()
        nums = re.findall(r'\d+', answer_lower)
        if nums:
            income = int(nums[0])
            if "lakh" in answer_lower or "लाख" in answer:
                income *= 100000
            elif income < 100 and income > 0:
                # Probably meant in thousands
                income *= 1000
            return income, None
        return None, "कृपया अपनी मासिक आय रुपये में बताएं (जैसे 15000)।"

    if field == "state":
        # Try to match against known states
        answer_lower = answer.lower().strip()
        for state in INDIAN_STATES:
            if state in answer_lower or answer_lower in state:
                return answer.strip(), None
        # Accept anyway if it looks reasonable
        if len(answer) >= 2:
            return answer.strip(), None
        return None, "कृपया अपने राज्य का नाम बताएं (जैसे उत्तर प्रदेश)।"

    return answer, None


def check_eligibility(profile_data: dict) -> str:
    """Check eligibility for all 3 schemes based on profile data."""
    age = profile_data.get("age", 0) or 0
    income = profile_data.get("income", 0) or 0
    name = profile_data.get("name", "")
    _state = profile_data.get("state", "")  # reserved for state-specific rules

    results = []
    results.append(f"नमस्ते {name}! आपकी प्रोफाइल के आधार पर पात्रता:")
    results.append("")

    # PM-KISAN: farmers with land, income < 2L/month typically
    if income <= 200000:
        results.append("1. पीएम-किसान सम्मान निधि: पात्र हो सकते हैं")
        results.append("   लाभ: 6,000 रुपये/वर्ष (2,000 रुपये हर 4 महीने)")
        results.append("   शर्त: खेती योग्य भूमि होनी चाहिए")
    else:
        results.append("1. पीएम-किसान सम्मान निधि: आय अधिक होने पर पात्र नहीं")

    results.append("")

    # Ayushman Bharat: SECC 2011, generally low income
    if income <= 50000:
        results.append("2. आयुष्मान भारत (पीएम-जय): पात्र हो सकते हैं")
        results.append("   लाभ: 5 लाख रुपये/वर्ष स्वास्थ्य कवर")
        results.append("   शर्त: SECC 2011 सूची में होना आवश्यक")
    else:
        results.append("2. आयुष्मान भारत (पीएम-जय): आय सीमा से अधिक, संभवत: पात्र नहीं")

    results.append("")

    # Sukanya Samriddhi: needs girl child < 10
    if age >= 18:
        results.append("3. सुकन्या समृद्धि योजना: आप माता-पिता/अभिभावक के रूप में खोल सकते हैं")
        results.append("   लाभ: ~8.2% ब्याज, धारा 80C कर लाभ")
        results.append("   शर्त: 10 वर्ष से कम आयु की बालिका होनी चाहिए")
    else:
        results.append("3. सुकन्या समृद्धि योजना: उम्र कम होने पर स्वयं आवेदन नहीं कर सकते")

    results.append("")
    results.append("अधिक जानकारी के लिए किसी योजना का नाम लिखें।")

    return "\n".join(results)


async def profiler_agent_respond(user_id: str, content: str) -> dict:
    """
    Profiler Agent: checks if profile is incomplete, asks ONE question at a time.
    Returns None if profile is complete (let normal chat handle it).
    Returns response dict if profiler is active.
    """
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        return None

    profile_data = user.get("profile_data", {})
    if not profile_data:
        profile_data = {"name": "", "age": None, "income": None, "state": ""}
        await db.users.update_one({"id": user_id}, {"$set": {
            "profile_data": profile_data,
            "profile_complete": False,
        }})

    is_complete = user.get("profile_complete", False)
    if is_complete:
        return None  # Profile done, use normal chat

    pending_field = get_next_missing_field(profile_data)
    if not pending_field:
        # All fields filled — mark complete + run eligibility
        await db.users.update_one({"id": user_id}, {"$set": {"profile_complete": True}})
        return None

    # Check if user is greeting — greet back + ask the question
    content_lower = content.lower().strip()
    is_greeting = any(w in content_lower for w in ["hello", "hi", "namaste", "नमस्ते", "हैलो", "हेलो", "start"])

    # Check which field we were previously asking (from last bot message)
    last_bot = await db.chat_logs.find_one(
        {"user_id": user_id, "role": "assistant", "type": "profiler"},
        {"_id": 0},
        sort=[("created_at", -1)]
    )
    asked_field = last_bot.get("profiler_field", "") if last_bot else ""

    if is_greeting or not asked_field:
        # First interaction or greeting — ask the first missing field
        greeting = "नमस्ते! मैं नागरिक सहायक हूँ।\nआपकी पात्रता जांचने के लिए मुझे कुछ जानकारी चाहिए।\n\n"
        return {
            "content": greeting + PROFILER_QUESTIONS[pending_field],
            "tool_calls": [],
            "type": "profiler",
            "profiler_field": pending_field,
        }

    # User is answering a question — parse the answer for the asked field
    if asked_field in PROFILE_FIELDS:
        value, error = parse_profile_answer(asked_field, content)
        if error:
            return {
                "content": error + "\n\n" + PROFILER_QUESTIONS[asked_field],
                "tool_calls": [],
                "type": "profiler",
                "profiler_field": asked_field,
            }

        # Save the value
        profile_data[asked_field] = value
        if asked_field == "name":
            await db.users.update_one({"id": user_id}, {"$set": {
                f"profile_data.{asked_field}": value,
                "name": value,
            }})
        else:
            await db.users.update_one({"id": user_id}, {"$set": {
                f"profile_data.{asked_field}": value,
            }})

        # Check next field
        next_field = get_next_missing_field(profile_data)
        if not next_field:
            # Profile complete! Auto-trigger eligibility
            await db.users.update_one({"id": user_id}, {"$set": {"profile_complete": True}})
            eligibility_text = check_eligibility(profile_data)
            return {
                "content": f"धन्यवाद! आपकी प्रोफाइल पूरी हो गई।\n\n{eligibility_text}",
                "tool_calls": [{
                    "tool_name": "check_eligibility",
                    "tool_input": {"profile": profile_data},
                    "documents_scanned": [s["title"] for s in SCHEMES_SEED],
                    "match_found": True,
                }],
                "type": "profiler_complete",
                "profiler_field": "",
            }
        else:
            confirm = ""
            if asked_field == "name":
                confirm = f"धन्यवाद, {value}!\n\n"
            elif asked_field == "age":
                confirm = f"उम्र: {value} वर्ष। ठीक है।\n\n"
            elif asked_field == "income":
                confirm = f"मासिक आय: ₹{value:,}। ठीक है।\n\n"

            return {
                "content": confirm + PROFILER_QUESTIONS[next_field],
                "tool_calls": [],
                "type": "profiler",
                "profiler_field": next_field,
            }

    # Fallback — ask the pending field
    return {
        "content": PROFILER_QUESTIONS[pending_field],
        "tool_calls": [],
        "type": "profiler",
        "profiler_field": pending_field,
    }


# --- Startup Event: Seed Schemes ---

@app.on_event("startup")
async def seed_schemes():
    count = await db.schemes.count_documents({})
    if count == 0:
        await db.schemes.insert_many(SCHEMES_SEED)
        logger.info("Seeded 3 government schemes")
    else:
        logger.info(f"Schemes collection already has {count} documents")


# --- AUTH ROUTES ---

@api_router.post("/auth/send-otp", response_model=AuthResponse)
async def send_otp(req: SendOTPRequest):
    if not req.phone or len(req.phone) < 10:
        raise HTTPException(status_code=400, detail="Invalid phone number")

    await db.otp_sessions.update_one(
        {"phone": req.phone},
        {"$set": {
            "phone": req.phone,
            "otp": "1234",
            "verified": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        }},
        upsert=True
    )
    return AuthResponse(success=True, message="OTP sent successfully")


@api_router.post("/auth/verify-otp", response_model=AuthResponse)
async def verify_otp(req: VerifyOTPRequest):
    if req.otp != "1234":
        return AuthResponse(success=False, message="Invalid OTP")

    session = await db.otp_sessions.find_one({"phone": req.phone}, {"_id": 0})
    if not session:
        return AuthResponse(success=False, message="OTP session not found. Please request OTP first.")

    await db.otp_sessions.update_one(
        {"phone": req.phone},
        {"$set": {"verified": True}}
    )

    user = await db.users.find_one({"phone": req.phone}, {"_id": 0})
    if not user:
        user_id = str(uuid.uuid4())
        user = {
            "id": user_id,
            "phone": req.phone,
            "name": "",
            "language": "hi",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "profile_data": {
                "name": "",
                "age": None,
                "income": None,
                "state": "",
            },
            "profile_complete": False,
        }
        await db.users.insert_one(user)
    else:
        user_id = user["id"]

    return AuthResponse(success=True, message="OTP verified successfully", user_id=user_id, phone=req.phone)


# --- PROFILE ROUTES ---

@api_router.get("/profile/{user_id}")
async def get_profile(user_id: str):
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@api_router.put("/profile/{user_id}")
async def update_profile(user_id: str, update: ProfileUpdate):
    update_dict = {k: v for k, v in update.model_dump().items() if v is not None}
    if not update_dict:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = await db.users.update_one({"id": user_id}, {"$set": update_dict})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    return user


# --- SCHEMES ROUTES ---

@api_router.get("/schemes")
async def get_schemes():
    schemes = await db.schemes.find({}, {"_id": 0}).to_list(100)
    return schemes


@api_router.get("/schemes/{scheme_id}")
async def get_scheme(scheme_id: str):
    scheme = await db.schemes.find_one({"id": scheme_id}, {"_id": 0})
    if not scheme:
        raise HTTPException(status_code=404, detail="Scheme not found")
    return scheme


# --- CHAT ROUTES ---

@api_router.post("/chat")
async def send_chat_message(req: ChatMessageRequest):
    user_msg_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    user_msg = {
        "id": user_msg_id,
        "user_id": req.user_id,
        "role": "user",
        "content": req.content,
        "status": "sent",
        "created_at": now,
        "tool_calls": [],
    }
    await db.chat_logs.insert_one({**user_msg, "_id_field": None})

    # Step 1: Check profiler agent (incomplete profile takes priority)
    profiler_result = await profiler_agent_respond(req.user_id, req.content)

    if profiler_result:
        bot_msg_id = str(uuid.uuid4())
        bot_msg = {
            "id": bot_msg_id,
            "user_id": req.user_id,
            "role": "assistant",
            "content": profiler_result["content"],
            "status": "delivered",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "tool_calls": profiler_result.get("tool_calls", []),
            "type": profiler_result.get("type", "profiler"),
            "profiler_field": profiler_result.get("profiler_field", ""),
        }
        await db.chat_logs.insert_one({**bot_msg, "_id_field": None})
        await db.chat_logs.update_one({"id": user_msg_id}, {"$set": {"status": "read"}})

        return {
            "user_message": {k: v for k, v in user_msg.items() if k != "_id_field"},
            "bot_message": {k: v for k, v in bot_msg.items() if k != "_id_field"},
        }

    # Step 2: Normal MCP response
    mcp_result = get_bot_response_with_mcp(req.content, req.language)
    bot_msg_id = str(uuid.uuid4())

    bot_msg = {
        "id": bot_msg_id,
        "user_id": req.user_id,
        "role": "assistant",
        "content": mcp_result["content"],
        "status": "delivered",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tool_calls": mcp_result["tool_calls"],
    }
    await db.chat_logs.insert_one({**bot_msg, "_id_field": None})

    await db.chat_logs.update_one({"id": user_msg_id}, {"$set": {"status": "read"}})

    return {
        "user_message": {k: v for k, v in user_msg.items() if k != "_id_field"},
        "bot_message": {k: v for k, v in bot_msg.items() if k != "_id_field"},
    }


@api_router.get("/chat/history/{user_id}")
async def get_chat_history(user_id: str):
    messages = await db.chat_logs.find(
        {"user_id": user_id},
        {"_id": 0, "_id_field": 0}
    ).sort("created_at", 1).to_list(500)
    return messages


# --- VOICE / STT ROUTE ---

@api_router.post("/chat/voice")
async def voice_to_text(
    audio: UploadFile = File(...),
    user_id: str = Form(""),
    language: str = Form("hi")
):
    try:
        audio_bytes = await audio.read()

        stt_provider = os.environ.get("STT_PROVIDER", "openai_whisper")

        if stt_provider == "sarvam":
            try:
                from sarvamai import SarvamAI
                sarvam_key = os.environ.get("SARVAM_API_KEY", "")
                if not sarvam_key:
                    raise ValueError("SARVAM_API_KEY not configured")
                sarvam_client = SarvamAI(api_subscription_key=sarvam_key)
                with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
                    tmp.write(audio_bytes)
                    tmp_path = tmp.name
                response = sarvam_client.speech_to_text.transcribe(
                    file=open(tmp_path, "rb"),
                    model="saaras:v3",
                    mode="transcribe"
                )
                os.unlink(tmp_path)
                transcript = response.transcript
            except Exception as e:
                logger.error(f"Sarvam STT failed: {e}")
                raise HTTPException(status_code=500, detail=f"Sarvam STT failed: {str(e)}")
        else:
            try:
                from emergentintegrations.llm.openai import OpenAISpeechToText
                api_key = os.environ.get("EMERGENT_LLM_KEY", "")
                if not api_key:
                    raise ValueError("EMERGENT_LLM_KEY not configured")
                stt = OpenAISpeechToText(api_key=api_key)
                with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
                    tmp.write(audio_bytes)
                    tmp_path = tmp.name
                with open(tmp_path, "rb") as f:
                    response = await stt.transcribe(
                        file=f,
                        model="whisper-1",
                        response_format="json",
                        language=language if language != "hi" else "hi"
                    )
                os.unlink(tmp_path)
                transcript = response.text
            except Exception as e:
                logger.error(f"OpenAI Whisper STT failed: {e}")
                raise HTTPException(status_code=500, detail=f"Whisper STT failed: {str(e)}")

        return {"success": True, "transcript": transcript}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Voice processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- LLM PROVIDERS INFO ---

@api_router.get("/llm-providers")
async def get_llm_providers():
    return LLM_PROVIDERS


@api_router.get("/stt-providers")
async def get_stt_providers():
    return STT_PROVIDERS


# --- MCP TOOL ENDPOINTS ---

@api_router.get("/mcp/tools")
async def list_mcp_tools():
    """List available MCP tools (simulated MCP server)."""
    return {"tools": MCP_TOOLS}


@api_router.post("/search-schemes")
async def search_schemes_endpoint(req: SearchSchemesRequest):
    """
    Direct invocation of the search_schemes MCP tool.
    Scans seeded scheme documents and returns eligibility + criteria.
    """
    result = search_schemes(req.query, "en")
    return result


# --- SARVAM TRANSCRIBE ENDPOINT ---

@api_router.post("/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    user_id: str = Form(""),
):
    """
    Transcribe audio using Sarvam Saaras v3.
    - mode="translate" → returns English translation of spoken Hindi/regional audio
    - Also runs mode="transcribe" → returns original-language (Hindi) transcript
    Both stored in ChatLog.
    """
    from sarvamai import SarvamAI

    sarvam_key = os.environ.get("SARVAM_API_KEY", "")
    if not sarvam_key:
        raise HTTPException(status_code=500, detail="SARVAM_API_KEY not configured")

    audio_bytes = await audio.read()

    # Save audio file for playback
    audio_msg_id = str(uuid.uuid4())
    audio_filename = f"{audio_msg_id}.webm"
    audio_path = AUDIO_DIR / audio_filename
    with open(audio_path, "wb") as af:
        af.write(audio_bytes)

    # Write to temp file for Sarvam calls
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    sarvam_client = SarvamAI(api_subscription_key=sarvam_key)
    transcript_hi = ""
    transcript_en = ""

    # 1) Transcribe — original language (Hindi)
    try:
        with open(tmp_path, "rb") as f:
            resp_hi = sarvam_client.speech_to_text.transcribe(
                file=f,
                model="saaras:v3",
                mode="transcribe",
            )
        transcript_hi = resp_hi.transcript or ""
        logger.info(f"Sarvam transcribe (hi): {transcript_hi[:80]}")
    except Exception as e:
        logger.error(f"Sarvam transcribe mode failed: {e}")

    # 2) Translate — English translation
    try:
        with open(tmp_path, "rb") as f:
            resp_en = sarvam_client.speech_to_text.transcribe(
                file=f,
                model="saaras:v3",
                mode="translate",
            )
        transcript_en = resp_en.transcript or ""
        logger.info(f"Sarvam translate (en): {transcript_en[:80]}")
    except Exception as e:
        logger.error(f"Sarvam translate mode failed: {e}")

    # Clean up temp file
    try:
        os.unlink(tmp_path)
    except OSError:
        pass

    if not transcript_hi and not transcript_en:
        raise HTTPException(status_code=500, detail="Sarvam transcription returned empty for both modes")

    # Store in ChatLog as a transcription message
    now = datetime.now(timezone.utc).isoformat()
    display_content = ""
    if transcript_hi:
        display_content += f"[Hindi] {transcript_hi}"
    if transcript_en:
        if display_content:
            display_content += f"\n[English] {transcript_en}"
        else:
            display_content += f"[English] {transcript_en}"

    audio_url = f"/api/audio/{audio_msg_id}"

    chat_entry = {
        "id": audio_msg_id,
        "user_id": user_id,
        "role": "user",
        "content": display_content,
        "status": "read",
        "created_at": now,
        "tool_calls": [],
        "type": "transcription",
        "transcript_hi": transcript_hi,
        "transcript_en": transcript_en,
        "audio_url": audio_url,
    }
    await db.chat_logs.insert_one({**chat_entry, "_id_field": None})

    # Also generate a bot response based on the Hindi transcript
    query_text = transcript_hi if transcript_hi else transcript_en

    # Check profiler first
    profiler_result = await profiler_agent_respond(user_id, query_text) if user_id else None

    if profiler_result:
        bot_msg_id = str(uuid.uuid4())
        bot_msg = {
            "id": bot_msg_id,
            "user_id": user_id,
            "role": "assistant",
            "content": profiler_result["content"],
            "status": "delivered",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "tool_calls": profiler_result.get("tool_calls", []),
            "type": profiler_result.get("type", "profiler"),
            "profiler_field": profiler_result.get("profiler_field", ""),
        }
    else:
        mcp_result = get_bot_response_with_mcp(query_text, "hi")
        bot_msg_id = str(uuid.uuid4())
        bot_msg = {
            "id": bot_msg_id,
            "user_id": user_id,
            "role": "assistant",
            "content": mcp_result["content"],
            "status": "delivered",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "tool_calls": mcp_result["tool_calls"],
        }
    await db.chat_logs.insert_one({**bot_msg, "_id_field": None})

    return {
        "success": True,
        "transcript_hi": transcript_hi,
        "transcript_en": transcript_en,
        "user_message": {k: v for k, v in chat_entry.items() if k != "_id_field"},
        "bot_message": {k: v for k, v in bot_msg.items() if k != "_id_field"},
    }


# --- AUDIO PLAYBACK ENDPOINT ---

@api_router.get("/audio/{msg_id}")
async def serve_audio(msg_id: str):
    """Serve stored audio file for playback."""
    audio_path = AUDIO_DIR / f"{msg_id}.webm"
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio not found")
    return FileResponse(
        path=str(audio_path),
        media_type="audio/webm",
        headers={"Accept-Ranges": "bytes"},
    )


# --- HEALTH ---

@api_router.get("/")
async def root():
    return {"message": "Nagarik Sahayak API", "version": "1.0.0"}


# Include router
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
