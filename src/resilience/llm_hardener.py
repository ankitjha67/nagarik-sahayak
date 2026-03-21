"""
GovScheme SuperAgent â€” LLM Response Hardener
Addresses limitation: "Claude/GPT will sometimes return malformed JSON,
hallucinate dates, or misclassify exams."
Layers of defense:
  1. JSON extraction from mixed text/markdown responses
  2. Structural repair of malformed JSON (unclosed brackets, trailing commas)
  3. Schema validation against expected fields and types
  4. Date plausibility checks (no dates before 2020 or after 2030)
  5. Enum value correction (fuzzy match against valid values)
  6. Retry with simplified prompt on failure
  7. Confidence penalty for repaired responses
"""
from __future__ import annotations
import json
import logging
import re
from datetime import datetime, date
from typing import Any, Optional
logger = logging.getLogger("llm_hardener")
# â”€â”€ Date Plausibility Window â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
MIN_PLAUSIBLE_YEAR = 2020
MAX_PLAUSIBLE_YEAR = 2032
class LLMResponseHardener:
    """Repairs and validates LLM JSON responses."""
    def __init__(self, valid_enums: Optional[dict[str, list[str]]] = None):
        """
        Args:
            valid_enums: Map of field_name â†’ list of valid enum string values.
                         e.g. {"level": ["Central", "State", "Union_Territory"]}
        """
        self.valid_enums = valid_enums or {}
        self.repair_count = 0
        self.reject_count = 0
    # â”€â”€â”€ Main Entry Point â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def parse_and_validate(
        self,
        raw_response: str,
        required_fields: Optional[list[str]] = None,
        date_fields: Optional[list[str]] = None,
        numeric_fields: Optional[list[str]] = None,
    ) -> tuple[Optional[dict], float]:
        """
        Parse LLM response, repair if needed, validate, return (data, confidence_penalty).
        confidence_penalty: 0.0 = no repairs needed, up to 0.5 = heavily repaired.
        Returns (None, 1.0) if unrecoverable.
        """
        penalty = 0.0
        # Step 1: Extract JSON from response
        data = self._extract_json(raw_response)
        if data is None:
            # Try structural repair
            repaired = self._repair_json_structure(raw_response)
            data = self._extract_json(repaired)
            if data is None:
                logger.warning("JSON extraction failed after repair")
                self.reject_count += 1
                return None, 1.0
            penalty += 0.15
        # Step 2: Type coercion
        if numeric_fields:
            for field in numeric_fields:
                if field in data and data[field] is not None:
                    data[field], p = self._coerce_numeric(data[field])
                    penalty += p
        # Step 3: Enum correction
        for field, valid_values in self.valid_enums.items():
            if field in data and data[field] is not None:
                data[field], p = self._correct_enum(data[field], valid_values)
                penalty += p
        # Step 4: Date plausibility
        if date_fields:
            for field in date_fields:
                if field in data and data[field] is not None:
                    data[field], p = self._validate_date(data[field], field)
                    penalty += p
        # Step 5: Required fields check
        if required_fields:
            missing = [f for f in required_fields if f not in data or data[f] is None]
            if missing:
                logger.debug("Missing required fields: %s", missing)
                penalty += 0.05 * len(missing)
        # Step 6: Nested list validation (phases, vacancies, documents)
        for list_field in ["phases", "vacancies", "documents_required"]:
            if list_field in data:
                data[list_field] = self._validate_list_field(data[list_field])
        if penalty > 0:
            self.repair_count += 1
        return data, min(penalty, 0.5)
    # â”€â”€â”€ JSON Extraction â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _extract_json(self, text: str) -> Optional[dict]:
        """Extract JSON object from LLM response that may contain markdown or prose."""
        if not text or not text.strip():
            return None
        text = text.strip()
        # Try direct parse
        try:
            result = json.loads(text)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass
        # Try extracting from markdown code block
        patterns = [
            r'```json\s*\n(.*?)\n\s*```',
            r'```\s*\n(.*?)\n\s*```',
            r'(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    result = json.loads(match.group(1))
                    if isinstance(result, dict):
                        return result
                except json.JSONDecodeError:
                    continue
        # Try finding the outermost { ... }
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start >= 0 and brace_end > brace_start:
            candidate = text[brace_start : brace_end + 1]
            try:
                result = json.loads(candidate)
                if isinstance(result, dict):
                    return result
            except json.JSONDecodeError:
                pass
        return None
    # â”€â”€â”€ Structural JSON Repair â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _repair_json_structure(self, text: str) -> str:
        """Fix common JSON structural issues from LLM output."""
        # Extract the JSON-looking portion
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start < 0:
            return text
        if brace_end <= brace_start:
            # Missing closing brace â€” try to fix
            candidate = text[brace_start:]
        else:
            candidate = text[brace_start : brace_end + 1]
        # Fix trailing commas before } or ]
        candidate = re.sub(r',\s*([}\]])', r'\1', candidate)
        # Fix single quotes â†’ double quotes (but not inside strings)
        candidate = self._fix_quotes(candidate)
        # Fix unquoted keys
        candidate = re.sub(r'(?<=[{,])\s*(\w+)\s*:', r' "\1":', candidate)
        # Fix None â†’ null, True â†’ true, False â†’ false
        candidate = candidate.replace(": None", ": null")
        candidate = candidate.replace(": True", ": true")
        candidate = candidate.replace(": False", ": false")
        candidate = re.sub(r':\s*None\b', ': null', candidate)
        # Balance braces
        open_braces = candidate.count("{") - candidate.count("}")
        if open_braces > 0:
            candidate += "}" * open_braces
        open_brackets = candidate.count("[") - candidate.count("]")
        if open_brackets > 0:
            candidate += "]" * open_brackets
        # Remove comments (// and /* */)
        candidate = re.sub(r'//.*?$', '', candidate, flags=re.MULTILINE)
        candidate = re.sub(r'/\*.*?\*/', '', candidate, flags=re.DOTALL)
        return candidate
    def _fix_quotes(self, text: str) -> str:
        """Convert single-quoted strings to double-quoted, carefully."""
        result = []
        i = 0
        in_double = False
        in_single = False
        while i < len(text):
            ch = text[i]
            if ch == '"' and not in_single:
                in_double = not in_double
                result.append(ch)
            elif ch == "'" and not in_double:
                in_single = not in_single
                result.append('"')
            elif ch == '\\' and i + 1 < len(text):
                result.append(ch)
                result.append(text[i + 1])
                i += 1
            else:
                result.append(ch)
            i += 1
        return "".join(result)
    # â”€â”€â”€ Type Coercion â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _coerce_numeric(self, value: Any) -> tuple[Any, float]:
        """Try to coerce a value to numeric. Returns (value, penalty)."""
        if isinstance(value, (int, float)):
            return value, 0.0
        if isinstance(value, str):
            # Remove currency symbols, commas
            cleaned = re.sub(r'[â‚¹$,Rs\.INR\s]', '', value)
            try:
                if '.' in cleaned:
                    return float(cleaned), 0.02
                return int(cleaned), 0.02
            except (ValueError, TypeError):
                pass
        return value, 0.0
    # â”€â”€â”€ Enum Correction â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _correct_enum(self, value: str, valid_values: list[str]) -> tuple[str, float]:
        """Fuzzy-match a value against valid enum values."""
        if value in valid_values:
            return value, 0.0
        # Case-insensitive exact match
        value_lower = value.lower().strip()
        for v in valid_values:
            if v.lower() == value_lower:
                return v, 0.01
        # Substring match
        for v in valid_values:
            if value_lower in v.lower() or v.lower() in value_lower:
                logger.debug("Enum correction: '%s' â†’ '%s'", value, v)
                return v, 0.05
        # Replace underscores/spaces/hyphens and retry
        normalized = re.sub(r'[\s\-_]+', '_', value_lower)
        for v in valid_values:
            if re.sub(r'[\s\-_]+', '_', v.lower()) == normalized:
                return v, 0.03
        # No match â€” return original (will be caught by Pydantic validation)
        logger.warning("No enum match for '%s' in %s", value, valid_values[:5])
        return value, 0.1
    # â”€â”€â”€ Date Plausibility â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _validate_date(self, value: str, field_name: str) -> tuple[Optional[str], float]:
        """Check if a date string is plausible. Nullify hallucinated dates."""
        if not value or not isinstance(value, str):
            return value, 0.0
        # Try parsing
        parsed = self._try_parse_date(value)
        if parsed is None:
            logger.debug("Unparseable date in %s: '%s'", field_name, value)
            return value, 0.05  # Keep raw â€” might be parseable downstream
        year = parsed.year
        # Plausibility check
        if year < MIN_PLAUSIBLE_YEAR:
            logger.warning("Implausible past date in %s: %s (year %d)", field_name, value, year)
            return None, 0.15  # Nullify â€” almost certainly hallucinated
        if year > MAX_PLAUSIBLE_YEAR:
            logger.warning("Implausible future date in %s: %s (year %d)", field_name, value, year)
            return None, 0.15
        # If date is > 5 years in the future for application dates, suspicious
        if "application" in field_name.lower():
            days_away = (parsed - date.today()).days
            if days_away > 365 * 3:
                logger.warning("Suspiciously far future application date: %s = %s", field_name, value)
                return None, 0.1
        return value, 0.0
    def _try_parse_date(self, text: str) -> Optional[date]:
        """Try multiple date formats. Return date or None."""
        formats = [
            "%Y-%m-%d",             # ISO
            "%d/%m/%Y",             # Indian DD/MM/YYYY
            "%d-%m-%Y",             # Indian DD-MM-YYYY
            "%d.%m.%Y",             # DD.MM.YYYY
            "%d %B %Y",             # 15 March 2025
            "%B %d, %Y",           # March 15, 2025
            "%d %b %Y",            # 15 Mar 2025
            "%b %d, %Y",           # Mar 15, 2025
            "%Y-%m-%dT%H:%M:%S",   # ISO with time
        ]
        for fmt in formats:
            try:
                return datetime.strptime(text.strip(), fmt).date()
            except ValueError:
                continue
        return None
    # â”€â”€â”€ List Field Validation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _validate_list_field(self, value: Any) -> list:
        """Ensure a field that should be a list is actually a list."""
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            # Try parsing as JSON array
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed
            except (json.JSONDecodeError, TypeError):
                pass
            # Split comma-separated string
            if "," in value:
                return [item.strip() for item in value.split(",") if item.strip()]
            return [value]
        return [value]
    # â”€â”€â”€ Stats â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def get_stats(self) -> dict:
        return {
            "repaired": self.repair_count,
            "rejected": self.reject_count,
            "total_processed": self.repair_count + self.reject_count,
        }
# â”€â”€ Convenience: Pre-configured hardener for scheme classification â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def create_scheme_hardener() -> LLMResponseHardener:
    return LLMResponseHardener(valid_enums={
        "level": ["Central", "State", "Union_Territory"],
        "sector": [
            "Education", "Agriculture", "Fisheries", "MSME", "Startup",
            "Science_Technology", "Health", "Women_Child_Development",
            "Social_Justice", "Tribal_Affairs", "Minority_Affairs",
            "Rural_Development", "Urban_Development", "Labour_Employment",
            "Skill_Development", "Housing", "Finance", "Industry",
            "IT_Electronics", "Textiles", "Food_Processing", "Environment",
            "Energy", "Transport", "Tourism", "Sports_Youth", "Culture",
            "Defence", "Disability", "General",
        ],
        "scheme_type": [
            "Scholarship", "Grant", "Startup_Fund", "Subsidy", "Loan",
            "Pension", "Insurance", "Fellowship", "Award", "Stipend", "Other",
        ],
    })
def create_exam_hardener() -> LLMResponseHardener:
    return LLMResponseHardener(valid_enums={
        "exam_category": [
            "Civil_Services", "Banking", "Railway", "Defence", "Police",
            "Intelligence", "SSC", "PSU", "Medical", "Engineering",
            "Teaching", "Insurance", "Revenue", "Judiciary", "Agriculture",
            "State_PSC", "State_Police", "State_Teaching",
            "State_Subordinate", "Other_Central",
        ],
        "exam_level": ["Central", "State", "UT"],
    })
