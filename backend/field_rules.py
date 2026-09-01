"""Rule-based form field extraction from PDF text.

Real Indian government forms are overwhelmingly scanned images, so the text we
get back is OCR output: noisy, with broken table structure and stray glyphs.
This module recovers form fields from that text using layout heuristics plus a
canonical keyword map, with no LLM involved.

It serves two roles:

1. **Fallback** — when no LLM key is configured, or the LLM call fails, this
   still produces a usable field list so the app keeps working.
2. **Enrichment** — its canonical `profileKey` mapping is applied to LLM output
   too, so the same real-world concept ("Name of Applicant", "Applicant Name",
   "आवेदक का नाम") always lands on one profile key and answers are reused
   across schemes.

Heuristics are deliberately conservative: it is better to miss an ambiguous
field than to invent one, because a hallucinated field becomes a question the
user cannot meaningfully answer.
"""
from __future__ import annotations

import re

# ── Canonical field vocabulary ───────────────────────────────────────────
# Ordered most-specific first: "father name" must beat the generic "name" rule,
# and "date of birth" must beat the generic "date" rule.
CANONICAL_FIELDS: list[tuple[str, dict]] = [
    (r"father.{0,12}(name|s name)|husband.{0,12}name|पिता|पति",
     {"profileKey": "father_husband_name", "type": "text",
      "labelEnglish": "Father's / Husband's Name", "labelHindi": "पिता / पति का नाम"}),
    (r"mother.{0,12}name|माता",
     {"profileKey": "mother_name", "type": "text",
      "labelEnglish": "Mother's Name", "labelHindi": "माता का नाम"}),
    (r"spouse.{0,12}name|wife.{0,12}name",
     {"profileKey": "spouse_name", "type": "text",
      "labelEnglish": "Spouse Name", "labelHindi": "जीवनसाथी का नाम"}),
    (r"aadha?ar|aadhar|uid\b|आधार",
     {"profileKey": "aadhaar_number", "type": "aadhaar",
      "labelEnglish": "Aadhaar Number", "labelHindi": "आधार संख्या"}),
    (r"date.{0,5}of.{0,5}birth|\bdob\b|birth.{0,5}date|जन्म.{0,5}तिथि",
     {"profileKey": "date_of_birth", "type": "date",
      "labelEnglish": "Date of Birth", "labelHindi": "जन्म तिथि"}),
    (r"\bage\b|आयु|उम्र",
     {"profileKey": "age", "type": "number",
      "labelEnglish": "Age", "labelHindi": "आयु"}),
    (r"mobile|phone|contact.{0,5}(no|number)|मोबाइल|दूरभाष",
     {"profileKey": "mobile_number", "type": "phone",
      "labelEnglish": "Mobile Number", "labelHindi": "मोबाइल नंबर"}),
    (r"e-?mail|ईमेल",
     {"profileKey": "email", "type": "email",
      "labelEnglish": "Email Address", "labelHindi": "ईमेल पता"}),
    (r"ifsc",
     {"profileKey": "ifsc_code", "type": "text",
      "labelEnglish": "IFSC Code", "labelHindi": "आईएफएससी कोड"}),
    (r"(bank|account).{0,15}(a/?c|account).{0,5}(no|number)|account.{0,5}(no|number)|खाता.{0,5}संख्या",
     {"profileKey": "bank_account_number", "type": "text",
      "labelEnglish": "Bank Account Number", "labelHindi": "बैंक खाता संख्या"}),
    (r"name.{0,5}of.{0,5}bank|bank.{0,5}name|बैंक.{0,5}नाम",
     {"profileKey": "bank_name", "type": "text",
      "labelEnglish": "Bank Name", "labelHindi": "बैंक का नाम"}),
    (r"branch|शाखा",
     {"profileKey": "branch_name", "type": "text",
      "labelEnglish": "Branch Name", "labelHindi": "शाखा का नाम"}),
    (r"(annual|family|monthly).{0,10}income|income.{0,10}(per annum|p\.a)|आय",
     {"profileKey": "annual_income", "type": "number",
      "labelEnglish": "Annual Family Income (₹)", "labelHindi": "वार्षिक पारिवारिक आय (₹)"}),
    (r"ration.{0,5}card|राशन",
     {"profileKey": "ration_card_number", "type": "text",
      "labelEnglish": "Ration Card Number", "labelHindi": "राशन कार्ड संख्या"}),
    (r"job.{0,5}card|mgnrega|nrega|मनरेगा",
     {"profileKey": "job_card_number", "type": "text",
      "labelEnglish": "MGNREGA Job Card Number", "labelHindi": "मनरेगा जॉब कार्ड संख्या"}),
    (r"\bpin.?code\b|\bpin\b|पिन",
     {"profileKey": "pincode", "type": "number",
      "labelEnglish": "PIN Code", "labelHindi": "पिन कोड"}),
    (r"district|जिला|ज़िला",
     {"profileKey": "district", "type": "text",
      "labelEnglish": "District", "labelHindi": "जिला"}),
    (r"\bstate\b|राज्य",
     {"profileKey": "state", "type": "text",
      "labelEnglish": "State", "labelHindi": "राज्य"}),
    (r"village|gram|गाँव|ग्राम",
     {"profileKey": "village", "type": "text",
      "labelEnglish": "Village", "labelHindi": "गाँव"}),
    (r"tehsil|taluk|block|तहसील|ब्लॉक",
     {"profileKey": "tehsil", "type": "text",
      "labelEnglish": "Tehsil / Block", "labelHindi": "तहसील / ब्लॉक"}),
    (r"address|पता|निवास",
     {"profileKey": "address_line", "type": "textarea",
      "labelEnglish": "Address", "labelHindi": "पता"}),
    (r"\bgender\b|\bsex\b|लिंग",
     {"profileKey": "gender", "type": "select",
      "labelEnglish": "Gender", "labelHindi": "लिंग",
      "options": ["Male", "Female", "Transgender"]}),
    (r"\bcategory\b|caste|sc.?/.?st|श्रेणी|जाति",
     {"profileKey": "category", "type": "select",
      "labelEnglish": "Category", "labelHindi": "श्रेणी",
      "options": ["General", "OBC", "SC", "ST", "EWS"]}),
    (r"survey.{0,5}(no|number)|khasra|खसरा|खतौनी",
     {"profileKey": "survey_khasra_number", "type": "text",
      "labelEnglish": "Survey / Khasra Number", "labelHindi": "सर्वे / खसरा नंबर"}),
    (r"(land|area).{0,15}(acre|hectare)|area in acres|land.{0,10}holding|भूमि|खेती",
     {"profileKey": "land_holding_acres", "type": "number",
      "labelEnglish": "Land Holding (acres)", "labelHindi": "भूमि (एकड़)"}),
    (r"loan.{0,10}amount|amount.{0,10}of.{0,5}loan|ऋण.{0,5}राशि",
     {"profileKey": "loan_amount_required", "type": "number",
      "labelEnglish": "Loan Amount Required (₹)", "labelHindi": "आवश्यक ऋण राशि (₹)"}),
    (r"institution|school|college|university|संस्थान|विद्यालय|महाविद्यालय",
     {"profileKey": "institution_name", "type": "text",
      "labelEnglish": "Name of Institution", "labelHindi": "संस्थान का नाम"}),
    (r"course|class.{0,5}of.{0,5}study|पाठ्यक्रम|कक्षा",
     {"profileKey": "course_name", "type": "text",
      "labelEnglish": "Course / Class", "labelHindi": "पाठ्यक्रम / कक्षा"}),
    (r"percentage|percent|marks|%|प्रतिशत|अंक",
     {"profileKey": "last_exam_percentage", "type": "number",
      "labelEnglish": "Percentage in Last Examination", "labelHindi": "पिछली परीक्षा में प्रतिशत"}),
    (r"roll.{0,5}(no|number)|enrol|registration.{0,5}(no|number)|रोल|नामांकन",
     {"profileKey": "roll_number", "type": "text",
      "labelEnglish": "Roll / Enrollment Number", "labelHindi": "रोल / नामांकन संख्या"}),
    (r"occupation|profession|व्यवसाय",
     {"profileKey": "occupation", "type": "text",
      "labelEnglish": "Occupation", "labelHindi": "व्यवसाय"}),
    (r"nationality|राष्ट्रीयता",
     {"profileKey": "nationality", "type": "text",
      "labelEnglish": "Nationality", "labelHindi": "राष्ट्रीयता"}),
    (r"marital|वैवाहिक",
     {"profileKey": "marital_status", "type": "select",
      "labelEnglish": "Marital Status", "labelHindi": "वैवाहिक स्थिति",
      "options": ["Single", "Married", "Widowed", "Divorced"]}),
    # Generic name rule stays last so the specific ones above win.
    (r"name.{0,5}of.{0,5}(the.{0,5})?(applicant|beneficiary|candidate|student|member)"
     r"|applicant.{0,5}name|full.{0,5}name|^name\b|नाम",
     {"profileKey": "name", "type": "text",
      "labelEnglish": "Full Name", "labelHindi": "पूरा नाम"}),
]

# Lines matching these are form furniture, not fields.
NOISE_PATTERNS = re.compile(
    r"^(annexure|form\s+no|page\s+\d|for\s+office\s+use|signature|thumb\s+impression"
    r"|place\s*:|date\s*:\s*$|seal|stamp|to\s*:?$|the\s+branch\s+manager"
    r"|declaration|i\s*/\s*we\s+hereby|certified\s+that|note\s*:|instructions?\s*:"
    r"|specimen|affix|photograph|passport\s+size)",
    re.IGNORECASE,
)

# Separators the extraction pipeline injects itself, e.g. "--- Page 2 (OCR) ---"
# or "--- Additional text (PyMuPDF) ---". These are our own scaffolding and must
# never be mistaken for form content.
PAGE_MARKER = re.compile(r"^\s*-{2,}.*?-{2,}\s*$")

# Signals that a document is an actual fillable form rather than prose
# (guidelines, FAQs, circulars — which government portals publish far more of).
FORM_KEYWORDS = re.compile(
    r"application\s+form|form\s+no|annexure|affix\s+.{0,20}photograph"
    r"|signature\s+of\s+(the\s+)?(applicant|candidate)|declaration\s+by"
    r"|to\s+be\s+filled|for\s+office\s+use|आवेदन\s*पत्र|प्रपत्र",
    re.IGNORECASE,
)

# Fill markers: dotted leaders, underscores, boxes — a strong signal that the
# preceding text is a field label on a blank form.
FILL_MARKER = re.compile(r"[.．_—–\-]{3,}|\.{2,}\s*$|\[\s*\]|\(\s*\)|□|☐")

# Section headers: "A. Particulars of the applicant", "PART-B", "SECTION 3"
# \b after part/section prevents "Particulars..." parsing as "Part" + "iculars".
SECTION_HEADER = re.compile(
    r"^\s*(?:(?:part|section)\b\s*[-–]?\s*)?([A-Z])[.)]\s+(.{3,60})$|"
    r"^\s*(part|section)\b\s*[-–]?\s*([A-Z0-9]{1,3})\s*[:.]\s*(.{0,60})$",
    re.IGNORECASE,
)

YES_NO = re.compile(r"\byes\b.{0,15}\bno\b|\bno\b.{0,15}\byes\b|हाँ.{0,10}नहीं", re.IGNORECASE)

# Sentence fragments, not labels. Declaration and nomination forms are dense
# legal prose interleaved with dotted signature lines, so the fill-marker signal
# alone would turn clauses like "I hereby nominate the person mentioned below"
# into fields. A real label is a short noun phrase.
PROSE_STARTER = re.compile(
    r"^(i|we|he|she|they|it|that|this|these|those|which|who|whom|whose|there"
    r"|here|having|being|hereby|whereas|provided|subject|in\s+case|if\s|and\s"
    r"|or\s|but\s|as\s|for\s|to\s|of\s|the\s+above|my\s|our\s|is\s|are\s|was\s"
    r"|were\s|shall|will|may\s|must|should|certified|declared"
    # Verb-led clauses from award/achievement forms, e.g.
    # "obtained the First/Second/Third position in the event held from..."
    r"|obtained|held|awarded|received|passed|enclose|attach|attested)\b",
    re.IGNORECASE,
)

# A generic (non-canonical) label longer than this is prose, not a field name.
MAX_GENERIC_LABEL_WORDS = 6


def _slug(text: str, fallback: str = "field") -> str:
    """snake_case identifier from a label."""
    s = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    s = re.sub(r"\s+", "_", s.strip().lower())
    s = re.sub(r"_+", "_", s).strip("_")
    return (s[:48] or fallback)


def classify_label(label: str) -> dict | None:
    """Map a raw label to a canonical field definition, or None if unrecognised."""
    low = label.lower()
    for pattern, spec in CANONICAL_FIELDS:
        if re.search(pattern, low, re.IGNORECASE | re.UNICODE):
            return dict(spec)
    return None


def _clean_label(raw: str) -> str:
    """Strip fill markers, numbering, and OCR noise from a candidate label."""
    s = FILL_MARKER.sub(" ", raw)
    s = re.sub(r"^\s*\(?\d{1,2}[.)]\s*", "", s)          # leading "1." / "(2)"
    s = re.sub(r"^\s*[a-zA-Z][.)]\s+", "", s)             # leading "a) "
    s = re.sub(r"[:：]\s*$", "", s)                        # trailing colon
    s = re.sub(r"\s{2,}", " ", s)
    # OCR frequently leaves isolated punctuation/single glyphs behind
    s = re.sub(r"\s+[|/\\]+\s*$", "", s)
    return s.strip(" .:-|_\t")


def _is_probable_label(line: str) -> bool:
    """Does this line look like a form field label rather than prose?"""
    stripped = line.strip()
    if len(stripped) < 3 or len(stripped) > 120:
        return False
    if PAGE_MARKER.match(stripped) or NOISE_PATTERNS.search(stripped):
        return False
    # Prose sentences (long, ending in a period, many words) are not labels.
    words = stripped.split()
    if len(words) > 14:
        return False
    # Needs at least some letters — OCR table fragments are often pure symbols.
    letters = sum(ch.isalpha() for ch in stripped)
    if letters < 3:
        return False
    return True


def looks_like_form(text: str) -> tuple[bool, str]:
    """Decide whether `text` came from a fillable form or from prose.

    Government portals publish far more guidelines, FAQs and circulars than
    actual forms. Running field extraction over prose yields plausible-looking
    but meaningless fields (a sentence mentioning "class" becomes a "Course"
    field), so callers should refuse rather than emit that noise.

    Returns (is_form, reason).
    """
    if not text or not text.strip():
        return False, "empty document"

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return False, "empty document"

    fill_markers = sum(1 for ln in lines if FILL_MARKER.search(ln))
    colon_labels = sum(
        1 for ln in lines
        if ":" in ln and len(ln) < 90 and not PAGE_MARKER.match(ln)
    )
    has_keyword = bool(FORM_KEYWORDS.search(text))

    # Prose runs long; form lines are short and fragmentary.
    long_lines = sum(1 for ln in lines if len(ln.split()) > 18)
    prose_ratio = long_lines / len(lines)

    structural = fill_markers + colon_labels

    if has_keyword and structural >= 3:
        return True, f"form keywords + {structural} structural signals"
    if structural >= 8 and prose_ratio < 0.35:
        return True, f"{structural} structural signals, low prose ratio"
    if has_keyword and prose_ratio < 0.2:
        return True, "form keywords with minimal prose"

    return False, (
        f"{structural} field signals, {prose_ratio:.0%} long lines"
        f"{', no form keywords' if not has_keyword else ''}"
    )


def extract_sections(text: str) -> list[dict]:
    """Pull section headers like 'A. Particulars of the applicant'."""
    sections: list[dict] = []
    seen: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if PAGE_MARKER.match(stripped):
            continue
        m = SECTION_HEADER.match(stripped)
        if not m:
            continue
        title = (m.group(2) or m.group(5) or "").strip(" .:-")
        title = _clean_label(title)
        if len(title) < 3 or NOISE_PATTERNS.search(title):
            continue
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)
        sections.append({"name": title[:60], "nameHindi": ""})
    return sections


def extract_fields_from_text(text: str, max_fields: int = 60) -> list[dict]:
    """Recover form fields from (usually OCR'd) form text.

    Returns field dicts in the same shape the LLM path produces, so callers can
    treat both identically.
    """
    if not text or not text.strip():
        return []

    fields: list[dict] = []
    seen_keys: set[str] = set()
    current_section = ""

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or PAGE_MARKER.match(line):
            continue

        # Track which section we are in.
        sm = SECTION_HEADER.match(line)
        if sm:
            title = _clean_label((sm.group(2) or sm.group(5) or ""))
            if len(title) >= 3 and not NOISE_PATTERNS.search(title):
                current_section = title[:60]
                continue

        if not _is_probable_label(line):
            continue

        has_marker = bool(FILL_MARKER.search(line))
        has_colon = ":" in line
        label = _clean_label(line.split(":")[0] if has_colon else line)
        if len(label) < 3:
            continue

        spec = classify_label(label)

        # Without a canonical match we require a strong structural signal
        # (a fill marker or a colon) before trusting it as a field.
        if spec is None and not (has_marker or has_colon):
            continue

        # Even a canonical keyword match must not come from a prose sentence:
        # "...students of that class may apply" should not become a Course field.
        if spec is not None and not (has_marker or has_colon) and len(label.split()) > 7:
            continue

        if spec is None:
            # Unrecognised but structurally a field — keep it generically, but
            # only if it reads like a label rather than a clause. Without this,
            # declaration/nomination forms yield keys like
            # "i_hereby_nominate_the_person_persons_mentioned".
            if not has_marker:
                continue
            if len(label.split()) > MAX_GENERIC_LABEL_WORDS:
                continue
            if PROSE_STARTER.match(label):
                continue
            key = _slug(label)
            if not key or key in seen_keys:
                continue
            spec = {
                "profileKey": key,
                "type": "select" if YES_NO.search(line) else "text",
                "labelEnglish": label[:100],
                "labelHindi": "",
            }
            if spec["type"] == "select":
                spec["options"] = ["Yes", "No"]
        else:
            # Yes/No phrasing overrides the canonical type.
            if YES_NO.search(line) and spec.get("type") not in ("select",):
                spec = dict(spec)
                spec["type"] = "select"
                spec["options"] = ["Yes", "No"]

        key = spec["profileKey"]
        if key in seen_keys:
            continue
        seen_keys.add(key)

        fields.append({
            "fieldName": key,
            "labelEnglish": spec.get("labelEnglish") or label[:100],
            "labelHindi": spec.get("labelHindi", ""),
            "type": spec.get("type", "text"),
            "required": True,
            "section": current_section or "Form Details",
            "profileKey": key,
            **({"options": spec["options"]} if spec.get("options") else {}),
        })

        if len(fields) >= max_fields:
            break

    return fields


def canonicalize_fields(fields: list[dict]) -> list[dict]:
    """Normalise profileKeys on an existing field list (e.g. LLM output).

    Two different forms calling the same thing "Name of Applicant" and
    "Applicant's Full Name" must share profileKey `name`, otherwise the profiler
    asks the user the same question twice. Also de-duplicates by profileKey.
    """
    out: list[dict] = []
    seen: set[str] = set()
    for field in fields or []:
        if not isinstance(field, dict):
            continue
        item = dict(field)
        label = (item.get("labelEnglish") or item.get("fieldName") or "")
        spec = classify_label(label)
        if spec:
            item["profileKey"] = spec["profileKey"]
            # Trust the canonical type for strongly-typed fields; the LLM often
            # labels Aadhaar/phone/date fields as plain text.
            if spec["type"] in ("aadhaar", "phone", "date", "email", "number"):
                item["type"] = spec["type"]
            if spec.get("options") and not item.get("options"):
                item["options"] = spec["options"]
            if spec.get("labelHindi") and not item.get("labelHindi"):
                item["labelHindi"] = spec["labelHindi"]
        else:
            item.setdefault("profileKey", _slug(label))

        key = item.get("profileKey")
        if not key or key in seen:
            continue
        seen.add(key)
        item.setdefault("fieldName", key)
        item.setdefault("type", "text")
        item.setdefault("required", True)
        item.setdefault("section", "Form Details")
        item.setdefault("labelHindi", "")
        out.append(item)
    return out


def infer_scheme_metadata(text: str) -> dict:
    """Best-effort scheme name and category from form text."""
    head = "\n".join(text.splitlines()[:40])

    # Score candidate title lines rather than taking the longest match: the
    # longest line containing "scheme" is often a sentence in the body text.
    # Real titles sit near the top, are set in capitals, and name the form.
    best_score, name = 0.0, ""
    for idx, line in enumerate(head.splitlines()):
        s = re.sub(r"\s{2,}", " ", line.strip(" .:_-"))
        if not (10 < len(s) < 120) or NOISE_PATTERNS.match(s):
            continue
        if PAGE_MARKER.match(s) or PROSE_STARTER.match(s):
            continue
        if not re.search(
            r"(application\s+(form|for)|form\s+for|yojana|scheme|योजना|आवेदन)",
            s, re.IGNORECASE,
        ):
            continue

        score = 1.0
        letters = [c for c in s if c.isalpha()]
        if letters and sum(c.isupper() for c in letters) / len(letters) > 0.7:
            score += 2.0                      # ALL CAPS reads as a heading
        if re.search(r"application\s+(form|for)|आवेदन\s*पत्र", s, re.IGNORECASE):
            score += 1.5                      # names the document explicitly
        score += max(0.0, 1.5 - idx * 0.05)   # earlier lines are likelier titles
        if s.endswith((".", ";", ",")):
            score -= 1.0                      # sentences end in punctuation

        if score > best_score:
            best_score, name = score, s

    name = name.strip()

    # Score every category by how many distinct keywords it matches rather than
    # taking the first hit: a widow *pension* form that happens to mention a
    # school would otherwise be filed under education.
    low = text.lower()
    patterns = {
        "agriculture": r"krishi|farmer|kisan|crop|agricultur|कृषि|किसान",
        "education": r"scholarship|student|school|college|educat|tuition"
                     r"|छात्रवृत्ति|शिक्षा|विद्यालय",
        "health": r"health|hospital|medical|ayushman|treatment|स्वास्थ्य|चिकित्सा",
        "housing": r"awas|housing|dwelling|pucca|kutcha|आवास|मकान",
        "startup": r"startup|entrepreneur|msme|udyam|स्टार्टअप|उद्यम",
        "finance": r"loan|credit|savings|deposit|bank\s+account|ऋण|बचत",
        # Social-welfare entitlements: pensions, widow/old-age/disability aid.
        "general": r"pension|widow|destitute|old\s+age|divyang|disabilit"
                   r"|handicap|bpl|antyodaya|पेंशन|विधवा|वृद्धावस्था|दिव्यांग",
    }
    scores = {
        cat: len(set(re.findall(pat, low, re.IGNORECASE)))
        for cat, pat in patterns.items()
    }
    best = max(scores, key=lambda c: scores[c])
    category = best if scores[best] else "general"

    return {"schemeName": name[:150], "category": category}


def build_template_from_text(text: str, scheme_hint: str = "",
                             require_form: bool = True) -> dict:
    """Full no-LLM extraction: fields + sections + metadata.

    Returns a FormTemplate-compatible dict, or a dict with `error` if the
    document is not a fillable form (set require_form=False to extract anyway).
    """
    if require_form:
        is_form, reason = looks_like_form(text)
        if not is_form:
            return {
                "error": f"This document does not appear to be a fillable "
                         f"application form ({reason}). It may be a guidelines, "
                         f"FAQ or circular document.",
                "_not_a_form": True,
                "_reason": reason,
            }

    fields = extract_fields_from_text(text)
    meta = infer_scheme_metadata(text)
    sections = extract_sections(text)

    if not sections:
        names, seen = [], set()
        for f in fields:
            s = f.get("section") or "Form Details"
            if s not in seen:
                seen.add(s)
                names.append({"name": s, "nameHindi": ""})
        sections = names

    return {
        "schemeName": scheme_hint or meta["schemeName"] or "Untitled Government Form",
        "schemeNameHindi": "",
        "category": meta["category"],
        "totalFields": len(fields),
        "sections": sections,
        "extractedFields": fields,
        "_extraction_engine": "rule_based",
    }
