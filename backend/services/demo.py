"""Demo mode data and responses for stage presentations."""
import uuid
import time as _time
from config import AGNOST_WRITE_KEY, PDF_DIR, DEMO_MODE

DEMO_PROFILE = {
    "name": "Rajesh Kumar", "age": 42, "income": 18000,
    "state": "Karnataka", "child": "Son, 10th pass",
}

VIDYASIRI_RESULT = {
    "scheme": "Vidyasiri Scholarship", "scheme_hi": "विद्यासिरी छात्रवृत्ति",
    "eligible": True,
    "reasons": [
        "Child passed 10th — eligible for Post-Matric scholarship",
        "Family income ₹18,000/month within ₹2,50,000/year ceiling",
        "Karnataka domicile verified",
    ],
    "reason": "Child passed 10th — eligible for Post-Matric scholarship; "
              "Family income ₹18,000/month within ₹2,50,000/year ceiling; "
              "Karnataka domicile verified",
    "benefit": "₹12,000–₹24,000/year tuition + hostel allowance for post-10th students",
}

PMKISAN_DEMO_RESULT = {
    "scheme": "PM-KISAN Samman Nidhi", "scheme_hi": "पीएम-किसान सम्मान निधि",
    "eligible": True,
    "reasons": ["Family income ₹18,000/month within ₹2,00,000/year limit"],
    "reason": "Family income ₹18,000/month within ₹2,00,000/year limit",
    "benefit": "₹6,000/year (₹2,000 every 4 months via DBT)",
}

DEMO_EXACT_TRIGGERS = [
    "mera beta 10th pass hai", "mera beta 10th pass",
    "मेरा बेटा 10th पास है", "मेरा बेटा दसवीं पास है",
]
DEMO_SIGNALS = [
    "scholarship", "छात्रवृत्ति", "vidyasiri", "विद्यासिरी", "student", "education", "शिक्षा",
    "10th", "10वीं", "दसवीं", "pass", "पास", "beta", "बेटा", "college", "tuition", "पढ़ाई",
]


def is_demo_trigger(text: str) -> bool:
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

    if AGNOST_WRITE_KEY:
        try:
            import agnost
            agnost.track(
                user_id=user_id, agent_name="nagarik_tool",
                input="mera beta 10th pass hai", output=str(len(pdf_urls)),
                properties={"tool": "demo_stage", "pdf_count": len(pdf_urls)},
                success=True, latency=int((_time.time() - t0) * 1000),
            )
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
        "tool_calls": [{
            "tool_name": "eligibility_matcher",
            "tool_input": {"profile": DEMO_PROFILE},
            "documents_scanned": ["Vidyasiri Scholarship Guidelines", "PM-KISAN Operational Guidelines"],
            "match_found": True, "results": results,
        }],
        "type": "profiler_complete", "profiler_field": "", "eligibility_results": results,
        "pdf_url": pdf_urls[0]["pdf_url"] if pdf_urls else "",
        "pdf_urls": pdf_urls,
        "tool_progress": [
            {"step": "reading_pdf", "text_hi": "विद्यासिरी छात्रवृत्ति PDF पढ़ रहे हैं...", "text_en": "Reading Vidyasiri Scholarship PDF..."},
            {"step": "checking_eligibility", "text_hi": "पात्रता मानदंड जांच रहे हैं...", "text_en": "Checking eligibility criteria..."},
            {"step": "generating_form", "text_hi": "भरा हुआ आवेदन फॉर्म तैयार कर रहे हैं...", "text_en": "Generating filled application form..."},
        ],
    }
