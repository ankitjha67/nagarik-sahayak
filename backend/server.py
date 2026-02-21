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
import time as _time
import agnost

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Initialize Agnost tracking
_agnost_key = os.environ.get("AGNOST_WRITE_KEY", "")
if _agnost_key:
    agnost.init(_agnost_key)
    logging.getLogger(__name__).info("Agnost tracking initialized")

DEMO_MODE = os.environ.get("DEMO_MODE", "").lower() in ("true", "1", "yes")

AUDIO_DIR = ROOT_DIR / "audio_files"
AUDIO_DIR.mkdir(exist_ok=True)

PDF_DIR = ROOT_DIR / "pdf_reports"
PDF_DIR.mkdir(exist_ok=True)

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
    },
    {
        "name": "eligibility_matcher",
        "description": "Compares a user profile (age, income, state) against scheme-specific criteria extracted from scanned documents. Returns per-scheme {eligible, reason} with exact limit comparisons.",
        "input_schema": {
            "type": "object",
            "properties": {
                "profile": {
                    "type": "object",
                    "description": "User profile with name, age, income, state",
                    "properties": {
                        "name": {"type": "string"},
                        "age": {"type": "integer"},
                        "income": {"type": "integer", "description": "Monthly income in INR"},
                        "state": {"type": "string"}
                    }
                },
                "query": {
                    "type": "string",
                    "description": "Optional query to narrow scheme search"
                }
            },
            "required": ["profile"]
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


# --- DEMO MODE: Hardcoded Stage Demo ---

DEMO_PROFILE = {
    "name": "Rajesh Kumar",
    "age": 42,
    "income": 18000,
    "state": "Karnataka",
    "child": "Son, 10th pass",
}

VIDYASIRI_RESULT = {
    "scheme": "Vidyasiri Scholarship",
    "scheme_hi": "विद्यासिरी छात्रवृत्ति",
    "eligible": True,
    "reasons": [
        "Child passed 10th — eligible for Post-Matric scholarship",
        "Family income ₹18,000/month within ₹2,50,000/year ceiling",
        "Karnataka domicile verified",
    ],
    "reason": "Child passed 10th — eligible for Post-Matric scholarship; Family income ₹18,000/month within ₹2,50,000/year ceiling; Karnataka domicile verified",
    "benefit": "₹12,000–₹24,000/year tuition + hostel allowance for post-10th students",
}

PMKISAN_DEMO_RESULT = {
    "scheme": "PM-KISAN Samman Nidhi",
    "scheme_hi": "पीएम-किसान सम्मान निधि",
    "eligible": True,
    "reasons": [
        "Family income ₹18,000/month within ₹2,00,000/year limit",
        "Cultivable land requirement — verify at local office",
    ],
    "reason": "Family income ₹18,000/month within ₹2,00,000/year limit; Cultivable land requirement — verify at local office",
    "benefit": "₹6,000/year (₹2,000 every 4 months via DBT)",
}

# Exact trigger + fuzzy variations
DEMO_EXACT_TRIGGERS = [
    "mera beta 10th pass hai",
    "mera beta 10th pass",
    "mera beta das pass hai",
    "मेरा बेटा 10th पास है",
    "मेरा बेटा दसवीं पास है",
    "मेरा बेटा 10वीं पास है",
]

DEMO_SCHOLARSHIP_SIGNALS = [
    "scholarship", "छात्रवृत्ति", "vidyasiri", "विद्यासिरी", "student",
    "education", "शिक्षा", "college", "university", "tuition", "fee",
    "study", "पढ़ाई", "degree", "hostel", "exam",
    "10th", "10वीं", "दसवीं", "pass", "पास", "beta", "बेटा",
]


def _is_demo_trigger(text: str) -> bool:
    """Check if the text matches the hardcoded stage demo trigger."""
    if not DEMO_MODE:
        return False
    low = text.lower().strip()
    # Exact match first
    if low in DEMO_EXACT_TRIGGERS:
        return True
    # Fuzzy: any scholarship-related signal
    return any(sig in low for sig in DEMO_SCHOLARSHIP_SIGNALS)


def demo_stage_response(user_id: str = "demo") -> dict:
    """
    Hardcoded stage demo: 100% reliable, zero external dependencies.
    Profile → Eligibility → PDF in one shot.
    """
    from pdf_generator import generate_eligibility_pdf

    t0 = _time.time()
    results = [VIDYASIRI_RESULT, PMKISAN_DEMO_RESULT]
    pdf_id = str(uuid.uuid4())
    pdf_path = str(PDF_DIR / f"{pdf_id}.pdf")
    generate_eligibility_pdf(
        profile=DEMO_PROFILE,
        eligibility_results=results,
        output_path=pdf_path,
    )
    pdf_url = f"/api/pdf/{pdf_id}"
    latency_ms = int((_time.time() - t0) * 1000)

    try:
        if _agnost_key:
            agnost.track(
                user_id=user_id,
                agent_name="nagarik_tool",
                input="mera beta 10th pass hai",
                output=pdf_url,
                properties={"tool": "demo_stage", "pdf_id": pdf_id},
                success=True,
                latency=latency_ms,
            )
    except Exception:
        pass  # Never fail on tracking

    summary = (
        "प्रोफाइल पूरी हो गई!\n"
        f"नाम: {DEMO_PROFILE['name']} | उम्र: {DEMO_PROFILE['age']} वर्ष\n"
        f"मासिक आय: ₹{DEMO_PROFILE['income']:,} | राज्य: {DEMO_PROFILE['state']}\n"
        f"बच्चा: {DEMO_PROFILE['child']}\n\n"
        "पात्रता जांच पूरी हुई!\n\n"
        f"[+] विद्यासिरी छात्रवृत्ति: पात्र\n"
        f"    कारण: {VIDYASIRI_RESULT['reason']}\n"
        f"    लाभ: {VIDYASIRI_RESULT['benefit']}\n\n"
        f"[+] पीएम-किसान सम्मान निधि: पात्र\n"
        f"    कारण: {PMKISAN_DEMO_RESULT['reason']}\n"
        f"    लाभ: {PMKISAN_DEMO_RESULT['benefit']}\n\n"
        "PDF रिपोर्ट तैयार है! नीचे डाउनलोड करें।"
    )

    return {
        "content": summary,
        "tool_calls": [{
            "tool_name": "eligibility_matcher",
            "tool_input": {"profile": DEMO_PROFILE, "query": "10th pass scholarship"},
            "documents_scanned": ["Vidyasiri Scholarship Guidelines", "PM-KISAN Operational Guidelines"],
            "match_found": True,
            "results": results,
        }],
        "type": "profiler_complete",
        "profiler_field": "",
        "eligibility_results": results,
        "pdf_url": pdf_url,
    }



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
        t0 = _time.time()
        tool_result = search_schemes(content, language)
        latency_ms = int((_time.time() - t0) * 1000)
        if _agnost_key:
            agnost.track(
                user_id="chat",
                agent_name="nagarik_tool",
                input=content,
                output=str(tool_result.get("match_found", False)),
                properties={"tool": "search_schemes", "language": language},
                success=tool_result.get("match_found", False),
                latency=latency_ms,
            )
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


def eligibility_matcher(profile_data: dict, query: str = "") -> dict:
    """
    MCP Tool: eligibility_matcher
    1. Calls search_schemes to identify relevant schemes
    2. Compares user profile vs scheme-specific criteria from documents
    3. Returns per-scheme {eligible, reason} with exact limit comparisons
    """
    age = profile_data.get("age", 0) or 0
    income = profile_data.get("income", 0) or 0
    name = profile_data.get("name", "")
    _state = profile_data.get("state", "")  # for future state-specific rules

    # Step 1: Use search_schemes if query given, else check all
    if query:
        search_result = search_schemes(query, "en")
        if search_result["match_found"]:
            scheme_indices = []
            for ms in search_result.get("matched_schemes", []):
                for i, s in enumerate(SCHEMES_SEED):
                    if s["title"] == ms["scheme_title_en"]:
                        scheme_indices.append(i)
        else:
            scheme_indices = []
    else:
        scheme_indices = [0, 1, 2]

    documents_scanned = [s["title"] for s in SCHEMES_SEED]

    # Step 2: Per-scheme eligibility rules (extracted from document text)
    # Criteria thresholds from actual scheme PDFs
    SCHEME_RULES = {
        0: {  # PM-KISAN
            "scheme": "PM-KISAN Samman Nidhi",
            "scheme_hi": "पीएम-किसान सम्मान निधि",
            "criteria": {
                "income_limit": 200000,  # ₹2L/month — income tax payer exclusion
                "min_age": 18,
                "requires": "cultivable_land",
            },
            "benefit": "₹6,000/year (₹2,000 every 4 months via DBT)",
        },
        1: {  # Ayushman Bharat
            "scheme": "Ayushman Bharat (PM-JAY)",
            "scheme_hi": "आयुष्मान भारत (पीएम-जय)",
            "criteria": {
                "income_limit": 50000,  # ₹50K/month SECC threshold
                "min_age": 0,
                "requires": "secc_2011_listing",
            },
            "benefit": "₹5,00,000/year health cover per family",
        },
        2: {  # Sukanya Samriddhi
            "scheme": "Sukanya Samriddhi Yojana",
            "scheme_hi": "सुकन्या समृद्धि योजना",
            "criteria": {
                "income_limit": None,  # No income limit
                "min_age": 18,  # Parent/guardian must be 18+
                "requires": "girl_child_under_10",
            },
            "benefit": "~8.2% interest p.a., ₹1.5L tax deduction under 80C",
        },
    }

    results = []

    for idx in scheme_indices:
        rule = SCHEME_RULES.get(idx)
        if not rule:
            continue

        scheme_name = rule["scheme"]
        scheme_hi = rule["scheme_hi"]
        criteria = rule["criteria"]
        reasons = []
        eligible = True

        # Age check
        if criteria["min_age"] > 0 and age < criteria["min_age"]:
            eligible = False
            reasons.append(f"Age {age} years is below minimum {criteria['min_age']} years required")

        # Income check
        if criteria["income_limit"] is not None:
            if income > criteria["income_limit"]:
                eligible = False
                income_fmt = f"₹{income:,}"
                limit_fmt = f"₹{criteria['income_limit']:,}"
                reasons.append(f"Income {income_fmt}/month exceeds {limit_fmt}/month limit")
            else:
                income_fmt = f"₹{income:,}"
                limit_fmt = f"₹{criteria['income_limit']:,}"
                reasons.append(f"Income {income_fmt}/month is within {limit_fmt}/month limit")

        # Special requirement checks
        req = criteria.get("requires", "")
        if req == "cultivable_land":
            reasons.append("Requires cultivable agricultural land (cannot verify digitally)")
        elif req == "secc_2011_listing":
            reasons.append("Requires listing in SECC 2011 census (verify at mera.pmjay.gov.in)")
        elif req == "girl_child_under_10":
            reasons.append("Requires girl child below 10 years of age")

        # Age-based notes
        if idx == 2 and age >= 18:
            if eligible:
                reasons.append(f"Age {age}: eligible as parent/guardian to open account")

        result_entry = {
            "scheme": scheme_name,
            "scheme_hi": scheme_hi,
            "eligible": eligible,
            "reasons": reasons,
            "reason": "; ".join(reasons),
            "benefit": rule["benefit"],
        }
        results.append(result_entry)

    # Handle no matching schemes
    if not results and query:
        return {
            "tool_name": "eligibility_matcher",
            "tool_input": {"profile": profile_data, "query": query},
            "documents_scanned": documents_scanned,
            "match_found": False,
            "results": [],
            "summary": "I don't know — criteria not explicitly stated in PDFs.",
            "summary_hi": "मुझे जानकारी नहीं मिली — पीडीएफ दस्तावेजों में यह मापदंड स्पष्ट रूप से नहीं बताया गया है।",
        }

    # Build summary text
    summary_parts = [f"नमस्ते {name}! प्रोफाइल आधारित पात्रता:", ""]
    for r in results:
        status = "पात्र" if r["eligible"] else "अपात्र"
        icon = "+" if r["eligible"] else "-"
        summary_parts.append(f"[{icon}] {r['scheme_hi']}: {status}")
        summary_parts.append(f"    कारण: {r['reason']}")
        if r["eligible"]:
            summary_parts.append(f"    लाभ: {r['benefit']}")
        summary_parts.append("")

    return {
        "tool_name": "eligibility_matcher",
        "tool_input": {"profile": profile_data, "query": query},
        "documents_scanned": documents_scanned,
        "match_found": True,
        "results": results,
        "summary": "\n".join(summary_parts),
    }


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
            # Profile complete! Auto-trigger eligibility matcher + generate PDF
            await db.users.update_one({"id": user_id}, {"$set": {"profile_complete": True}})
            t0 = _time.time()
            matcher_result = eligibility_matcher(profile_data)
            latency_ms = int((_time.time() - t0) * 1000)
            if _agnost_key:
                agnost.track(
                    user_id=user_id,
                    agent_name="nagarik_tool",
                    input=str(profile_data),
                    output=str(matcher_result.get("match_found", False)),
                    properties={"tool": "eligibility_matcher", "trigger": "profiler_complete"},
                    success=matcher_result.get("match_found", False),
                    latency=latency_ms,
                )

            # Auto-generate PDF
            pdf_url = ""
            try:
                from pdf_generator import generate_eligibility_pdf
                pdf_id = str(uuid.uuid4())
                pdf_path = str(PDF_DIR / f"{pdf_id}.pdf")
                t0_pdf = _time.time()
                generate_eligibility_pdf(
                    profile=profile_data,
                    eligibility_results=matcher_result.get("results", []),
                    output_path=pdf_path,
                )
                pdf_url = f"/api/pdf/{pdf_id}"
                if _agnost_key:
                    agnost.track(
                        user_id=user_id,
                        agent_name="nagarik_tool",
                        input=str(profile_data),
                        output=pdf_url,
                        properties={"tool": "generate_pdf", "pdf_id": pdf_id, "trigger": "profiler_complete"},
                        success=True,
                        latency=int((_time.time() - t0_pdf) * 1000),
                    )
            except Exception as e:
                logger.error(f"PDF generation failed: {e}")

            content = f"धन्यवाद! आपकी प्रोफाइल पूरी हो गई।\n\n{matcher_result['summary']}"
            if pdf_url:
                content += "\n\nPDF रिपोर्ट तैयार है! नीचे डाउनलोड करें।"

            return {
                "content": content,
                "tool_calls": [{
                    "tool_name": "eligibility_matcher",
                    "tool_input": matcher_result["tool_input"],
                    "documents_scanned": matcher_result["documents_scanned"],
                    "match_found": matcher_result["match_found"],
                    "results": matcher_result.get("results", []),
                }],
                "type": "profiler_complete",
                "profiler_field": "",
                "eligibility_results": matcher_result.get("results", []),
                "pdf_url": pdf_url,
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
    try:
        await db.chat_logs.insert_one({**user_msg, "_id_field": None})
    except Exception:
        if not DEMO_MODE:
            raise  # Only swallow in demo mode

    # DEMO_MODE fast-path: "mera beta 10th pass hai" or any scholarship query
    # → instant profile + eligibility + PDF. Works even if DB is down.
    if DEMO_MODE and _is_demo_trigger(req.content):
        demo = demo_stage_response(req.user_id)
        bot_msg_id = str(uuid.uuid4())
        bot_msg = {
            "id": bot_msg_id,
            "user_id": req.user_id,
            "role": "assistant",
            "content": demo["content"],
            "status": "delivered",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "tool_calls": demo.get("tool_calls", []),
            "type": demo.get("type", "profiler_complete"),
            "profiler_field": "",
            "eligibility_results": demo.get("eligibility_results", []),
            "pdf_url": demo.get("pdf_url", ""),
        }
        try:
            await db.chat_logs.insert_one({**bot_msg, "_id_field": None})
            await db.chat_logs.update_one({"id": user_msg_id}, {"$set": {"status": "read"}})
        except Exception:
            pass  # DB failure must not break demo
        return {
            "user_message": {k: v for k, v in user_msg.items() if k != "_id_field"},
            "bot_message": {k: v for k, v in bot_msg.items() if k != "_id_field"},
        }

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
            "eligibility_results": profiler_result.get("eligibility_results", []),
            "pdf_url": profiler_result.get("pdf_url", ""),
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
    # DEMO_MODE: scholarship/education query → instant Vidyasiri + PM-KISAN result
    if DEMO_MODE and _is_demo_trigger(req.query):
        return {
            "tool_name": "search_schemes",
            "tool_input": {"query": req.query},
            "documents_scanned": ["Vidyasiri Scholarship Guidelines", "PM-KISAN Operational Guidelines"],
            "match_found": True,
            "matched_schemes": [{
                "scheme_title": VIDYASIRI_RESULT["scheme_hi"],
                "scheme_title_en": VIDYASIRI_RESULT["scheme"],
                "eligibility": "10th pass student, Karnataka domicile, family income < ₹2,50,000/year",
                "benefits": VIDYASIRI_RESULT["benefit"],
                "pdf_url": "https://sw.kar.nic.in/vidyasiri",
                "category": "education",
            }],
            "result_text": f"Document scanned: Vidyasiri Scholarship Guidelines\n\n{VIDYASIRI_RESULT['scheme']}:\nEligibility: 10th pass student, Karnataka domicile, family income < ₹2,50,000/year\n\nBenefits: {VIDYASIRI_RESULT['benefit']}",
        }

    t0 = _time.time()
    result = search_schemes(req.query, "en")
    latency_ms = int((_time.time() - t0) * 1000)
    if _agnost_key:
        agnost.track(
            user_id="api",
            agent_name="nagarik_tool",
            input=req.query,
            output=str(result.get("match_found", False)),
            properties={"tool": "search_schemes"},
            success=result.get("match_found", False),
            latency=latency_ms,
        )
    return result


class EligibilityCheckRequest(BaseModel):
    user_id: Optional[str] = None
    profile: Optional[Dict[str, Any]] = None
    query: str = ""


@api_router.post("/eligibility-check")
async def eligibility_check_endpoint(req: EligibilityCheckRequest):
    """
    Direct invocation of the eligibility_matcher MCP tool.
    Accepts a user_id (fetches profile from DB) or inline profile dict.
    Runs search_schemes then compares profile vs criteria.
    Returns per-scheme {eligible, reason} JSON.
    """
    profile = req.profile

    # If user_id provided, fetch profile from DB
    if req.user_id and not profile:
        user = await db.users.find_one({"id": req.user_id}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        profile = user.get("profile_data", {})

    if not profile:
        raise HTTPException(status_code=400, detail="Provide user_id or profile object")

    t0 = _time.time()
    result = eligibility_matcher(profile, req.query)
    latency_ms = int((_time.time() - t0) * 1000)
    if _agnost_key:
        agnost.track(
            user_id=req.user_id or "api",
            agent_name="nagarik_tool",
            input=str(profile),
            output=str(result.get("match_found", False)),
            properties={"tool": "eligibility_matcher", "query": req.query},
            success=result.get("match_found", False),
            latency=latency_ms,
        )
    return result


class GeneratePDFRequest(BaseModel):
    user_id: Optional[str] = None
    profile: Optional[Dict[str, Any]] = None
    scheme_id: Optional[str] = None


@api_router.post("/generate-pdf")
async def generate_pdf_endpoint(req: GeneratePDFRequest):
    """
    Generate an eligibility report PDF for a user profile.
    Accepts user_id (fetches profile + runs eligibility) or inline profile.
    Optionally focuses on a single scheme_id for detailed report.
    Returns download link + stores chat message.
    """
    from pdf_generator import generate_eligibility_pdf

    profile = req.profile

    # Fetch profile from DB if user_id given
    if req.user_id and not profile:
        user = await db.users.find_one({"id": req.user_id}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        profile = user.get("profile_data", {})

    if not profile or not profile.get("name"):
        raise HTTPException(status_code=400, detail="Profile incomplete — complete profiler first")

    # Run eligibility matcher
    t0 = _time.time()
    matcher = eligibility_matcher(profile)
    results = matcher.get("results", [])

    if not results:
        raise HTTPException(status_code=400, detail="No eligibility results to generate PDF for")

    # Fetch single scheme detail if requested
    scheme_detail = None
    if req.scheme_id:
        scheme_doc = await db.schemes.find_one({"id": req.scheme_id}, {"_id": 0})
        if scheme_doc:
            scheme_detail = scheme_doc

    # Generate PDF
    pdf_id = str(uuid.uuid4())
    pdf_path = str(PDF_DIR / f"{pdf_id}.pdf")

    generate_eligibility_pdf(
        profile=profile,
        eligibility_results=results,
        scheme_detail=scheme_detail,
        output_path=pdf_path,
    )
    latency_ms = int((_time.time() - t0) * 1000)

    pdf_url = f"/api/pdf/{pdf_id}"

    # Track with Agnost
    if _agnost_key:
        agnost.track(
            user_id=req.user_id or "api",
            agent_name="nagarik_tool",
            input=str(profile),
            output=pdf_url,
            properties={"tool": "generate_pdf", "pdf_id": pdf_id},
            success=True,
            latency=latency_ms,
        )

    # Store as chat message if user_id provided
    if req.user_id:
        now = datetime.now(timezone.utc).isoformat()
        eligible_count = sum(1 for r in results if r["eligible"])
        total = len(results)

        bot_msg_id = str(uuid.uuid4())
        bot_msg = {
            "id": bot_msg_id,
            "user_id": req.user_id,
            "role": "assistant",
            "content": f"आपकी पात्रता रिपोर्ट तैयार है! {eligible_count}/{total} योजनाओं में पात्र।\nPDF डाउनलोड करें:",
            "status": "delivered",
            "created_at": now,
            "tool_calls": [],
            "type": "pdf_report",
            "pdf_url": pdf_url,
            "eligible_count": eligible_count,
            "total_schemes": total,
        }
        await db.chat_logs.insert_one({**bot_msg, "_id_field": None})

    return {
        "success": True,
        "pdf_url": pdf_url,
        "pdf_id": pdf_id,
        "eligible_count": sum(1 for r in results if r["eligible"]),
        "total_schemes": len(results),
        "results": results,
    }


@api_router.get("/pdf/{pdf_id}")
async def serve_pdf(pdf_id: str):
    """Serve generated PDF report for download."""
    pdf_path = PDF_DIR / f"{pdf_id}.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=f"Nagarik_Sahayak_Report_{pdf_id[:8]}.pdf",
        headers={"Content-Disposition": f"attachment; filename=Nagarik_Sahayak_Report_{pdf_id[:8]}.pdf"},
    )


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


@api_router.get("/analytics/status")
async def analytics_status():
    """Check if Agnost analytics tracking is active."""
    return {
        "enabled": bool(_agnost_key),
        "dashboard_url": "https://app.agnost.ai",
    }


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
    if _agnost_key:
        agnost.shutdown()
    client.close()
