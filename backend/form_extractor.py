"""Form Extraction Engine — Uses Claude Sonnet 4.5 via Emergent LLM to analyze PDFs and extract form fields."""
import os
import json
import logging
import tempfile
import httpx
import pdfplumber
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / '.env')
logger = logging.getLogger(__name__)

EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

EXTRACTION_SYSTEM_PROMPT = """You are an expert at analyzing Indian government application forms and official documents.
Given the text content extracted from a PDF form, you must identify EVERY single field/question that an applicant needs to fill.

Output a JSON object with this exact structure:
{
  "schemeName": "Official scheme name",
  "schemeNameHindi": "Hindi name if available",
  "category": "housing|education|agriculture|startup|health|finance|general",
  "totalFields": <number>,
  "sections": [{"name": "Section Name", "nameHindi": "Hindi section name"}],
  "extractedFields": [
    {
      "fieldName": "snake_case_unique_key",
      "labelHindi": "Hindi label for the field",
      "labelEnglish": "English label for the field",
      "type": "text|number|date|select|phone|email|aadhaar|textarea",
      "required": true/false,
      "section": "Section Name this field belongs to",
      "options": ["option1", "option2"] (only for type=select),
      "profileKey": "snake_case key to store in user profile"
    }
  ]
}

Rules:
- Extract EVERY field from the form — do not skip any
- Use appropriate types: aadhaar for 12-digit Aadhaar, phone for mobile numbers, date for dates
- For Yes/No questions, use type=select with options ["No", "Yes"]
- profileKey should be a reusable key (e.g., "name", "aadhaar_number", "annual_income") so it can match across schemes
- Group fields into logical sections
- Hindi labels are mandatory for every field
- Output ONLY valid JSON, no markdown code blocks or extra text"""


async def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text content from a local PDF file using pdfplumber."""
    text_parts = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(f"--- Page {i+1} ---\n{page_text}")
                # Also extract tables
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if row:
                            text_parts.append(" | ".join([str(cell or "") for cell in row]))
    except Exception as e:
        logger.error(f"PDF text extraction failed: {e}")
    return "\n\n".join(text_parts)


async def download_pdf(url: str) -> str:
    """Download a PDF from URL to a temp file. Returns file path."""
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
            tmp.write(resp.content)
            tmp.close()
            return tmp.name
    except Exception as e:
        logger.error(f"PDF download failed from {url}: {e}")
        return ""


async def extract_form_fields_llm(pdf_text: str, scheme_hint: str = "") -> dict:
    """Use Claude Sonnet 4.5 to analyze PDF text and extract structured form fields."""
    if not EMERGENT_KEY:
        logger.error("EMERGENT_LLM_KEY not set")
        return {"error": "LLM key not configured"}

    from emergentintegrations.llm.chat import LlmChat, UserMessage

    chat = LlmChat(
        api_key=EMERGENT_KEY,
        session_id=f"form_extract_{scheme_hint[:20]}",
        system_message=EXTRACTION_SYSTEM_PROMPT,
    ).with_model("anthropic", "claude-sonnet-4-20250514")

    prompt = f"Analyze this government form/document and extract ALL fields:\n\n{pdf_text[:15000]}"
    if scheme_hint:
        prompt = f"Scheme: {scheme_hint}\n\n{prompt}"

    try:
        response = await chat.send_message(UserMessage(text=prompt))
        # Parse the JSON response
        text = response.strip()
        # Remove markdown code blocks if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        if text.startswith("json"):
            text = text[4:]
        result = json.loads(text.strip())
        return result
    except json.JSONDecodeError as e:
        logger.error(f"LLM response JSON parse failed: {e}\nRaw: {response[:500]}")
        return {"error": f"Failed to parse LLM response: {str(e)}"}
    except Exception as e:
        logger.error(f"LLM form extraction failed: {e}")
        return {"error": str(e)}


async def extract_form_fields(pdf_url: str = "", pdf_path: str = "", scheme_hint: str = "") -> dict:
    """Main entry: extract form fields from a PDF URL or local file.

    Returns a complete FormTemplate-compatible dict with extractedFields.
    """
    local_path = pdf_path
    if pdf_url and not pdf_path:
        local_path = await download_pdf(pdf_url)
        if not local_path:
            return {"error": f"Could not download PDF from {pdf_url}"}

    if not local_path or not Path(local_path).exists():
        return {"error": "No valid PDF file provided"}

    # Step 1: Extract text
    pdf_text = await extract_text_from_pdf(local_path)
    if not pdf_text or len(pdf_text.strip()) < 50:
        return {"error": "Could not extract sufficient text from PDF. The PDF may be image-based (scanned)."}

    # Step 2: LLM analysis
    result = await extract_form_fields_llm(pdf_text, scheme_hint)

    # Clean up temp file if we downloaded it
    if pdf_url and local_path and not pdf_path:
        try:
            os.unlink(local_path)
        except Exception:
            pass

    return result
