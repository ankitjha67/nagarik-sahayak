"""
Tests for the PDF form extraction pipeline.

Covers:
- Text extraction (pdfplumber, PyMuPDF fallback)
- AcroForm field parsing
- OCR graceful degradation
- Multi-strategy pipeline
- Text sanitization and limits
- LLM extraction (mocked)
- Download + extraction flow
"""
import os
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017/test")
os.environ.setdefault("EMERGENT_LLM_KEY", "")

import pytest

# Add backend dir to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ─── Helper: create a minimal valid PDF (text-based) ───

def _create_text_pdf(text: str = "Applicant Name: ________\nAadhaar Number: ________\nDate of Birth: ________") -> str:
    """Create a minimal PDF with given text content using fpdf2. Returns temp file path."""
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    for line in text.split("\n"):
        pdf.cell(0, 10, text=line, new_x="LMARGIN", new_y="NEXT")
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    pdf.output(tmp.name)
    return tmp.name


def _create_empty_pdf() -> str:
    """Create a PDF with no text content (blank page)."""
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    pdf.output(tmp.name)
    return tmp.name


# ─── Text sanitization ───

class TestSanitization:
    def test_sanitize_removes_control_chars(self):
        from form_extractor import _sanitize_pdf_text
        text = "Hello\x00World\x07Test\nOK"
        result = _sanitize_pdf_text(text)
        assert "\x00" not in result
        assert "\x07" not in result
        assert "Hello" in result
        assert "\n" in result  # newlines preserved

    def test_sanitize_collapses_whitespace(self):
        from form_extractor import _sanitize_pdf_text
        text = "Field1" + " " * 20 + "Field2"
        result = _sanitize_pdf_text(text)
        assert "   " in result  # collapsed to 3 spaces
        assert " " * 20 not in result

    def test_sanitize_collapses_newlines(self):
        from form_extractor import _sanitize_pdf_text
        text = "Section1" + "\n" * 10 + "Section2"
        result = _sanitize_pdf_text(text)
        assert "\n" * 10 not in result
        assert "\n\n\n" in result

    def test_sanitize_respects_max_length(self):
        from form_extractor import _sanitize_pdf_text, MAX_PDF_TEXT_LENGTH
        text = "A" * (MAX_PDF_TEXT_LENGTH + 10000)
        result = _sanitize_pdf_text(text)
        assert len(result) == MAX_PDF_TEXT_LENGTH

    def test_max_text_length_is_50000(self):
        from form_extractor import MAX_PDF_TEXT_LENGTH
        assert MAX_PDF_TEXT_LENGTH == 50000


# ─── Pdfplumber text extraction ───

class TestPdfplumberExtraction:
    def test_extract_text_from_valid_pdf(self):
        from form_extractor import _extract_with_pdfplumber
        pdf_path = _create_text_pdf("Name: ________\nPhone: ________")
        try:
            text = _extract_with_pdfplumber(pdf_path)
            assert "Name" in text
            assert "Phone" in text
        finally:
            os.unlink(pdf_path)

    def test_extract_text_from_empty_pdf(self):
        from form_extractor import _extract_with_pdfplumber
        pdf_path = _create_empty_pdf()
        try:
            text = _extract_with_pdfplumber(pdf_path)
            assert text.strip() == ""
        finally:
            os.unlink(pdf_path)

    def test_extract_text_from_nonexistent_file(self):
        from form_extractor import _extract_with_pdfplumber
        text = _extract_with_pdfplumber("/tmp/nonexistent_abc123.pdf")
        assert text == ""

    def test_extract_multipage_pdf(self):
        from fpdf import FPDF
        from form_extractor import _extract_with_pdfplumber
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        pdf.cell(0, 10, text="Page One Content")
        pdf.add_page()
        pdf.cell(0, 10, text="Page Two Content")
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        pdf.output(tmp.name)
        try:
            text = _extract_with_pdfplumber(tmp.name)
            assert "Page 1" in text
            assert "Page 2" in text
            assert "Page One Content" in text
            assert "Page Two Content" in text
        finally:
            os.unlink(tmp.name)


# ─── AcroForm parsing ───

class TestAcroFormExtraction:
    def test_acroform_returns_empty_for_non_fillable(self):
        from form_extractor import extract_acroform_fields
        pdf_path = _create_text_pdf("Just plain text")
        try:
            fields = extract_acroform_fields(pdf_path)
            assert isinstance(fields, list)
            assert len(fields) == 0  # no form fields in a plain text PDF
        finally:
            os.unlink(pdf_path)

    def test_acroform_handles_nonexistent_file(self):
        from form_extractor import extract_acroform_fields
        fields = extract_acroform_fields("/tmp/nonexistent_form_abc.pdf")
        assert isinstance(fields, list)
        assert len(fields) == 0

    def test_widget_type_mapping(self):
        from form_extractor import _map_widget_type
        assert _map_widget_type(1) == "text"
        assert _map_widget_type(3) == "checkbox"
        assert _map_widget_type(4) == "radio"
        assert _map_widget_type(5) == "select"
        assert _map_widget_type(6) == "select"
        assert _map_widget_type(7) == "signature"
        assert _map_widget_type(99) == "text"  # unknown defaults to text

    def test_format_acroform_for_llm_empty(self):
        from form_extractor import _format_acroform_for_llm
        assert _format_acroform_for_llm([]) == ""

    def test_format_acroform_for_llm_with_fields(self):
        from form_extractor import _format_acroform_for_llm
        fields = [
            {"field_name": "applicant_name", "field_type": "text", "value": ""},
            {"field_name": "category", "field_type": "select", "options": ["SC", "ST", "OBC"], "required": True},
        ]
        result = _format_acroform_for_llm(fields)
        assert "AcroForm Fields" in result
        assert "applicant_name" in result
        assert "category" in result
        assert "SC, ST, OBC" in result
        assert "REQUIRED" in result


# ─── OCR graceful degradation ───

class TestOCR:
    def test_ocr_returns_empty_when_libs_missing(self):
        from form_extractor import ocr_pdf
        with patch("form_extractor._HAS_FITZ", False), \
             patch("form_extractor._HAS_TESSERACT", False):
            result = ocr_pdf("/tmp/any.pdf")
            assert result == ""

    def test_fitz_extract_returns_empty_when_missing(self):
        from form_extractor import _fitz_extract_text
        with patch("form_extractor._HAS_FITZ", False):
            result = _fitz_extract_text("/tmp/any.pdf")
            assert result == ""

    def test_ocr_requires_both_fitz_and_tesseract(self):
        from form_extractor import ocr_pdf
        with patch("form_extractor._HAS_FITZ", True), \
             patch("form_extractor._HAS_TESSERACT", False):
            result = ocr_pdf("/tmp/any.pdf")
            assert result == ""


# ─── Multi-strategy pipeline ───

class TestMultiStrategyPipeline:
    @pytest.mark.asyncio
    async def test_pipeline_uses_pdfplumber_for_text_pdf(self):
        from form_extractor import extract_text_from_pdf
        pdf_path = _create_text_pdf("Name: Test User\nPhone: 9876543210\nAadhaar: 123456789012")
        try:
            result = await extract_text_from_pdf(pdf_path)
            assert "pdfplumber" in result["extraction_method"]
            assert "Name" in result["text"]
            assert "Phone" in result["text"]
        finally:
            os.unlink(pdf_path)

    @pytest.mark.asyncio
    async def test_pipeline_returns_insufficient_for_empty_pdf(self):
        from form_extractor import extract_text_from_pdf
        pdf_path = _create_empty_pdf()
        try:
            result = await extract_text_from_pdf(pdf_path)
            assert "insufficient" in result["extraction_method"] or result["extraction_method"] == "none"
            assert len(result["text"].strip()) < 50
        finally:
            os.unlink(pdf_path)

    @pytest.mark.asyncio
    async def test_pipeline_result_structure(self):
        from form_extractor import extract_text_from_pdf
        pdf_path = _create_text_pdf("Hello World - This is a test form with enough content to pass threshold")
        try:
            result = await extract_text_from_pdf(pdf_path)
            assert "text" in result
            assert "acroform_fields" in result
            assert "extraction_method" in result
            assert isinstance(result["acroform_fields"], list)
        finally:
            os.unlink(pdf_path)

    @pytest.mark.asyncio
    async def test_pipeline_fitz_fallback(self):
        """When pdfplumber returns little text, fitz should be tried."""
        from form_extractor import extract_text_from_pdf
        pdf_path = _create_text_pdf("Short")
        try:
            with patch("form_extractor._extract_with_pdfplumber", return_value=""):
                result = await extract_text_from_pdf(pdf_path)
                # Should have tried fitz fallback
                method = result["extraction_method"]
                assert method in ("pymupdf", "none", "insufficient_text_no_ocr",
                                  "insufficient_text", "pymupdf+acroform")
        finally:
            os.unlink(pdf_path)


# ─── Full extraction flow (with mocked LLM) ───

class TestExtractFormFields:
    @pytest.mark.asyncio
    async def test_extract_no_pdf_provided(self):
        from form_extractor import extract_form_fields
        result = await extract_form_fields()
        assert "error" in result

    @pytest.mark.asyncio
    async def test_extract_nonexistent_file(self):
        from form_extractor import extract_form_fields
        result = await extract_form_fields(pdf_path="/tmp/nonexistent_form_xyz.pdf")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_extract_valid_pdf_with_mocked_llm(self):
        from form_extractor import extract_form_fields
        pdf_path = _create_text_pdf(
            "PRADHAN MANTRI AWAS YOJANA\n"
            "Application Form\n"
            "1. Applicant Name: ________\n"
            "2. Father/Husband Name: ________\n"
            "3. Aadhaar Number: ________\n"
            "4. Date of Birth: __ / __ / ____\n"
            "5. Mobile Number: ________\n"
            "6. Annual Income: ________\n"
        )
        mock_llm_response = {
            "schemeName": "Pradhan Mantri Awas Yojana",
            "schemeNameHindi": "प्रधानमंत्री आवास योजना",
            "category": "housing",
            "totalFields": 6,
            "sections": [{"name": "Personal Details", "nameHindi": "व्यक्तिगत विवरण"}],
            "extractedFields": [
                {"fieldName": "applicant_name", "labelHindi": "आवेदक का नाम", "labelEnglish": "Applicant Name",
                 "type": "text", "required": True, "section": "Personal Details", "profileKey": "name"},
            ],
        }
        try:
            with patch("form_extractor.extract_form_fields_llm", new_callable=AsyncMock, return_value=mock_llm_response):
                result = await extract_form_fields(pdf_path=pdf_path, scheme_hint="PMAY")
                assert "error" not in result
                assert result["schemeName"] == "Pradhan Mantri Awas Yojana"
                assert result["totalFields"] == 6
                assert "_extraction_method" in result
                assert "_text_length" in result
        finally:
            os.unlink(pdf_path)

    @pytest.mark.asyncio
    async def test_extract_empty_pdf_returns_error(self):
        from form_extractor import extract_form_fields
        pdf_path = _create_empty_pdf()
        try:
            result = await extract_form_fields(pdf_path=pdf_path)
            assert "error" in result
            assert "text" in result["error"].lower() or "ocr" in result["error"].lower()
        finally:
            os.unlink(pdf_path)

    @pytest.mark.asyncio
    async def test_extract_attaches_metadata(self):
        from form_extractor import extract_form_fields
        pdf_path = _create_text_pdf("Government Form\n" * 20)
        mock_result = {
            "schemeName": "Test Scheme",
            "totalFields": 1,
            "extractedFields": [{"fieldName": "test"}],
        }
        try:
            with patch("form_extractor.extract_form_fields_llm", new_callable=AsyncMock, return_value=mock_result):
                result = await extract_form_fields(pdf_path=pdf_path)
                assert "_extraction_method" in result
                assert "_acroform_field_count" in result
                assert "_text_length" in result
                assert result["_text_length"] > 0
        finally:
            os.unlink(pdf_path)


# ─── LLM extraction (mocked) ───

class TestLLMExtraction:
    @pytest.mark.asyncio
    async def test_llm_no_key_returns_error(self):
        from form_extractor import extract_form_fields_llm
        with patch("form_extractor.EMERGENT_KEY", ""):
            result = await extract_form_fields_llm("some text")
            assert "error" in result
            assert "key" in result["error"].lower()


# ─── Download ───

class TestDownload:
    @pytest.mark.asyncio
    async def test_download_invalid_url(self):
        from form_extractor import download_pdf
        result = await download_pdf("http://localhost:1/nonexistent.pdf")
        assert result == ""

    @pytest.mark.asyncio
    async def test_download_non_pdf_content(self):
        from form_extractor import download_pdf
        import httpx

        async def mock_get(*args, **kwargs):
            resp = MagicMock()
            resp.content = b"<html>Not a PDF</html>"
            resp.raise_for_status = MagicMock()
            return resp

        with patch("httpx.AsyncClient") as mock_client:
            instance = AsyncMock()
            instance.get = mock_get
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = instance
            result = await download_pdf("http://example.com/fake.pdf")
            assert result == ""


# ─── Safe unlink ───

class TestSafeUnlink:
    def test_safe_unlink_nonexistent(self):
        from form_extractor import _safe_unlink
        _safe_unlink("/tmp/this_file_does_not_exist_12345.pdf")  # should not raise

    def test_safe_unlink_real_file(self):
        from form_extractor import _safe_unlink
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        path = tmp.name
        tmp.close()
        assert os.path.exists(path)
        _safe_unlink(path)
        assert not os.path.exists(path)
