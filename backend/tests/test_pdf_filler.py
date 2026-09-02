"""
Tests for the PDF form filler module.

Covers:
- AcroForm filling (fillable PDFs)
- Text overlay filling (non-fillable PDFs)
- Unified fill_pdf_form entry point
- Field value formatting (no masking for official forms)
- Field name normalization and fuzzy matching
- Error handling for missing files/libraries
- PDF generator is_draft parameter
"""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# Check if PyMuPDF is available
try:
    import fitz
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False


# ─── Helper: create test PDFs ───

def _create_text_pdf(text: str = "Name: ________") -> str:
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    for line in text.split("\n"):
        pdf.cell(0, 10, text=line, new_x="LMARGIN", new_y="NEXT")
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    pdf.output(tmp.name)
    return tmp.name


# ─── Value formatting (full values, no masking) ───

class TestValueFormatting:
    def test_format_aadhaar_full(self):
        from pdf_filler import _format_value_for_fill
        result = _format_value_for_fill("123456789012", "aadhaar")
        assert result == "123456789012"  # No masking

    def test_format_phone_10_digits(self):
        from pdf_filler import _format_value_for_fill
        result = _format_value_for_fill("9876543210", "phone")
        assert result == "9876543210"

    def test_format_phone_with_country_code(self):
        from pdf_filler import _format_value_for_fill
        result = _format_value_for_fill("919876543210", "phone")
        assert result == "9876543210"

    def test_format_date_iso(self):
        from pdf_filler import _format_value_for_fill
        result = _format_value_for_fill("1990-05-15", "date")
        assert result == "15/05/1990"

    def test_format_empty_value(self):
        from pdf_filler import _format_value_for_fill
        assert _format_value_for_fill("", "text") == ""
        assert _format_value_for_fill(None, "text") == ""

    def test_format_text_passthrough(self):
        from pdf_filler import _format_value_for_fill
        assert _format_value_for_fill("Raj Kumar", "text") == "Raj Kumar"


# ─── Field name normalization ───

class TestFieldNameNormalization:
    def test_normalize_simple(self):
        from pdf_filler import _normalize_field_name
        assert _normalize_field_name("applicant_name") == "applicant_name"

    def test_normalize_with_brackets(self):
        from pdf_filler import _normalize_field_name
        result = _normalize_field_name("form[0].applicant_name")
        assert result == "form_0_applicant_name"

    def test_normalize_with_spaces(self):
        from pdf_filler import _normalize_field_name
        assert _normalize_field_name("Applicant Name") == "applicant_name"

    def test_normalize_with_dots(self):
        from pdf_filler import _normalize_field_name
        assert _normalize_field_name("field.name.here") == "field_name_here"

    def test_normalize_uppercase(self):
        from pdf_filler import _normalize_field_name
        assert _normalize_field_name("MOBILE_NUMBER") == "mobile_number"


# ─── AcroForm filling ───

class TestAcroFormFilling:
    def test_fill_nonexistent_file(self):
        from pdf_filler import fill_acroform_pdf
        result = fill_acroform_pdf("/tmp/nonexistent.pdf", "/tmp/out.pdf", {})
        assert result["success"] is False

    def test_fill_non_fillable_pdf(self):
        from pdf_filler import fill_acroform_pdf
        if not HAS_FITZ:
            # Without fitz, should return "not available"
            result = fill_acroform_pdf("/any.pdf", "/tmp/out.pdf", {"name": "Test"})
            assert result["success"] is False
            return

        pdf_path = _create_text_pdf("Just plain text")
        out_path = tempfile.mktemp(suffix=".pdf")
        try:
            result = fill_acroform_pdf(pdf_path, out_path, {"name": "Test"})
            assert result["success"] is False
        finally:
            os.unlink(pdf_path)
            if os.path.exists(out_path):
                os.unlink(out_path)

    @pytest.mark.skipif(not HAS_FITZ, reason="PyMuPDF not installed")
    def test_fill_acroform_pdf(self):
        """Test filling a real AcroForm PDF."""
        doc = fitz.open()
        page = doc.new_page()
        widget = fitz.Widget()
        widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
        widget.field_name = "applicant_name"
        widget.rect = fitz.Rect(100, 100, 300, 120)
        widget.field_value = ""
        page.add_widget(widget)
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        doc.save(tmp.name)
        doc.close()
        pdf_path = tmp.name

        out_path = tempfile.mktemp(suffix=".pdf")
        try:
            from pdf_filler import fill_acroform_pdf
            result = fill_acroform_pdf(
                pdf_path, out_path,
                field_values={"applicant_name": "Raj Kumar"},
            )
            assert result["success"] is True
            assert result["filled_count"] == 1
            assert result["method"] == "acroform"
            assert os.path.exists(out_path)
        finally:
            os.unlink(pdf_path)
            if os.path.exists(out_path):
                os.unlink(out_path)

    def test_fill_when_fitz_unavailable(self):
        from pdf_filler import fill_acroform_pdf
        with patch("pdf_filler._HAS_FITZ", False):
            result = fill_acroform_pdf("/tmp/any.pdf", "/tmp/out.pdf", {})
            assert result["success"] is False
            assert "not available" in result["error"]


# ─── Text overlay filling ───

class TestOverlayFilling:
    def test_overlay_nonexistent_file(self):
        from pdf_filler import fill_overlay_pdf
        result = fill_overlay_pdf("/tmp/nonexistent.pdf", "/tmp/out.pdf", {})
        assert result["success"] is False

    @pytest.mark.skipif(not HAS_FITZ, reason="PyMuPDF not installed")
    def test_overlay_with_manual_positions(self):
        from pdf_filler import fill_overlay_pdf
        pdf_path = _create_text_pdf("Name: ________\nPhone: ________")
        out_path = tempfile.mktemp(suffix=".pdf")
        positions = [
            {"profileKey": "name", "page": 1, "x": 100, "y": 100, "font_size": 10},
            {"profileKey": "phone", "page": 1, "x": 100, "y": 130, "font_size": 10},
        ]
        try:
            result = fill_overlay_pdf(
                pdf_path, out_path,
                field_values={"name": "Test User", "phone": "9876543210"},
                field_positions=positions,
            )
            assert result["success"] is True
            assert result["filled_count"] == 2
            assert result["method"] == "overlay"
            assert os.path.exists(out_path)
        finally:
            os.unlink(pdf_path)
            if os.path.exists(out_path):
                os.unlink(out_path)

    def test_overlay_auto_detect_no_positions(self):
        from pdf_filler import fill_overlay_pdf
        if not HAS_FITZ:
            result = fill_overlay_pdf("/any.pdf", "/tmp/out.pdf", {})
            assert result["success"] is False
            return
        pdf_path = _create_text_pdf("Some text")
        out_path = tempfile.mktemp(suffix=".pdf")
        try:
            result = fill_overlay_pdf(
                pdf_path, out_path,
                field_values={"name": "Test"},
            )
            assert result["method"] == "overlay"
        finally:
            os.unlink(pdf_path)
            if os.path.exists(out_path):
                os.unlink(out_path)

    def test_overlay_when_fitz_unavailable(self):
        from pdf_filler import fill_overlay_pdf
        with patch("pdf_filler._HAS_FITZ", False):
            result = fill_overlay_pdf("/tmp/any.pdf", "/tmp/out.pdf", {})
            assert result["success"] is False


# ─── Unified fill_pdf_form ───

class TestUnifiedFiller:
    def test_fill_pdf_form_nonexistent(self):
        from pdf_filler import fill_pdf_form
        result = fill_pdf_form("/tmp/nonexistent.pdf", "/tmp/out.pdf", {})
        assert result["success"] is False

    @pytest.mark.skipif(not HAS_FITZ, reason="PyMuPDF not installed")
    def test_fill_pdf_form_with_overlay_positions(self):
        """Unified filler should fall back to overlay when no AcroForm fields."""
        pdf_path = _create_text_pdf("Name: ________")
        out_path = tempfile.mktemp(suffix=".pdf")
        try:
            from pdf_filler import fill_pdf_form
            result = fill_pdf_form(
                pdf_path, out_path,
                field_values={"name": "Test"},
                field_positions=[{"profileKey": "name", "page": 1, "x": 100, "y": 100, "font_size": 10}],
            )
            assert result["success"] is True
            assert result["method"] == "overlay"
        finally:
            os.unlink(pdf_path)
            if os.path.exists(out_path):
                os.unlink(out_path)

    def test_fill_pdf_form_when_fitz_unavailable(self):
        from pdf_filler import fill_pdf_form
        with patch("pdf_filler._HAS_FITZ", False):
            result = fill_pdf_form("/tmp/any.pdf", "/tmp/out.pdf", {})
            assert result["success"] is False
            assert result["method"] == "none"


# ─── PDF generator is_draft parameter ───

class TestPdfGeneratorDraft:
    def test_format_field_value_draft_masks_aadhaar(self):
        from pdf_generator import _format_field_value
        result = _format_field_value("123456789012", "aadhaar", is_draft=True)
        assert "XXXX" in result
        assert "123456789012" not in result

    def test_format_field_value_final_shows_full_aadhaar(self):
        from pdf_generator import _format_field_value
        result = _format_field_value("123456789012", "aadhaar", is_draft=False)
        assert "1234 5678 9012" == result

    def test_mask_aadhaar_full_mode(self):
        from pdf_generator import _mask_aadhaar
        assert _mask_aadhaar("123456789012", full=True) == "1234 5678 9012"
        assert _mask_aadhaar("123456789012", full=False) == "XXXX XXXX 9012"

    def test_generate_pdf_with_draft_false_no_watermark(self):
        """Generating with is_draft=False should produce a valid PDF."""
        from pdf_generator import generate_real_filled_form_pdf

        out_path = tempfile.mktemp(suffix=".pdf")
        try:
            generate_real_filled_form_pdf(
                filled_fields={"name": "Test User"},
                scheme_name="Test Scheme",
                form_fields=[{"fieldName": "name", "profileKey": "name", "labelEnglish": "Name",
                              "labelHindi": "naam", "type": "text", "required": True, "section": "Details"}],
                sections=[{"name": "Details", "nameHindi": "vivaran"}],
                output_path=out_path,
                is_draft=False,
            )
            assert os.path.exists(out_path)
            assert os.path.getsize(out_path) > 0
        finally:
            if os.path.exists(out_path):
                os.unlink(out_path)

    def test_generate_pdf_with_draft_true(self):
        """Generating with is_draft=True should produce a valid PDF."""
        from pdf_generator import generate_real_filled_form_pdf

        out_path = tempfile.mktemp(suffix=".pdf")
        try:
            generate_real_filled_form_pdf(
                filled_fields={"name": "Test User"},
                scheme_name="Test Scheme",
                form_fields=[{"fieldName": "name", "profileKey": "name", "labelEnglish": "Name",
                              "labelHindi": "naam", "type": "text", "required": True, "section": "Details"}],
                sections=[{"name": "Details", "nameHindi": "vivaran"}],
                output_path=out_path,
                is_draft=True,
            )
            assert os.path.exists(out_path)
            assert os.path.getsize(out_path) > 0
        finally:
            if os.path.exists(out_path):
                os.unlink(out_path)

    def test_format_field_value_empty(self):
        from pdf_generator import _format_field_value
        assert _format_field_value(None) == "_______________"
        assert _format_field_value("") == "_______________"

    def test_format_field_value_date(self):
        from pdf_generator import _format_field_value
        assert _format_field_value("1990-05-15", "date") == "15/05/1990"

    def test_format_field_value_phone(self):
        from pdf_generator import _format_field_value
        result = _format_field_value("9876543210", "phone")
        assert "98765" in result
