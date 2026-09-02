"""
GovScheme SuperAgent â€” Classification Agent
Uses LLM to classify raw scheme data into proper categories.
"""
from __future__ import annotations
import asyncio
import json
import logging
from typing import Optional
import httpx
from src.agents.models import (
    RawSchemeData, ClassifiedScheme, SchemeLevel, SchemeSector, SchemeType,
)
from src.config.settings import AgentConfig
logger = logging.getLogger("classify_agent")
CLASSIFICATION_PROMPT = """You are a government scheme classification expert for India.
Analyze the following scheme information and classify it accurately.
Scheme Name: {name}
Source Portal: {source}
Raw Description: {description}
Raw Ministry/Department: {ministry}
Raw State: {state}
Raw Category: {category}
Raw Eligibility: {eligibility}
Raw Benefits: {benefits}
Classify this scheme into EXACTLY these categories. Respond ONLY with valid JSON:
{{
    "level": "<Central|State|Union_Territory>",
    "state": "<state name if State/UT level, else null>",
    "sector": "<one of: Education, Agriculture, Fisheries, MSME, Startup, Science_Technology, Health, Women_Child_Development, Social_Justice, Tribal_Affairs, Minority_Affairs, Rural_Development, Urban_Development, Labour_Employment, Skill_Development, Housing, Finance, Industry, IT_Electronics, Textiles, Food_Processing, Environment, Energy, Transport, Tourism, Sports_Youth, Culture, Defence, Disability, General>",
    "scheme_type": "<one of: Scholarship, Grant, Startup_Fund, Subsidy, Loan, Pension, Insurance, Fellowship, Award, Stipend, Other>",
    "clean_name": "<cleaned, standardized scheme name>",
    "summary": "<2-3 sentence summary of the scheme>",
    "eligibility_summary": "<brief eligibility criteria>",
    "benefit_amount": "<monetary benefit if mentioned, else null>",
    "target_group": "<target beneficiary group>",
    "confidence": <0.0 to 1.0 confidence score>
}}
Rules:
- If the scheme mentions a specific state government, classify as State level
- If from a central ministry or "Government of India", classify as Central
- If from a Union Territory administration, classify as Union_Territory
- For the state field, use the standardized name (e.g., "Tamil_Nadu", "Maharashtra")
- Choose the MOST SPECIFIC sector that matches
- If fisheries/aquaculture is mentioned, use Fisheries even if under Agriculture ministry
- For startup/entrepreneurship schemes, prefer Startup over MSME unless clearly MSME-focused
- Be precise with scheme_type â€” scholarships are for students, grants are for projects/organizations
"""
class ClassificationAgent:
    """
    Uses LLM to intelligently classify raw scheme data into
    structured categories for folder organization.
    """
    def __init__(self, config: AgentConfig):
        self.config = config
        self.classified_count = 0
        self.failed_count = 0
    async def classify_scheme(self, raw: RawSchemeData) -> Optional[ClassifiedScheme]:
        """Classify a single raw scheme using LLM."""
        prompt = CLASSIFICATION_PROMPT.format(
            name=raw.scheme_name,
            source=raw.source_portal,
            description=(raw.raw_description or "Not available")[:1500],
            ministry=raw.raw_ministry or "Not specified",
            state=raw.raw_state or "Not specified",
            category=raw.raw_category or "Not specified",
            eligibility=(raw.raw_eligibility or "Not available")[:500],
            benefits=(raw.raw_benefits or "Not available")[:500],
        )
        try:
            result = await self._call_llm(prompt)
            if not result:
                return self._fallback_classify(raw)
            # Parse JSON response
            classification = self._parse_llm_response(result)
            if not classification:
                return self._fallback_classify(raw)
            classified = ClassifiedScheme(
                raw_data=raw,
                level=SchemeLevel(classification.get("level", "Central")),
                state=classification.get("state"),
                sector=SchemeSector(classification.get("sector", "General")),
                scheme_type=SchemeType(classification.get("scheme_type", "Other")),
                clean_name=classification.get("clean_name", raw.scheme_name),
                summary=classification.get("summary", ""),
                eligibility_summary=classification.get("eligibility_summary"),
                benefit_amount=classification.get("benefit_amount"),
                target_group=classification.get("target_group"),
                classification_confidence=classification.get("confidence", 0.5),
            )
            self.classified_count += 1
            return classified
        except Exception as e:
            logger.error("Classification failed for '%s': %s", raw.scheme_name, e)
            self.failed_count += 1
            return self._fallback_classify(raw)
    async def classify_batch(
        self,
        schemes: list[RawSchemeData],
        max_concurrent: int = 5,
        batch_size: int = 10,
    ) -> list[ClassifiedScheme]:
        """Classify a batch of schemes with concurrency control."""
        classified = []
        sem = asyncio.Semaphore(max_concurrent)
        async def _classify_one(raw: RawSchemeData) -> Optional[ClassifiedScheme]:
            async with sem:
                result = await self.classify_scheme(raw)
                await asyncio.sleep(0.2)  # Rate limit LLM calls
                return result
        # Process in batches to manage memory
        for i in range(0, len(schemes), batch_size):
            batch = schemes[i : i + batch_size]
            tasks = [_classify_one(raw) for raw in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, ClassifiedScheme):
                    classified.append(result)
                elif isinstance(result, Exception):
                    logger.warning("Batch classify error: %s", result)
            logger.info(
                "Classified %d/%d schemes", len(classified), len(schemes)
            )
        return classified
    async def _call_llm(self, prompt: str) -> Optional[str]:
        """Call the LLM API (Anthropic or OpenAI)."""
        if self.config.llm_provider == "anthropic":
            return await self._call_anthropic(prompt)
        elif self.config.llm_provider == "openai":
            return await self._call_openai(prompt)
        else:
            raise ValueError(f"Unknown LLM provider: {self.config.llm_provider}")
    async def _call_anthropic(self, prompt: str) -> Optional[str]:
        """Call Anthropic Claude API."""
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.config.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.config.model_name,
                    "max_tokens": 1000,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return data["content"][0]["text"]
            else:
                logger.error("Anthropic API error: %d %s", resp.status_code, resp.text[:200])
                return None
    async def _call_openai(self, prompt: str) -> Optional[str]:
        """Call OpenAI API."""
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.config.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1000,
                    "temperature": 0.1,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            return None
    def _parse_llm_response(self, response: str) -> Optional[dict]:
        """Parse JSON from LLM response, handling common issues."""
        # Strip markdown code fences
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()
        try:
            data = json.loads(text)
            # Validate required fields
            if "level" in data and "sector" in data:
                return data
        except json.JSONDecodeError:
            # Try to extract JSON from the response
            import re
            match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
        return None
    def _fallback_classify(self, raw: RawSchemeData) -> ClassifiedScheme:
        """Rule-based fallback classification when LLM fails."""
        name_lower = (raw.scheme_name or "").lower()
        desc_lower = (raw.raw_description or "").lower()
        combined = f"{name_lower} {desc_lower}"
        # Determine level
        level = SchemeLevel.CENTRAL
        state = None
        if raw.raw_state:
            state = raw.raw_state.replace(" ", "_")
            from src.config.settings import INDIAN_STATES, UNION_TERRITORIES
            if state in UNION_TERRITORIES:
                level = SchemeLevel.UNION_TERRITORY
            elif state in INDIAN_STATES:
                level = SchemeLevel.STATE
        # Determine sector via keyword matching
        sector_keywords = {
            SchemeSector.EDUCATION: ["scholarship", "student", "education", "school", "college", "university", "academic"],
            SchemeSector.AGRICULTURE: ["agriculture", "farmer", "crop", "kisan", "farm"],
            SchemeSector.FISHERIES: ["fisheries", "fish", "aquaculture", "marine", "fishing"],
            SchemeSector.MSME: ["msme", "micro", "small enterprise", "medium enterprise"],
            SchemeSector.STARTUP: ["startup", "entrepreneur", "innovation", "incubat"],
            SchemeSector.HEALTH: ["health", "medical", "hospital", "ayushman", "doctor", "nursing"],
            SchemeSector.WOMEN_CHILD: ["women", "girl", "child", "maternal", "beti", "mahila"],
            SchemeSector.SOCIAL_JUSTICE: ["sc/st", "obc", "backward", "dalit", "social justice"],
            SchemeSector.TRIBAL_AFFAIRS: ["tribal", "adivasi", "scheduled tribe"],
            SchemeSector.MINORITY_AFFAIRS: ["minority", "muslim", "christian", "sikh", "buddhist", "jain"],
            SchemeSector.SKILL_DEVELOPMENT: ["skill", "training", "vocational", "apprentice"],
            SchemeSector.HOUSING: ["housing", "awas", "pradhan mantri awas"],
            SchemeSector.RURAL_DEVELOPMENT: ["rural", "panchayat", "gram", "village"],
            SchemeSector.LABOUR_EMPLOYMENT: ["labour", "worker", "employment", "esi", "epf"],
            SchemeSector.SCIENCE_TECHNOLOGY: ["science", "research", "technology", "innovation", "dst"],
            SchemeSector.DISABILITY: ["disability", "handicap", "divyang", "pwd"],
        }
        sector = SchemeSector.GENERAL
        for s, keywords in sector_keywords.items():
            if any(kw in combined for kw in keywords):
                sector = s
                break
        # Determine type
        type_keywords = {
            SchemeType.SCHOLARSHIP: ["scholarship", "merit"],
            SchemeType.FELLOWSHIP: ["fellowship", "research fellow"],
            SchemeType.GRANT: ["grant", "funding"],
            SchemeType.SUBSIDY: ["subsidy", "subsidised"],
            SchemeType.LOAN: ["loan", "credit", "mudra"],
            SchemeType.PENSION: ["pension", "old age"],
            SchemeType.INSURANCE: ["insurance", "bima"],
            SchemeType.STIPEND: ["stipend"],
            SchemeType.STARTUP_FUND: ["startup fund", "seed fund", "venture"],
        }
        scheme_type = SchemeType.OTHER
        for t, keywords in type_keywords.items():
            if any(kw in combined for kw in keywords):
                scheme_type = t
                break
        return ClassifiedScheme(
            raw_data=raw,
            level=level,
            state=state,
            sector=sector,
            scheme_type=scheme_type,
            clean_name=raw.scheme_name.strip(),
            summary=raw.raw_description[:300] if raw.raw_description else "Details pending enrichment.",
            eligibility_summary=raw.raw_eligibility[:200] if raw.raw_eligibility else None,
            classification_confidence=0.4,  # Lower confidence for fallback
        )
