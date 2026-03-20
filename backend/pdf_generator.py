"""
PDF generation for Nagarik Sahayak eligibility reports.
Uses fpdf2 with Noto Sans (English) + Noto Sans Devanagari (Hindi).
"""
import re
from fpdf import FPDF
from pathlib import Path
from datetime import datetime, timezone

FONTS_DIR = Path(__file__).parent / "fonts"


def _format_date(value: str) -> str:
    """Format date values to DD/MM/YYYY if recognizable."""
    if not value or value == "_______________":
        return value
    # Try ISO format (YYYY-MM-DD)
    match = re.match(r'^(\d{4})-(\d{2})-(\d{2})', str(value))
    if match:
        return f"{match.group(3)}/{match.group(2)}/{match.group(1)}"
    return str(value)


def _format_phone(value: str) -> str:
    """Format phone number with spacing for readability."""
    digits = re.sub(r'\D', '', str(value))
    if len(digits) == 10:
        return f"+91 {digits[:5]} {digits[5:]}"
    if len(digits) == 12 and digits.startswith('91'):
        return f"+{digits[:2]} {digits[2:7]} {digits[7:]}"
    return str(value)


def _mask_aadhaar(value: str) -> str:
    """Mask Aadhaar number for display: XXXX XXXX 1234."""
    digits = re.sub(r'\D', '', str(value))
    if len(digits) == 12:
        return f"XXXX XXXX {digits[8:]}"
    return str(value)


def _format_field_value(value, field_type: str = "text") -> str:
    """Format field value based on type."""
    if value is None or value == "":
        return "_______________"
    val = str(value)
    if field_type == "date":
        return _format_date(val)
    elif field_type == "phone":
        return _format_phone(val)
    elif field_type == "aadhaar":
        return _mask_aadhaar(val)
    return val


def generate_eligibility_pdf(
    profile: dict,
    eligibility_results: list,
    scheme_detail: dict = None,
    output_path: str = "/tmp/report.pdf",
) -> str:
    """
    Generate a clean eligibility report PDF.

    Args:
        profile: {name, age, income, state}
        eligibility_results: list of {scheme, scheme_hi, eligible, reason, benefit}
        scheme_detail: optional single-scheme detail dict for focused report
        output_path: where to save the PDF

    Returns:
        path to generated PDF
    """
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)

    # Register fonts
    pdf.add_font("NS", "", str(FONTS_DIR / "NotoSans-Regular.ttf"))
    pdf.add_font("NS", "B", str(FONTS_DIR / "NotoSans-Bold.ttf"))
    pdf.add_font("NH", "", str(FONTS_DIR / "NotoSansDevanagari-Regular.ttf"))

    pdf.add_page()

    # === HEADER BAR ===
    pdf.set_fill_color(255, 153, 51)  # Saffron
    pdf.rect(0, 0, 210, 18, "F")
    pdf.set_fill_color(19, 136, 8)  # India Green
    pdf.rect(0, 18, 210, 2, "F")

    pdf.set_y(4)
    pdf.set_font("NS", "B", 16)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 10, "Nagarik Sahayak", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_y(22)
    pdf.set_font("NH", size=12)
    pdf.set_text_color(0, 0, 128)  # Navy
    pdf.cell(0, 8, "ELIGIBILITY REPORT", align="C", new_x="LMARGIN", new_y="NEXT")

    # Reference & date
    ref_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    pdf.set_font("NS", size=8)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 5, f"Ref: NS-{ref_id}  |  Date: {datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M UTC')}", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(4)

    # === PROFILE SECTION ===
    _section_header(pdf, "Applicant Profile")

    name = profile.get("name", "N/A")
    age = profile.get("age", "N/A")
    income = profile.get("income", 0)
    state = profile.get("state", "N/A")
    income_str = f"Rs {income:,}/month" if isinstance(income, (int, float)) and income > 0 else "N/A"

    _profile_row(pdf, "Name", str(name))
    _profile_row(pdf, "Age", f"{age} years")
    _profile_row(pdf, "Monthly Income", income_str)
    _profile_row(pdf, "State", str(state))

    pdf.ln(4)

    # === ELIGIBILITY RESULTS ===
    _section_header(pdf, "Scheme Eligibility Assessment")

    for r in eligibility_results:
        _eligibility_block(pdf, r)

    pdf.ln(4)

    # === SINGLE SCHEME DETAIL (optional) ===
    if scheme_detail:
        _section_header(pdf, f"Scheme Details: {scheme_detail.get('title', '')}")
        pdf.set_font("NS", size=9)
        pdf.set_text_color(60, 60, 60)

        desc = scheme_detail.get("description", "")
        if desc:
            pdf.multi_cell(0, 5, f"Description: {desc}")
            pdf.ln(2)

        elig = scheme_detail.get("eligibility", "")
        if elig:
            pdf.multi_cell(0, 5, f"Eligibility Criteria: {elig}")
            pdf.ln(2)

        benefits = scheme_detail.get("benefits", "")
        if benefits:
            pdf.multi_cell(0, 5, f"Benefits: {benefits}")
            pdf.ln(2)

        pdf_url = scheme_detail.get("pdf_url", "")
        if pdf_url:
            pdf.set_text_color(0, 0, 128)
            pdf.multi_cell(0, 5, f"Official Guidelines: {pdf_url}")
            pdf.set_text_color(60, 60, 60)

        pdf.ln(4)

    # === FOOTER ===
    pdf.ln(6)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(3)

    pdf.set_font("NS", size=7)
    pdf.set_text_color(150, 150, 150)
    pdf.multi_cell(0, 4, (
        "Disclaimer: This is an automated eligibility assessment based on the information provided. "
        "Final eligibility is subject to verification by the respective government authority. "
        "Please visit your nearest Common Service Centre (CSC) or the official scheme website for application.\n"
        "Generated by Nagarik Sahayak | Digital India Initiative"
    ), align="C")

    pdf.output(output_path)
    return output_path


def _section_header(pdf: FPDF, title: str):
    pdf.set_fill_color(240, 240, 248)
    pdf.set_draw_color(0, 0, 128)
    pdf.set_font("NS", "B", 11)
    pdf.set_text_color(0, 0, 128)
    pdf.cell(0, 8, f"  {title}", fill=True, new_x="LMARGIN", new_y="NEXT", border="B")
    pdf.ln(3)


def _profile_row(pdf: FPDF, label: str, value: str):
    pdf.set_font("NS", "B", 9)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(45, 6, label)
    pdf.set_font("NS", size=9)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 6, value, new_x="LMARGIN", new_y="NEXT")


def _eligibility_block(pdf: FPDF, result: dict):
    eligible = result.get("eligible", False)
    scheme = result.get("scheme", "")
    reason = result.get("reason", "")
    benefit = result.get("benefit", "")

    # Background color
    if eligible:
        pdf.set_fill_color(240, 253, 244)  # green-50
        pdf.set_draw_color(34, 197, 94)
        status_text = "ELIGIBLE"
        status_color = (22, 163, 74)
    else:
        pdf.set_fill_color(254, 242, 242)  # red-50
        pdf.set_draw_color(239, 68, 68)
        status_text = "NOT ELIGIBLE"
        status_color = (220, 38, 38)

    y_start = pdf.get_y()
    pdf.rect(10, y_start, 190, 22, "DF")

    # Scheme name
    pdf.set_xy(14, y_start + 2)
    pdf.set_font("NS", "B", 10)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(130, 6, scheme)

    # Status badge
    pdf.set_font("NS", "B", 8)
    pdf.set_text_color(*status_color)
    pdf.cell(0, 6, status_text, align="R")

    # Reason
    pdf.set_xy(14, y_start + 9)
    pdf.set_font("NS", size=8)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 5, reason[:120], new_x="LMARGIN", new_y="NEXT")

    # Benefit (if eligible)
    if eligible and benefit:
        pdf.set_xy(14, y_start + 15)
        pdf.set_font("NS", size=8)
        pdf.set_text_color(22, 163, 74)
        pdf.cell(0, 5, f"Benefit: {benefit}")

    pdf.set_y(y_start + 25)



def generate_filled_form_pdf(
    profile: dict,
    scheme_name: str,
    scheme_criteria: str = "",
    output_path: str = "/tmp/filled_form.pdf",
) -> str:
    """
    Generate a pre-filled application form PDF with Hindi labels.
    Fields: naam, umr, aay, rajya, Scheme Name, Date (Hindi format).
    """
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)

    pdf.add_font("NS", "", str(FONTS_DIR / "NotoSans-Regular.ttf"))
    pdf.add_font("NS", "B", str(FONTS_DIR / "NotoSans-Bold.ttf"))
    pdf.add_font("NH", "", str(FONTS_DIR / "NotoSansDevanagari-Regular.ttf"))

    pdf.add_page()

    # === HEADER BAR (Saffron) ===
    pdf.set_fill_color(255, 153, 51)
    pdf.rect(0, 0, 210, 20, "F")
    pdf.set_fill_color(19, 136, 8)
    pdf.rect(0, 20, 210, 2, "F")

    pdf.set_y(5)
    pdf.set_font("NS", "B", 16)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 10, "Nagarik Sahayak", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_y(24)
    pdf.set_font("NS", "B", 13)
    pdf.set_text_color(0, 0, 128)
    pdf.cell(0, 8, "PRE-FILLED APPLICATION FORM", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("NS", size=9)
    pdf.set_text_color(0, 0, 128)
    pdf.cell(0, 6, "Bhara Hua Aavedan Form", align="C", new_x="LMARGIN", new_y="NEXT")

    # Reference & date in DD/MM/YYYY Hindi format
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%d/%m/%Y")
    ref_id = now.strftime("%Y%m%d%H%M%S")
    pdf.set_font("NS", size=8)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 5, f"Ref: NS-{ref_id}  |  Date: {date_str}", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(6)

    # === SCHEME INFO ===
    pdf.set_fill_color(240, 240, 248)
    pdf.set_draw_color(0, 0, 128)
    pdf.set_font("NS", "B", 11)
    pdf.set_text_color(0, 0, 128)
    pdf.cell(0, 8, f"  Scheme / Yojana: {scheme_name}", fill=True, new_x="LMARGIN", new_y="NEXT", border="B")
    pdf.ln(4)

    if scheme_criteria:
        pdf.set_font("NS", size=9)
        pdf.set_text_color(80, 80, 80)
        pdf.multi_cell(0, 5, f"Eligibility: {scheme_criteria}")
        pdf.ln(4)

    # === APPLICANT DETAILS (Hindi labels) ===
    pdf.set_fill_color(240, 240, 248)
    pdf.set_draw_color(0, 0, 128)
    pdf.set_font("NS", "B", 11)
    pdf.set_text_color(0, 0, 128)
    pdf.cell(0, 8, "  Applicant Details", fill=True, new_x="LMARGIN", new_y="NEXT", border="B")
    pdf.ln(4)

    name = profile.get("name", "N/A")
    age = profile.get("age", "N/A")
    income = profile.get("income", 0)
    state = profile.get("state", "N/A")
    income_str = f"Rs {income:,}/year" if isinstance(income, (int, float)) and income > 0 else "N/A"

    form_fields = [
        ("Naam / Name", str(name)),
        ("Umr / Age", f"{age} varsh / years"),
        ("Saalanaa Aay / Annual Income", income_str),
        ("Rajya / State", str(state)),
        ("Yojana / Scheme", scheme_name),
        ("Aavedan Tithi / Application Date", date_str),
    ]

    for label, value in form_fields:
        # Label
        pdf.set_font("NS", "B", 10)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(75, 8, label)
        # Value in a box
        pdf.set_font("NS", size=10)
        pdf.set_text_color(30, 30, 30)
        pdf.set_fill_color(255, 255, 255)
        pdf.set_draw_color(180, 180, 200)
        pdf.cell(0, 8, f"  {value}", border=1, fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

    pdf.ln(6)

    # === DECLARATION ===
    pdf.set_fill_color(240, 240, 248)
    pdf.set_draw_color(0, 0, 128)
    pdf.set_font("NS", "B", 11)
    pdf.set_text_color(0, 0, 128)
    pdf.cell(0, 8, "  Declaration", fill=True, new_x="LMARGIN", new_y="NEXT", border="B")
    pdf.ln(4)

    pdf.set_font("NS", size=9)
    pdf.set_text_color(60, 60, 60)
    pdf.multi_cell(0, 5, (
        "I hereby declare that the information provided above is true and correct "
        "to the best of my knowledge. I understand that any false information may "
        "lead to rejection of my application."
    ))
    pdf.ln(8)

    # Signature line
    pdf.set_font("NS", "B", 9)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(90, 6, "Signature / Hastakshar:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(100, 100, 100)
    pdf.line(10, pdf.get_y() + 15, 90, pdf.get_y() + 15)
    pdf.set_y(pdf.get_y() + 20)

    # === FOOTER ===
    pdf.set_draw_color(200, 200, 200)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(3)
    pdf.set_font("NS", size=7)
    pdf.set_text_color(150, 150, 150)
    pdf.multi_cell(0, 4, (
        "This is an auto-generated application form by Nagarik Sahayak. "
        "Please submit this form along with required documents at your nearest CSC or government office.\n"
        "Generated by Nagarik Sahayak | Digital India Initiative"
    ), align="C")

    pdf.output(output_path)
    return output_path



def _add_watermark(pdf: FPDF):
    """Add a diagonal 'DRAFT - FOR REFERENCE ONLY' watermark to the current page."""
    pdf.set_font("NS", "B", 38)
    pdf.set_text_color(220, 220, 220)
    with pdf.rotation(45, x=105, y=148):
        pdf.set_xy(20, 140)
        pdf.cell(170, 20, "DRAFT - FOR REFERENCE ONLY", align="C")


def _add_page_header(pdf: FPDF, scheme_name: str, scheme_name_hindi: str, ref_id: str, date_str: str):
    """Draw the standard government-style header on a new page."""
    # Saffron bar
    pdf.set_fill_color(255, 153, 51)
    pdf.rect(0, 0, 210, 20, "F")
    # Green accent
    pdf.set_fill_color(19, 136, 8)
    pdf.rect(0, 20, 210, 2, "F")
    # Ashoka Chakra-style blue line
    pdf.set_draw_color(0, 0, 128)
    pdf.line(10, 22.5, 200, 22.5)

    pdf.set_y(3)
    pdf.set_font("NS", "B", 14)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 8, "Nagarik Sahayak", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("NS", size=7)
    pdf.cell(0, 4, "Digital India Initiative | Government Scheme Assistance", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_y(25)
    pdf.set_font("NS", "B", 12)
    pdf.set_text_color(0, 0, 128)
    pdf.cell(0, 7, "APPLICATION FORM", align="C", new_x="LMARGIN", new_y="NEXT")

    display_name = scheme_name
    if scheme_name_hindi:
        display_name = f"{scheme_name} / {scheme_name_hindi}"
    pdf.set_font("NS", "B", 9)
    pdf.set_text_color(0, 0, 128)
    pdf.cell(0, 5, display_name, align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("NS", size=7)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 5, f"Ref: NS-{ref_id}  |  Date: {date_str}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)


def _add_page_footer(pdf: FPDF, page_num: int, total_pages_placeholder: str = ""):
    """Add footer with page numbers and disclaimer to current page."""
    pdf.set_y(-18)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(1)
    pdf.set_font("NS", size=6)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(95, 3, "Nagarik Sahayak | Digital India Initiative")
    pdf.cell(0, 3, f"Page {page_num}", align="R", new_x="LMARGIN", new_y="NEXT")


def _ensure_space(pdf: FPDF, needed_height: float, scheme_name: str, scheme_name_hindi: str, ref_id: str, date_str: str, page_counter: list):
    """Check if enough space remains on the page; if not, add a new page with header."""
    if pdf.get_y() + needed_height > pdf.h - 22:
        _add_page_footer(pdf, page_counter[0])
        pdf.add_page()
        page_counter[0] += 1
        _add_page_header(pdf, scheme_name, scheme_name_hindi, ref_id, date_str)
        _add_watermark(pdf)


def generate_real_filled_form_pdf(
    filled_fields: dict,
    scheme_name: str,
    scheme_name_hindi: str = "",
    sections: list = None,
    form_fields: list = None,
    output_path: str = "/tmp/filled_form.pdf",
) -> str:
    """Generate a production-grade pre-filled application form PDF with all real fields.

    Handles multi-page forms, field value formatting (date, phone, aadhaar masking),
    page numbers, draft watermark, and long textarea values.
    """
    pdf = FPDF()
    pdf.set_auto_page_break(auto=False)  # Manual page break control
    pdf.set_margin(10)

    pdf.add_font("NS", "", str(FONTS_DIR / "NotoSans-Regular.ttf"))
    pdf.add_font("NS", "B", str(FONTS_DIR / "NotoSans-Bold.ttf"))
    pdf.add_font("NH", "", str(FONTS_DIR / "NotoSansDevanagari-Regular.ttf"))

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%d/%m/%Y")
    ref_id = now.strftime("%Y%m%d%H%M%S")
    page_counter = [1]  # mutable so helpers can increment

    # First page
    pdf.add_page()
    _add_page_header(pdf, scheme_name, scheme_name_hindi, ref_id, date_str)
    _add_watermark(pdf)

    # --- Form number box (government form style) ---
    pdf.set_fill_color(245, 245, 252)
    pdf.set_draw_color(0, 0, 128)
    pdf.set_font("NS", "B", 8)
    pdf.set_text_color(0, 0, 128)
    y_box = pdf.get_y()
    pdf.rect(10, y_box, 190, 10, "D")
    pdf.set_xy(12, y_box + 2)
    pdf.cell(90, 6, f"Form No.: NS-{ref_id}")
    pdf.cell(0, 6, f"Category: Government Scheme Application", align="R")
    pdf.set_y(y_box + 12)

    if not form_fields:
        form_fields = []
    if not sections:
        sections = [{"name": "Application Details", "nameHindi": ""}]

    # Build section-to-fields map
    section_fields = {}
    for f in form_fields:
        sec = f.get("section", "Other")
        section_fields.setdefault(sec, []).append(f)

    field_counter = 0

    for sec_idx, sec in enumerate(sections):
        sec_name = sec.get("name", "")
        sec_hindi = sec.get("nameHindi", "")
        fields_in_sec = section_fields.get(sec_name, [])
        if not fields_in_sec:
            continue

        # Ensure space for section header + at least one field
        _ensure_space(pdf, 22, scheme_name, scheme_name_hindi, ref_id, date_str, page_counter)

        # Section header with numbering (government form style)
        header_text = f"  Section {sec_idx + 1}: {sec_name}"
        if sec_hindi:
            header_text += f" / {sec_hindi}"

        pdf.set_fill_color(230, 235, 248)
        pdf.set_draw_color(0, 0, 128)
        pdf.set_font("NS", "B", 9)
        pdf.set_text_color(0, 0, 128)
        pdf.cell(0, 7, header_text, fill=True, new_x="LMARGIN", new_y="NEXT", border="B")
        pdf.ln(2)

        for field in fields_in_sec:
            field_counter += 1
            pk = field.get("profileKey", field.get("fieldName", ""))
            raw_value = filled_fields.get(pk, "")
            field_type = field.get("type", "text")

            # Format value based on field type
            formatted_value = _format_field_value(raw_value, field_type)

            label_en = field.get("labelEnglish", "")
            label_hi = field.get("labelHindi", "")
            label = label_en
            if label_hi:
                label = f"{label_hi} / {label_en}"
            if field.get("required", False):
                label += " *"

            is_long_text = field_type == "textarea" or (len(formatted_value) > 60 and formatted_value != "_______________")

            if is_long_text:
                # Textarea / long text: label on top, multi_cell value below
                _ensure_space(pdf, 28, scheme_name, scheme_name_hindi, ref_id, date_str, page_counter)

                # Field number + label
                pdf.set_font("NS", "B", 8)
                pdf.set_text_color(80, 80, 80)
                pdf.cell(0, 6, f"{field_counter}. {label}", new_x="LMARGIN", new_y="NEXT")

                # Value in bordered box
                pdf.set_font("NS", size=9)
                pdf.set_text_color(30, 30, 30)
                pdf.set_fill_color(255, 255, 255)
                pdf.set_draw_color(180, 180, 200)
                x_start = pdf.get_x() + 4
                y_start = pdf.get_y()
                pdf.set_x(x_start)
                # Calculate height needed
                text_width = 190 - 8  # page width minus padding
                pdf.multi_cell(text_width, 5, f"  {formatted_value}", border=1, fill=True)
                pdf.ln(2)
            else:
                # Standard single-line field: label left, value right
                _ensure_space(pdf, 12, scheme_name, scheme_name_hindi, ref_id, date_str, page_counter)

                # Field number + label
                pdf.set_font("NS", "B", 8)
                pdf.set_text_color(80, 80, 80)
                label_display = f"{field_counter}. {label}"
                pdf.cell(82, 7, label_display[:65])

                # Value in bordered box
                pdf.set_font("NS", size=9)
                pdf.set_text_color(30, 30, 30)
                pdf.set_fill_color(255, 255, 255)
                pdf.set_draw_color(180, 180, 200)
                pdf.cell(0, 7, f"  {formatted_value}", border=1, fill=True, new_x="LMARGIN", new_y="NEXT")
                pdf.ln(1)

        pdf.ln(2)

    # === DECLARATION SECTION ===
    _ensure_space(pdf, 55, scheme_name, scheme_name_hindi, ref_id, date_str, page_counter)

    pdf.set_fill_color(230, 235, 248)
    pdf.set_draw_color(0, 0, 128)
    pdf.set_font("NS", "B", 9)
    pdf.set_text_color(0, 0, 128)
    pdf.cell(0, 7, "  Declaration / Ghoshana", fill=True, new_x="LMARGIN", new_y="NEXT", border="B")
    pdf.ln(3)

    pdf.set_font("NS", size=8)
    pdf.set_text_color(60, 60, 60)
    pdf.multi_cell(0, 4, (
        "I hereby declare that the information provided above is true and correct "
        "to the best of my knowledge and belief. I understand that any false statement "
        "may lead to rejection of my application and/or legal action.\n\n"
        "Main yeh ghoshana karta/karti hoon ki upar di gayi sabhi jaankari meri jaankari "
        "ke anusaar sahi aur satya hai."
    ))
    pdf.ln(6)

    # Signature and date lines
    pdf.set_font("NS", "B", 8)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(90, 5, "Signature / Hastakshar:")
    pdf.cell(0, 5, f"Date / Tithi: {date_str}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(100, 100, 100)
    pdf.line(10, pdf.get_y() + 12, 80, pdf.get_y() + 12)
    pdf.line(120, pdf.get_y() + 12, 200, pdf.get_y() + 12)
    pdf.set_y(pdf.get_y() + 16)

    # === OFFICE USE ONLY section (government form style) ===
    _ensure_space(pdf, 25, scheme_name, scheme_name_hindi, ref_id, date_str, page_counter)
    pdf.set_fill_color(245, 245, 245)
    pdf.set_draw_color(150, 150, 150)
    pdf.set_font("NS", "B", 8)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 6, "  FOR OFFICE USE ONLY", fill=True, new_x="LMARGIN", new_y="NEXT", border="TB")
    pdf.set_font("NS", size=7)
    pdf.set_text_color(180, 180, 180)
    pdf.cell(63, 5, "Verified by: _______________")
    pdf.cell(63, 5, "Date: _______________")
    pdf.cell(0, 5, "Seal: _______________", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    # Add footer to the last page
    _add_page_footer(pdf, page_counter[0])

    pdf.output(output_path)
    return output_path
