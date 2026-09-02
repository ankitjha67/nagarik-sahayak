"""
GovScheme SuperAgent â€” Exam Parser (V3)
LLM + regex hybrid: extracts dates, fees, vacancies, eligibility from exam notifications.
Handles Indian date formats, category-wise fees, multi-phase exam schedules.
"""
from __future__ import annotations
import asyncio
import json
import logging
import re
from datetime import date, datetime
from typing import Optional
import httpx
from src.config.settings import AgentConfig
from src.exams.exam_models import (
    RawExamData, ParsedExamData, ExamFee, ExamPhaseDate, ExamVacancy,
    ExamEligibility, ExamCategory, ExamLevel, ExamStatus, ExamChangeType,
)
logger = logging.getLogger("ExamParser")
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# DATE PATTERNS (Indian Government formats)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
MONTH_MAP = {
    "jan": 1, "january": 1, "feb": 2, "february": 2,
    "mar": 3, "march": 3, "apr": 4, "april": 4,
    "may": 5, "jun": 6, "june": 6,
    "jul": 7, "july": 7, "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}
DATE_PATTERNS = [
    (r'(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})', "dmy"),              # DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
    (r'(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2})\b', "dmy_short"),     # DD/MM/YY
    (r'(\d{4})[/\-](\d{2})[/\-](\d{2})', "iso"),                       # YYYY-MM-DD
    (r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\w*[\s,]+(\d{4})', "d_mon_y"),
    (r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\w*\s+(\d{1,2})[\s,]+(\d{4})', "mon_d_y"),
    (r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})', "mon_y"),
]
DATE_CONTEXT_KEYWORDS = {
    "notification_date": ["notification date", "date of notification", "published on", "advertised on", "advt date"],
    "application_start": ["application opens", "application start", "apply from", "online registration start",
                          "registration opens", "commencement of", "opening date"],
    "application_end": ["last date", "closing date", "application end", "deadline", "apply before",
                         "apply by", "last date for", "last date of", "close on", "last date to apply"],
    "fee_payment": ["fee payment", "payment deadline", "fee last date", "last date for fee",
                     "fee payment last date"],
    "correction_window": ["correction window", "application correction", "edit window"],
    "admit_card": ["admit card", "hall ticket", "call letter", "e-admit card", "download admit"],
    "exam_date": ["exam date", "examination date", "written test", "cbt date", "test date",
                   "date of exam", "date of examination", "computer based test", "prelims date"],
    "result_date": ["result", "merit list", "select list", "result date", "result declared"],
    "interview_date": ["interview", "document verification", "dv date", "personality test"],
}
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# FEE PATTERNS
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
FEE_AMOUNT_RE = re.compile(
    r'(?:â‚¹|Rs\.?\s*|INR\s*)([\d,]+(?:\.\d{1,2})?)', re.IGNORECASE
)
FEE_FREE_RE = re.compile(
    r'\b(?:nil|no\s+fee|no\s+charge|free\s+of\s+cost|fee\s+waived|exempted|not\s+applicable)\b',
    re.IGNORECASE,
)
FEE_CATEGORY_PATTERNS = {
    "general": re.compile(r'(?:general|gen|ur|unreserved)\s*[-:â€“]\s*(?:â‚¹|Rs\.?\s*|INR\s*)([\d,]+)', re.I),
    "obc": re.compile(r'(?:obc|other\s+backward)\s*[-:â€“]\s*(?:â‚¹|Rs\.?\s*|INR\s*)([\d,]+)', re.I),
    "sc_st": re.compile(r'(?:sc[/\s]+st|sc\s*[-:â€“]|st\s*[-:â€“]|scheduled)\s*[-:â€“]?\s*(?:â‚¹|Rs\.?\s*|INR\s*)?([\d,]+|nil|free|exempted)', re.I),
    "female": re.compile(r'(?:female|women|lady)\s*[-:â€“]\s*(?:â‚¹|Rs\.?\s*|INR\s*)?([\d,]+|nil|free|exempted)', re.I),
    "ews": re.compile(r'(?:ews|economically\s+weaker)\s*[-:â€“]\s*(?:â‚¹|Rs\.?\s*|INR\s*)([\d,]+)', re.I),
    "pwd": re.compile(r'(?:pwd|ph|disabled|divyang)\s*[-:â€“]\s*(?:â‚¹|Rs\.?\s*|INR\s*)?([\d,]+|nil|free|exempted)', re.I),
}
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# VACANCY PATTERNS
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
VACANCY_TOTAL_RE = re.compile(
    r'(?:total\s+)?(?:vacancies?|posts?|positions?)\s*[-:â€“]?\s*(\d[\d,]*)', re.I
)
VACANCY_POST_RE = re.compile(
    r'(?:post\s*(?:name)?\s*[-:â€“]\s*)(.+?)(?:\s*[-â€“]\s*(\d+)\s*(?:posts?|vacancies?)?)', re.I
)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# CATEGORY INFERENCE
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
CATEGORY_KEYWORDS: dict[ExamCategory, list[str]] = {
    ExamCategory.Civil_Services: ["civil services", "ias", "ifs exam", "ies ", "geo-scientist",
                                   "engineering services", "combined defence", "upsc cse", "upsc ifs"],
    ExamCategory.Banking: ["ibps", "sbi po", "sbi clerk", "rbi", "nabard", "sebi", "sidbi",
                            "bank po", "bank clerk", "probationary officer"],
    ExamCategory.Railway: ["railway", "rrb", "rrc ", "rpf", "loco pilot", "alp ", "ntpc ",
                            "group d", "group-d", "rrb ntpc", "rrb alp", "rrb je"],
    ExamCategory.Defence: ["nda ", "cds ", "afcat", "airmen", "navy ssr", "navy aa",
                            "technical entry", "army tgc", "army ssc", "naval academy",
                            "coast guard", "indian army", "indian navy", "indian air force"],
    ExamCategory.Police: ["bsf ", "crpf", "cisf", "ssb ", "itbp", "assam rifles",
                           "head constable", "sub-inspector", "capf", "asi "],
    ExamCategory.Intelligence: ["intelligence bureau", "acio", "jio ", "mha ib", "cbi ",
                                 "enforcement directorate", "narcotics", "nia "],
    ExamCategory.SSC: ["ssc cgl", "ssc chsl", "ssc mts", "ssc cpo", "ssc gd", "ssc je",
                        "stenographer", "junior hindi translator", "ssc steno",
                        "staff selection commission"],
    ExamCategory.PSU: ["isro ", "drdo ", "barc ", "bhel ", "bel ", "hal ", "ongc",
                        "ntpc ", "sail ", "gail ", "bpcl", "hpcl", "iocl", "coal india",
                        "nalco", "nmdc", "mecl", "ceptam"],
    ExamCategory.Medical: ["neet", "aiims", "upsc cms", "pg medical", "mbbs", "medical officer"],
    ExamCategory.Engineering: ["jee main", "jee advanced", "gate ", "bitsat"],
    ExamCategory.Teaching: ["ctet", "kvs ", "nvs ", "tgt ", "pgt ", "teacher eligibility",
                             "kendriya vidyalaya", "navodaya", "teacher recruitment"],
    ExamCategory.Insurance: ["lic aao", "lic ado", "lic ae", "gic re", "niacl", "uiic",
                              "insurance company"],
    ExamCategory.Revenue: ["income tax", "customs", "gst ", "central excise"],
    ExamCategory.Agriculture: ["icar ", "fci ", "agricultural", "krishi", "nabard grade"],
    ExamCategory.State_PSC: ["public service commission", " psc ", " pcs ", "ppsc", "rpsc",
                              "mpsc", "tnpsc", "uppsc", "bpsc", "wbpsc", "kpsc", "appsc",
                              "opsc", "jpsc", "hpsc", "gpsc", "mppsc", "tspsc", "ukpsc"],
    ExamCategory.State_Police: ["state police", "constable police", "si police",
                                 "police recruitment board", "police constable"],
    ExamCategory.State_Teaching: ["state tet", "state teacher", "teacher recruitment board"],
    ExamCategory.State_Subordinate: ["subordinate services", "staff selection board",
                                      "group c", "group-c", "clerical", "sssb", "sssc"],
}
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# LLM CLASSIFICATION PROMPT
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
EXAM_PARSE_PROMPT = """You are an expert at parsing Indian Government Exam notifications.
Analyze the following exam information and extract ALL structured data.
Exam Name: {exam_name}
Conducting Body: {conducting_body}
Source URL: {source_url}
Raw Notification Text (truncated):
{raw_notification_text}
Raw Application Start: {raw_application_start}
Raw Application End: {raw_application_end}
Raw Exam Date: {raw_exam_date}
Raw Fee: {raw_fee}
Raw Vacancies: {raw_vacancy}
Raw Eligibility: {raw_eligibility}
Raw Age Limit: {raw_age_limit}
Respond ONLY with valid JSON matching this exact schema:
{{
    "exam_category": "<one of: Civil_Services|Banking|Railway|Defence|Police|Intelligence|SSC|PSU|Medical|Engineering|Teaching|Insurance|Revenue|Judiciary|Agriculture|State_PSC|State_Police|State_Teaching|State_Subordinate|Other_Central>",
    "exam_level": "<Central|State|UT>",
    "state": "<state name or null>",
    "clean_exam_name": "<standardized full exam name>",
    "short_name": "<abbreviation: CSE, CGL, IBPS-PO, NDA, etc. or null>",
    "exam_cycle": "<year or range: 2026, 2025-26, CRP-XVI, etc. or null>",
    "notification_date": "<YYYY-MM-DD or null>",
    "application_start_date": "<YYYY-MM-DD or null>",
    "application_end_date": "<YYYY-MM-DD or null>",
    "fee_payment_deadline": "<YYYY-MM-DD or null>",
    "correction_window_start": "<YYYY-MM-DD or null>",
    "correction_window_end": "<YYYY-MM-DD or null>",
    "phases": [
        {{
            "phase_name": "<Prelims|Mains|Written|CBT Phase 1|Interview|DV>",
            "exam_date_start": "<YYYY-MM-DD or null>",
            "exam_date_end": "<YYYY-MM-DD or null>",
            "admit_card_date": "<YYYY-MM-DD or null>",
            "result_date": "<YYYY-MM-DD or null>",
            "mode": "<CBT|OMR|Online|Offline|null>"
        }}
    ],
    "result_date": "<final result YYYY-MM-DD or null>",
    "interview_date": "<YYYY-MM-DD or null>",
    "final_result_date": "<YYYY-MM-DD or null>",
    "joining_date": "<YYYY-MM-DD or null>",
    "fee_general": null,
    "fee_obc": null,
    "fee_sc_st": null,
    "fee_female": null,
    "fee_ews": null,
    "fee_pwd": null,
    "fee_note": "<payment instructions or null>",
    "is_free": false,
    "vacancies": [
        {{
            "post_name": "<post title>",
            "total_vacancies": null,
            "pay_scale": "<pay level/scale or null>"
        }}
    ],
    "total_vacancies": null,
    "age_min": null,
    "age_max": null,
    "age_relaxation_obc": null,
    "age_relaxation_sc_st": null,
    "age_relaxation_pwd": null,
    "qualification": "<string or null>",
    "min_percentage": null,
    "experience_years": null,
    "physical_standards": "<string or null>",
    "domicile_required": "<state or null>",
    "gender_restriction": "<Only Male|Only Female|null>",
    "apply_online_url": "<URL or null>",
    "admit_card_url": "<URL or null>",
    "result_url": "<URL or null>",
    "syllabus_url": "<URL or null>",
    "official_website": "<URL or null>",
    "confidence": 0.0
}}
Rules:
- Extract EVERY date. If approximate ("April 2026"), use first of month "2026-04-01".
- For "FY 2025-26", use application_start "2025-04-01", application_end "2026-03-31".
- For fees: extract exact INR amounts per category. If "Nil"/"No fee" â†’ is_free: true, all fee=0.
- SC/ST fee of 0 does NOT mean is_free. is_free=true ONLY if ALL categories pay nothing.
- For vacancies: one entry per distinct post. Sum total_vacancies across all posts.
- For phases: one entry per exam stage. Prelims, Mains, DV/Interview are separate phases.
- exam_cycle is the year the exam is FOR (e.g., "2026" for UPSC CSE 2026).
- Category: UPSC CSE/IFS/IES â†’ Civil_Services. NDA/CDS â†’ Defence. BSF/CRPF â†’ Police. IB ACIO â†’ Intelligence.
"""
class ExamParser:
    """LLM + regex hybrid parser for government exam notifications."""
    def __init__(self, config: AgentConfig):
        self.config = config
        self.llm_parsed: int = 0
        self.regex_parsed: int = 0
        self.failed: int = 0
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # PUBLIC API
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    async def parse_batch(
        self, raw_exams: list[RawExamData], max_concurrent: int = 5,
    ) -> list[ParsedExamData]:
        """Parse a batch of raw exam data into structured ParsedExamData."""
        semaphore = asyncio.Semaphore(max_concurrent)
        async def _parse_safe(raw: RawExamData) -> ParsedExamData:
            async with semaphore:
                return await self._parse_single(raw)
        tasks = [_parse_safe(r) for r in raw_exams]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        parsed = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning("Parse failed for %s: %s", raw_exams[i].exam_name, result)
                parsed.append(self._regex_parse(raw_exams[i]))
                self.failed += 1
            else:
                parsed.append(result)
        return parsed
    async def _parse_single(self, raw: RawExamData) -> ParsedExamData:
        """Try LLM parse, fall back to regex."""
        has_llm = bool(self.config.anthropic_api_key or self.config.openai_api_key)
        if has_llm and raw.raw_notification_text:
            try:
                result = await self._llm_parse(raw)
                if result.parsing_confidence >= 0.5:
                    self.llm_parsed += 1
                    return self._finalize(result)
            except Exception as e:
                logger.debug("LLM parse failed for %s: %s", raw.exam_name, e)
        result = self._regex_parse(raw)
        self.regex_parsed += 1
        return self._finalize(result)
    def _finalize(self, parsed: ParsedExamData) -> ParsedExamData:
        """Apply status inference and deadline computation."""
        parsed.exam_status = self._infer_exam_status(parsed)
        self._compute_deadlines(parsed)
        return parsed
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # LLM PARSING
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    async def _llm_parse(self, raw: RawExamData) -> ParsedExamData:
        """Call LLM to parse the exam notification."""
        prompt = EXAM_PARSE_PROMPT.format(
            exam_name=raw.exam_name,
            conducting_body=raw.conducting_body,
            source_url=raw.source_url,
            raw_notification_text=(raw.raw_notification_text or "")[:3000],
            raw_application_start=raw.raw_application_start or "N/A",
            raw_application_end=raw.raw_application_end or "N/A",
            raw_exam_date=raw.raw_exam_date or "N/A",
            raw_fee=raw.raw_fee or "N/A",
            raw_vacancy=raw.raw_vacancy_text or raw.raw_total_vacancies or "N/A",
            raw_eligibility=raw.raw_eligibility or "N/A",
            raw_age_limit=raw.raw_age_limit or "N/A",
        )
        if self.config.llm_provider == "anthropic" and self.config.anthropic_api_key:
            data = await self._call_anthropic(prompt)
        elif self.config.openai_api_key:
            data = await self._call_openai(prompt)
        else:
            raise ValueError("No LLM API key configured")
        return self._build_parsed_from_llm(raw, data)
    async def _call_anthropic(self, prompt: str) -> dict:
        """Call Anthropic API and parse JSON response."""
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.config.anthropic_api_key,
                    "content-type": "application/json",
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": self.config.model_name,
                    "max_tokens": 4096,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
            body = resp.json()
            text = body["content"][0]["text"]
            return self._safe_json_parse(text)
    async def _call_openai(self, prompt: str) -> dict:
        """Call OpenAI API and parse JSON response."""
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.config.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o",
                    "messages": [
                        {"role": "system", "content": "You parse Indian government exam notifications into structured JSON."},
                        {"role": "user", "content": prompt},
                    ],
                    "response_format": {"type": "json_object"},
                    "max_tokens": 4096,
                },
            )
            resp.raise_for_status()
            body = resp.json()
            text = body["choices"][0]["message"]["content"]
            return self._safe_json_parse(text)
    def _safe_json_parse(self, text: str) -> dict:
        """Extract JSON from LLM output, stripping markdown fences."""
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r'^```(?:json)?\n?', '', text)
            text = re.sub(r'\n?```$', '', text)
        return json.loads(text)
    def _build_parsed_from_llm(self, raw: RawExamData, data: dict) -> ParsedExamData:
        """Build ParsedExamData from LLM JSON output."""
        phases = []
        for p in data.get("phases") or []:
            if isinstance(p, dict) and p.get("phase_name"):
                phases.append(ExamPhaseDate(
                    phase_name=p["phase_name"],
                    exam_date_start=p.get("exam_date_start"),
                    exam_date_end=p.get("exam_date_end"),
                    admit_card_date=p.get("admit_card_date"),
                    result_date=p.get("result_date"),
                    mode=p.get("mode"),
                ))
        vacancies = []
        for v in data.get("vacancies") or []:
            if isinstance(v, dict) and v.get("post_name"):
                vacancies.append(ExamVacancy(
                    post_name=v["post_name"],
                    total_vacancies=_safe_int(v.get("total_vacancies")),
                    pay_scale=v.get("pay_scale"),
                ))
        fee = ExamFee(
            general=_safe_float(data.get("fee_general")),
            obc=_safe_float(data.get("fee_obc")),
            sc_st=_safe_float(data.get("fee_sc_st")),
            female=_safe_float(data.get("fee_female")),
            ews=_safe_float(data.get("fee_ews")),
            pwd=_safe_float(data.get("fee_pwd")),
            fee_note=data.get("fee_note"),
            is_free=bool(data.get("is_free", False)),
            raw_fee_text=raw.raw_fee,
        )
        elig = ExamEligibility(
            age_min=_safe_int(data.get("age_min")),
            age_max=_safe_int(data.get("age_max")),
            age_relaxation_obc=_safe_int(data.get("age_relaxation_obc")),
            age_relaxation_sc_st=_safe_int(data.get("age_relaxation_sc_st")),
            age_relaxation_pwd=_safe_int(data.get("age_relaxation_pwd")),
            qualification=data.get("qualification"),
            min_percentage=_safe_float(data.get("min_percentage")),
            experience_years=_safe_int(data.get("experience_years")),
            physical_standards=data.get("physical_standards"),
            domicile_required=data.get("domicile_required"),
            gender_restriction=data.get("gender_restriction"),
        )
        try:
            cat = ExamCategory(data.get("exam_category", "Other_Central"))
        except ValueError:
            cat = ExamCategory.Other_Central
        try:
            lvl = ExamLevel(data.get("exam_level", "Central"))
        except ValueError:
            lvl = ExamLevel.Central
        return ParsedExamData(
            raw=raw,
            exam_category=cat,
            exam_level=lvl,
            state=data.get("state"),
            clean_exam_name=data.get("clean_exam_name") or raw.exam_name,
            short_name=data.get("short_name"),
            exam_cycle=data.get("exam_cycle"),
            notification_date=data.get("notification_date"),
            application_start_date=data.get("application_start_date"),
            application_end_date=data.get("application_end_date"),
            fee_payment_deadline=data.get("fee_payment_deadline"),
            correction_window_start=data.get("correction_window_start"),
            correction_window_end=data.get("correction_window_end"),
            phases=phases,
            result_date=data.get("result_date"),
            interview_date=data.get("interview_date"),
            final_result_date=data.get("final_result_date"),
            joining_date=data.get("joining_date"),
            fee=fee,
            vacancies=vacancies,
            total_vacancies=_safe_int(data.get("total_vacancies")),
            eligibility=elig,
            official_notification_url=data.get("official_notification_url") or raw.notification_url,
            apply_online_url=data.get("apply_online_url") or raw.apply_url,
            admit_card_url=data.get("admit_card_url"),
            result_url=data.get("result_url"),
            syllabus_url=data.get("syllabus_url") or raw.syllabus_url,
            official_website=data.get("official_website"),
            parsing_confidence=float(data.get("confidence", 0.8)),
        )
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # REGEX FALLBACK PARSING
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    def _regex_parse(self, raw: RawExamData) -> ParsedExamData:
        """Complete regex-based fallback parser. No LLM needed."""
        text_pool = " ".join(filter(None, [
            raw.raw_notification_text, raw.raw_eligibility,
            raw.raw_fee, raw.raw_vacancy_text, raw.raw_age_limit,
        ]))
        # Extract dates
        dates = self._extract_contextual_dates(text_pool, raw)
        # Extract fee
        fee = self._extract_fee(raw.raw_fee or text_pool[:2000])
        # Extract vacancies
        vacancies, total_vac = self._extract_vacancies(
            raw.raw_vacancy_text or raw.raw_total_vacancies or text_pool[:2000]
        )
        # Extract eligibility
        elig = self._extract_eligibility(raw)
        # Infer category
        category = self._infer_exam_category(raw.exam_name, raw.conducting_body)
        # Infer level
        level = ExamLevel.Central
        state = None
        for s_name in ["Tamil_Nadu", "Karnataka", "Maharashtra", "Kerala", "Gujarat",
                        "Rajasthan", "Uttar_Pradesh", "Bihar", "West_Bengal", "Madhya_Pradesh",
                        "Punjab", "Haryana", "Odisha", "Andhra_Pradesh", "Telangana",
                        "Jharkhand", "Chhattisgarh", "Assam", "Himachal_Pradesh", "Uttarakhand"]:
            if s_name.lower().replace("_", " ") in raw.exam_name.lower() or \
               s_name.lower().replace("_", " ") in raw.conducting_body.lower():
                level = ExamLevel.State
                state = s_name
                break
        if category in (ExamCategory.State_PSC, ExamCategory.State_Police,
                        ExamCategory.State_Teaching, ExamCategory.State_Subordinate):
            level = ExamLevel.State
        # Extract cycle year
        cycle = None
        year_match = re.search(r'20(2[4-9]|3[0-9])', raw.exam_name)
        if year_match:
            cycle = f"20{year_match.group(1)}"
        else:
            fy_match = re.search(r'(\d{4})\s*[-â€“]\s*(\d{2,4})', raw.exam_name)
            if fy_match:
                cycle = f"{fy_match.group(1)}-{fy_match.group(2)}"
        return ParsedExamData(
            raw=raw,
            exam_category=category,
            exam_level=level,
            state=state,
            clean_exam_name=raw.exam_name.strip(),
            exam_cycle=cycle,
            notification_date=dates.get("notification_date"),
            application_start_date=dates.get("application_start") or _try_parse_date(raw.raw_application_start),
            application_end_date=dates.get("application_end") or _try_parse_date(raw.raw_application_end),
            fee_payment_deadline=dates.get("fee_payment"),
            phases=self._build_phases_from_dates(dates, raw),
            result_date=dates.get("result_date"),
            interview_date=dates.get("interview_date"),
            fee=fee,
            vacancies=vacancies,
            total_vacancies=total_vac,
            eligibility=elig,
            official_notification_url=raw.notification_url,
            apply_online_url=raw.apply_url,
            syllabus_url=raw.syllabus_url,
            parsing_confidence=0.4,
        )
    def _extract_contextual_dates(self, text: str, raw: RawExamData) -> dict[str, str]:
        """Extract dates near context keywords from text."""
        found: dict[str, str] = {}
        text_lower = text.lower()
        for field_name, keywords in DATE_CONTEXT_KEYWORDS.items():
            for kw in keywords:
                idx = text_lower.find(kw.lower())
                if idx == -1:
                    continue
                window = text[max(0, idx - 50):idx + len(kw) + 100]
                parsed = _extract_first_date(window)
                if parsed and field_name not in found:
                    found[field_name] = parsed
                    break
        # Also use raw fields directly
        if "application_start" not in found and raw.raw_application_start:
            d = _try_parse_date(raw.raw_application_start)
            if d:
                found["application_start"] = d
        if "application_end" not in found and raw.raw_application_end:
            d = _try_parse_date(raw.raw_application_end)
            if d:
                found["application_end"] = d
        if "exam_date" not in found and raw.raw_exam_date:
            d = _try_parse_date(raw.raw_exam_date)
            if d:
                found["exam_date"] = d
        if "admit_card" not in found and raw.raw_admit_card_date:
            d = _try_parse_date(raw.raw_admit_card_date)
            if d:
                found["admit_card"] = d
        if "result_date" not in found and raw.raw_result_date:
            d = _try_parse_date(raw.raw_result_date)
            if d:
                found["result_date"] = d
        return found
    def _extract_fee(self, text: str) -> ExamFee:
        """Parse fee text into structured ExamFee."""
        fee = ExamFee(raw_fee_text=text[:500] if text else None)
        if FEE_FREE_RE.search(text or ""):
            fee.is_free = True
            fee.general = 0
            fee.obc = 0
            fee.sc_st = 0
            fee.female = 0
            fee.ews = 0
            fee.pwd = 0
            return fee
        for cat_name, pattern in FEE_CATEGORY_PATTERNS.items():
            m = pattern.search(text or "")
            if m:
                val_str = m.group(1)
                if val_str.lower() in ("nil", "free", "exempted"):
                    val = 0.0
                else:
                    val = _safe_float(val_str.replace(",", ""))
                setattr(fee, cat_name, val)
        # If no category-wise fees found, try single amount
        if fee.general is None:
            amounts = FEE_AMOUNT_RE.findall(text or "")
            if amounts:
                first_amount = _safe_float(amounts[0].replace(",", ""))
                fee.general = first_amount
                if fee.obc is None:
                    fee.obc = first_amount
                if fee.ews is None:
                    fee.ews = first_amount
        return fee
    def _extract_vacancies(self, text: str) -> tuple[list[ExamVacancy], Optional[int]]:
        """Parse vacancy info from text."""
        vacancies: list[ExamVacancy] = []
        total = None
        # Total vacancies
        total_match = VACANCY_TOTAL_RE.search(text or "")
        if total_match:
            total = _safe_int(total_match.group(1).replace(",", ""))
        # Individual posts
        for m in VACANCY_POST_RE.finditer(text or ""):
            post_name = m.group(1).strip()
            vac_count = _safe_int(m.group(2))
            if post_name and len(post_name) > 2:
                vacancies.append(ExamVacancy(
                    post_name=post_name,
                    total_vacancies=vac_count,
                ))
        # If no individual posts but total found, create one generic entry
        if not vacancies and total:
            vacancies.append(ExamVacancy(post_name="Various Posts", total_vacancies=total))
        # Ensure total is set
        if not total and vacancies:
            total = sum(v.total_vacancies or 0 for v in vacancies) or None
        return vacancies, total
    def _extract_eligibility(self, raw: RawExamData) -> ExamEligibility:
        """Extract eligibility from raw fields."""
        elig = ExamEligibility()
        age_text = raw.raw_age_limit or ""
        age_nums = re.findall(r'(\d{2})\s*(?:to|-|â€“)\s*(\d{2})', age_text)
        if age_nums:
            elig.age_min = int(age_nums[0][0])
            elig.age_max = int(age_nums[0][1])
        else:
            single_age = re.findall(r'(\d{2})\s*years', age_text)
            if single_age:
                elig.age_max = int(single_age[0])
        # Age relaxation
        relax_obc = re.search(r'obc\s*[-:â€“]\s*(\d+)\s*year', age_text, re.I)
        if relax_obc:
            elig.age_relaxation_obc = int(relax_obc.group(1))
        relax_scst = re.search(r'sc[/\s]*st\s*[-:â€“]\s*(\d+)\s*year', age_text, re.I)
        if relax_scst:
            elig.age_relaxation_sc_st = int(relax_scst.group(1))
        relax_pwd = re.search(r'(?:pwd|ph|disabled)\s*[-:â€“]\s*(\d+)\s*year', age_text, re.I)
        if relax_pwd:
            elig.age_relaxation_pwd = int(relax_pwd.group(1))
        elig.qualification = raw.raw_qualification or raw.raw_eligibility
        elig.physical_standards = raw.raw_physical_standards
        return elig
    def _build_phases_from_dates(self, dates: dict, raw: RawExamData) -> list[ExamPhaseDate]:
        """Build exam phases from extracted dates."""
        phases: list[ExamPhaseDate] = []
        exam_date = dates.get("exam_date") or _try_parse_date(raw.raw_exam_date)
        admit_card = dates.get("admit_card") or _try_parse_date(raw.raw_admit_card_date)
        result_date = dates.get("result_date") or _try_parse_date(raw.raw_result_date)
        if exam_date or admit_card:
            phases.append(ExamPhaseDate(
                phase_name="Written / CBT",
                exam_date_start=exam_date,
                admit_card_date=admit_card,
                result_date=result_date,
            ))
        interview_date = dates.get("interview_date") or _try_parse_date(raw.raw_interview_date)
        if interview_date:
            phases.append(ExamPhaseDate(
                phase_name="Interview / DV",
                exam_date_start=interview_date,
            ))
        return phases
    def _infer_exam_category(self, exam_name: str, body: str) -> ExamCategory:
        """Rule-based category detection from exam name and conducting body."""
        combined = f"{exam_name} {body}".lower()
        for cat, keywords in CATEGORY_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in combined:
                    return cat
        return ExamCategory.Other_Central
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # STATUS INFERENCE
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    def _infer_exam_status(self, parsed: ParsedExamData) -> ExamStatus:
        """Infer exam status from parsed dates."""
        today = date.today()
        app_start = _safe_date(parsed.application_start_date)
        app_end = _safe_date(parsed.application_end_date)
        # Check if any phase has an exam date
        earliest_exam = None
        for phase in parsed.phases:
            d = _safe_date(phase.exam_date_start)
            if d and (earliest_exam is None or d < earliest_exam):
                earliest_exam = d
        final = _safe_date(parsed.final_result_date)
        result = _safe_date(parsed.result_date)
        if final and final <= today:
            return ExamStatus.Completed
        if result and result <= today and (not final or final > today):
            return ExamStatus.Result_Awaited
        if earliest_exam:
            exam_end = earliest_exam
            for phase in parsed.phases:
                d = _safe_date(phase.exam_date_end)
                if d and d > exam_end:
                    exam_end = d
            if earliest_exam <= today <= exam_end:
                return ExamStatus.Exam_Ongoing
            if earliest_exam > today and (not app_end or app_end <= today):
                # Check for admit card
                for phase in parsed.phases:
                    ac = _safe_date(phase.admit_card_date)
                    if ac and ac <= today:
                        return ExamStatus.Admit_Card_Out
                return ExamStatus.Application_Closed
        if app_end and app_end >= today and app_start and app_start <= today:
            return ExamStatus.Application_Open
        if app_start and app_start > today:
            return ExamStatus.Upcoming
        if app_end and app_end < today:
            return ExamStatus.Application_Closed
        return ExamStatus.Upcoming
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # DEADLINE COMPUTATION
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    def _compute_deadlines(self, parsed: ParsedExamData) -> None:
        """Set days_until_application_close and days_until_exam."""
        today = date.today()
        app_end = _safe_date(parsed.application_end_date)
        if app_end and app_end >= today:
            parsed.days_until_application_close = (app_end - today).days
        earliest_exam = None
        for phase in parsed.phases:
            d = _safe_date(phase.exam_date_start)
            if d and d >= today and (earliest_exam is None or d < earliest_exam):
                earliest_exam = d
        if earliest_exam:
            parsed.days_until_exam = (earliest_exam - today).days
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# UTILITY FUNCTIONS
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
def _safe_int(val) -> Optional[int]:
    if val is None:
        return None
    try:
        return int(str(val).replace(",", "").strip())
    except (ValueError, TypeError):
        return None
def _safe_float(val) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(str(val).replace(",", "").strip())
    except (ValueError, TypeError):
        return None
def _safe_date(date_str: Optional[str]) -> Optional[date]:
    """Parse ISO or Indian date string to date object."""
    if not date_str:
        return None
    return _try_parse_date_obj(date_str)
def _try_parse_date(text: Optional[str]) -> Optional[str]:
    """Try to parse a date string and return ISO format. Returns None on failure."""
    if not text:
        return None
    d = _try_parse_date_obj(text.strip())
    return d.isoformat() if d else None
def _try_parse_date_obj(text: str) -> Optional[date]:
    """Parse various date formats into a date object."""
    text = text.strip()
    # ISO: YYYY-MM-DD
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})', text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    # DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
    m = re.match(r'^(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})$', text)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    # DD/MM/YY
    m = re.match(r'^(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2})$', text)
    if m:
        yr = int(m.group(3))
        yr = yr + 2000 if yr < 50 else yr + 1900
        try:
            return date(yr, int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    # DD Month YYYY / DD Mon YYYY
    m = re.match(r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\w*[\s,]+(\d{4})', text, re.I)
    if m:
        month = MONTH_MAP.get(m.group(2).lower()[:3])
        if month:
            try:
                return date(int(m.group(3)), month, int(m.group(1)))
            except ValueError:
                pass
    # Month DD, YYYY
    m = re.match(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\w*\s+(\d{1,2})[\s,]+(\d{4})', text, re.I)
    if m:
        month = MONTH_MAP.get(m.group(1).lower()[:3])
        if month:
            try:
                return date(int(m.group(3)), month, int(m.group(2)))
            except ValueError:
                pass
    # Month YYYY (use 1st of month)
    m = re.match(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})', text, re.I)
    if m:
        month = MONTH_MAP.get(m.group(1).lower()[:3])
        if month:
            try:
                return date(int(m.group(2)), month, 1)
            except ValueError:
                pass
    return None
def _extract_first_date(text: str) -> Optional[str]:
    """Extract the first recognizable date from text, return ISO."""
    for pattern, fmt in DATE_PATTERNS:
        m = re.search(pattern, text, re.I)
        if m:
            groups = m.groups()
            try:
                if fmt == "dmy":
                    return date(int(groups[2]), int(groups[1]), int(groups[0])).isoformat()
                elif fmt == "dmy_short":
                    yr = int(groups[2])
                    yr = yr + 2000 if yr < 50 else yr + 1900
                    return date(yr, int(groups[1]), int(groups[0])).isoformat()
                elif fmt == "iso":
                    return date(int(groups[0]), int(groups[1]), int(groups[2])).isoformat()
                elif fmt == "d_mon_y":
                    month = MONTH_MAP.get(groups[1].lower()[:3])
                    if month:
                        return date(int(groups[2]), month, int(groups[0])).isoformat()
                elif fmt == "mon_d_y":
                    month = MONTH_MAP.get(groups[0].lower()[:3])
                    if month:
                        return date(int(groups[2]), month, int(groups[1])).isoformat()
                elif fmt == "mon_y":
                    month = MONTH_MAP.get(groups[0].lower()[:3])
                    if month:
                        return date(int(groups[1]), month, 1).isoformat()
            except (ValueError, TypeError):
                continue
    return None
