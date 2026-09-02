"""Scheme search — Prisma-backed and in-memory sync variants."""
import re
import logging
import time as _time
from database import prisma
from config import AGNOST_WRITE_KEY

logger = logging.getLogger(__name__)

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
        "pdf_url": "https://static.pib.gov.in/WriteReadData/specificdocs/documents/2026/jan/doc2026121762801.pdf",
        "icon": "baby", "category": "savings",
    },
]

SCHEME_KEYWORDS = {
    0: ["kisan", "farmer", "किसान", "pmkisan", "agriculture", "कृषि", "खेती", "land", "भूमि"],
    1: ["ayushman", "आयुष्मान", "health", "hospital", "स्वास्थ्य", "insurance", "बीमा", "pmjay"],
    2: ["sukanya", "सुकन्या", "girl", "बेटी", "beti", "daughter", "बालिका", "savings", "बचत"],
}

STOPWORDS = {
    "eligibility", "eligible", "criteria", "benefit", "benefits", "scheme", "yojana", "योजना",
    "how", "who", "what", "can", "get", "help", "tell", "about", "kya", "kaun", "kaise", "batao",
}


def _track(user_id, input_val, output_val, properties, success, latency):
    if not AGNOST_WRITE_KEY:
        return
    try:
        import agnost
        agnost.track(
            user_id=user_id, agent_name="nagarik_tool",
            input=input_val, output=output_val,
            properties=properties, success=success, latency=latency,
        )
    except Exception:
        pass


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
        for kw_list in SCHEME_KEYWORDS.values():
            score += sum(1 for t in specific if any(t in kw or kw in t for kw in kw_list))
        if score >= 1:
            matched.append((scheme, score))
    matched.sort(key=lambda x: x[1], reverse=True)

    latency = int((_time.time() - t0) * 1000)
    _track("tool", query, str(bool(matched)), {"tool": "search_schemes"}, bool(matched), latency)

    if not matched:
        return {
            "tool_name": "search_schemes", "tool_input": {"query": query},
            "documents_scanned": [s.name for s in schemes], "match_found": False,
            "result_text": "I don't know — criteria not explicitly stated in government PDFs.",
        }

    results = []
    for scheme, _ in matched:
        results.append({
            "scheme_id": scheme.id, "scheme_title": scheme.name, "scheme_title_en": scheme.name,
            "eligibility": scheme.eligibilityCriteriaText,
            "benefits": scheme.eligibilityCriteriaText,
            "pdf_url": scheme.pdfUrl, "category": "government",
        })
    top = matched[0][0]
    return {
        "tool_name": "search_schemes", "tool_input": {"query": query},
        "documents_scanned": [s.name for s, _ in matched],
        "match_found": True, "matched_schemes": results,
        "result_text": f"Document scanned: {top.name}\n\n{top.eligibilityCriteriaText}",
    }


def search_schemes_sync(query: str, language: str = "hi") -> dict:
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
        return {
            "tool_name": "search_schemes", "tool_input": {"query": query},
            "documents_scanned": [s["title"] for s in SCHEMES_SEED], "match_found": False,
            "result_text": "I don't know — criteria not explicitly stated in government PDFs.",
        }

    is_hi = language == "hi"
    results = []
    for idx in matched:
        s = SCHEMES_SEED[idx]
        results.append({
            "scheme_title": s["title_hi"] if is_hi else s["title"],
            "scheme_title_en": s["title"],
            "eligibility": s["eligibility_hi"] if is_hi else s["eligibility"],
            "benefits": s["benefits_hi"] if is_hi else s["benefits"],
            "pdf_url": s["pdf_url"], "category": s["category"],
        })
    top = SCHEMES_SEED[matched[0]]
    return {
        "tool_name": "search_schemes", "tool_input": {"query": query},
        "documents_scanned": [SCHEMES_SEED[i]["title"] for i in matched],
        "match_found": True, "matched_schemes": results,
        "result_text": f"Document scanned: {top['title']}\n\n{top['eligibility']}\n\nBenefits: {top['benefits']}",
    }
