"""PDF Form Filler — Fills real government PDF forms with user data.

Two strategies:
1. AcroForm filler: writes values into fillable PDF fields using PyMuPDF
2. Text overlay filler: overlays text onto non-fillable PDFs at detected positions

Falls back to generating a new document if neither strategy works.
"""
import os
import re
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import fitz  # PyMuPDF
    _HAS_FITZ = True
except ImportError:
    _HAS_FITZ = False
    logger.info("PyMuPDF (fitz) not available — PDF form filling disabled")


def _format_value_for_fill(value, field_type: str = "text") -> str:
    """Format a value for writing into a PDF form field (no masking — full values needed)."""
    if value is None or value == "":
        return ""
    val = str(value)
    if field_type == "date":
        # Convert ISO to DD/MM/YYYY
        match = re.match(r'^(\d{4})-(\d{2})-(\d{2})', val)
        if match:
            return f"{match.group(3)}/{match.group(2)}/{match.group(1)}"
    elif field_type == "phone":
        digits = re.sub(r'\D', '', val)
        if len(digits) == 10:
            return digits
        if len(digits) == 12 and digits.startswith('91'):
            return digits[2:]
    elif field_type == "aadhaar":
        # Full Aadhaar — no masking for official forms
        return re.sub(r'\D', '', val)
    return val


# ─────────────────────────────────────────────────────────────
# 1. AcroForm Filler — fills interactive form fields in a PDF
# ─────────────────────────────────────────────────────────────

def fill_acroform_pdf(
    source_pdf_path: str,
    output_path: str,
    field_values: dict,
    form_fields: list = None,
) -> dict:
    """Fill AcroForm fields in a PDF with user data.

    Args:
        source_pdf_path: Path to the original government PDF with fillable fields
        output_path: Where to save the filled PDF
        field_values: User's profile data {profileKey: value}
        form_fields: List of field definitions from FormTemplate.extractedFields
                     Used to map profileKeys to PDF field names

    Returns:
        dict with keys: success, filled_count, total_fields, unfilled_fields, method
    """
    if not _HAS_FITZ:
        return {"success": False, "error": "PyMuPDF not available", "method": "acroform"}

    if not os.path.exists(source_pdf_path):
        return {"success": False, "error": f"Source PDF not found: {source_pdf_path}", "method": "acroform"}

    try:
        doc = fitz.open(source_pdf_path)
    except Exception as e:
        return {"success": False, "error": f"Cannot open PDF: {e}", "method": "acroform"}

    # Build mapping from PDF field names → user values
    # Strategy: try direct profileKey match, then fuzzy match via form_fields
    field_map = _build_acroform_field_map(doc, field_values, form_fields)

    if not field_map:
        doc.close()
        return {
            "success": False,
            "error": "No fillable AcroForm fields found in PDF",
            "total_fields": 0,
            "method": "acroform",
        }

    filled_count = 0
    unfilled = []
    total_widget_count = 0

    for page_num in range(len(doc)):
        page = doc[page_num]
        widgets = page.widgets()
        if not widgets:
            continue
        for widget in widgets:
            total_widget_count += 1
            fname = widget.field_name or ""
            if fname in field_map and field_map[fname]:
                try:
                    widget.field_value = str(field_map[fname])
                    widget.update()
                    filled_count += 1
                except Exception as e:
                    logger.warning(f"Failed to fill field '{fname}': {e}")
                    unfilled.append(fname)
            else:
                unfilled.append(fname)

    try:
        doc.save(output_path)
        doc.close()
    except Exception as e:
        doc.close()
        return {"success": False, "error": f"Failed to save filled PDF: {e}", "method": "acroform"}

    return {
        "success": filled_count > 0,
        "filled_count": filled_count,
        "total_fields": total_widget_count,
        "unfilled_fields": unfilled,
        "method": "acroform",
    }


def _build_acroform_field_map(doc, field_values: dict, form_fields: list = None) -> dict:
    """Build a mapping from PDF AcroForm field names → user values.

    Uses multiple strategies:
    1. Direct match: PDF field name matches a profileKey
    2. Form field mapping: Use extractedFields to map profileKey → PDF field name
    3. Fuzzy match: Normalize field names and try to match
    """
    pdf_field_names = set()
    for page in doc:
        widgets = page.widgets()
        if widgets:
            for w in widgets:
                if w.field_name:
                    pdf_field_names.add(w.field_name)

    if not pdf_field_names:
        return {}

    result = {}

    # Strategy 1: Direct profileKey match
    for pdf_name in pdf_field_names:
        normalized = _normalize_field_name(pdf_name)
        if normalized in field_values:
            result[pdf_name] = field_values[normalized]
        elif pdf_name in field_values:
            result[pdf_name] = field_values[pdf_name]

    # Strategy 2: Use form_fields mapping (fieldName → profileKey)
    if form_fields:
        # Build fieldName → profileKey lookup
        field_to_profile = {}
        profile_to_type = {}
        for f in form_fields:
            fn = f.get("fieldName", "")
            pk = f.get("profileKey", "")
            ft = f.get("type", "text")
            if fn and pk:
                field_to_profile[fn] = pk
                field_to_profile[_normalize_field_name(fn)] = pk
                profile_to_type[pk] = ft

        for pdf_name in pdf_field_names:
            if pdf_name in result:
                continue  # already matched
            normalized = _normalize_field_name(pdf_name)
            # Check if this PDF field name matches any known fieldName
            profile_key = field_to_profile.get(pdf_name) or field_to_profile.get(normalized)
            if profile_key and profile_key in field_values:
                field_type = profile_to_type.get(profile_key, "text")
                result[pdf_name] = _format_value_for_fill(field_values[profile_key], field_type)

    # Strategy 3: Fuzzy matching on normalized names
    normalized_values = {_normalize_field_name(k): v for k, v in field_values.items()}
    for pdf_name in pdf_field_names:
        if pdf_name in result:
            continue
        normalized = _normalize_field_name(pdf_name)
        # Try partial matches
        for norm_key, val in normalized_values.items():
            if norm_key and normalized and (norm_key in normalized or normalized in norm_key):
                result[pdf_name] = str(val)
                break

    return result


def _normalize_field_name(name: str) -> str:
    """Normalize a field name for fuzzy matching."""
    # Convert to lowercase, replace brackets/dots/special chars with underscores
    s = name.lower().strip()
    s = re.sub(r'[^a-z0-9]+', '_', s)  # Non-alphanum → underscore
    s = s.strip('_')
    return s


# ─────────────────────────────────────────────────────────────
# 2. Text Overlay Filler — places text on non-fillable PDFs
# ─────────────────────────────────────────────────────────────

def fill_overlay_pdf(
    source_pdf_path: str,
    output_path: str,
    field_values: dict,
    form_fields: list = None,
    field_positions: list = None,
) -> dict:
    """Overlay text onto a non-fillable PDF at specified or auto-detected positions.

    Args:
        source_pdf_path: Path to the original government PDF
        output_path: Where to save the filled PDF
        field_values: User's profile data {profileKey: value}
        form_fields: List of field definitions from FormTemplate.extractedFields
        field_positions: Optional list of dicts with {profileKey, page, x, y, font_size}
                        If not provided, attempts auto-detection of blank lines/underscores

    Returns:
        dict with keys: success, filled_count, total_positions, method
    """
    if not _HAS_FITZ:
        return {"success": False, "error": "PyMuPDF not available", "method": "overlay"}

    if not os.path.exists(source_pdf_path):
        return {"success": False, "error": f"Source PDF not found: {source_pdf_path}", "method": "overlay"}

    try:
        doc = fitz.open(source_pdf_path)
    except Exception as e:
        return {"success": False, "error": f"Cannot open PDF: {e}", "method": "overlay"}

    positions = field_positions
    if not positions:
        # Auto-detect fillable positions (underscores, blank lines, dotted lines)
        positions = _detect_fill_positions(doc, form_fields, field_values)

    if not positions:
        doc.close()
        return {
            "success": False,
            "error": "No fill positions detected in PDF",
            "total_positions": 0,
            "method": "overlay",
        }

    filled_count = 0
    for pos in positions:
        profile_key = pos.get("profileKey", "")
        page_num = pos.get("page", 1) - 1  # Convert to 0-indexed
        x = pos.get("x", 50)
        y = pos.get("y", 50)
        font_size = pos.get("font_size", 10)

        if page_num < 0 or page_num >= len(doc):
            continue

        value = field_values.get(profile_key, "")
        if not value:
            continue

        # Get field type for formatting
        field_type = "text"
        if form_fields:
            for f in form_fields:
                if f.get("profileKey") == profile_key:
                    field_type = f.get("type", "text")
                    break

        formatted = _format_value_for_fill(value, field_type)
        if not formatted:
            continue

        page = doc[page_num]
        try:
            # Insert text at position
            text_point = fitz.Point(x, y)
            page.insert_text(
                text_point,
                formatted,
                fontsize=font_size,
                fontname="helv",  # Helvetica (built-in PDF font)
                color=(0, 0, 0.5),  # Dark blue to distinguish from printed text
            )
            filled_count += 1
        except Exception as e:
            logger.warning(f"Failed to overlay text for '{profile_key}' at ({x},{y}): {e}")

    try:
        doc.save(output_path)
        doc.close()
    except Exception as e:
        doc.close()
        return {"success": False, "error": f"Failed to save overlay PDF: {e}", "method": "overlay"}

    return {
        "success": filled_count > 0,
        "filled_count": filled_count,
        "total_positions": len(positions),
        "method": "overlay",
    }


def _detect_fill_positions(doc, form_fields: list = None, field_values: dict = None) -> list:
    """Auto-detect blank/fillable positions in a PDF by finding underscores and label text.

    Searches each page for patterns like:
    - "Name: ____________" or "Name: ............"
    - "नाम:" followed by blank space

    Returns list of {profileKey, page, x, y, font_size} dicts.
    """
    if not form_fields:
        return []

    positions = []
    # Build label → profileKey map from form_fields
    label_map = {}
    for f in form_fields:
        pk = f.get("profileKey", "")
        for label in [f.get("labelEnglish", ""), f.get("labelHindi", ""), f.get("fieldName", "")]:
            if label:
                label_map[label.lower().strip().rstrip(":")] = pk

    for page_num in range(len(doc)):
        page = doc[page_num]
        blocks = page.get_text("dict")["blocks"]

        for block in blocks:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                line_text = ""
                line_bbox = None
                for span in line["spans"]:
                    line_text += span["text"]
                    if not line_bbox:
                        line_bbox = span["bbox"]
                    else:
                        # Extend bbox
                        line_bbox = (
                            min(line_bbox[0], span["bbox"][0]),
                            min(line_bbox[1], span["bbox"][1]),
                            max(line_bbox[2], span["bbox"][2]),
                            max(line_bbox[3], span["bbox"][3]),
                        )

                if not line_text.strip() or not line_bbox:
                    continue

                # Check if this line contains a label followed by underscores/dots
                for label_text, profile_key in label_map.items():
                    if label_text in line_text.lower():
                        # Found a label — position the fill after the label
                        # Approximate: place text at 60% of page width, same y
                        fill_x = line_bbox[2] + 5  # Right after label text
                        fill_y = line_bbox[3] - 2   # Baseline aligned
                        font_size = min(max(line_bbox[3] - line_bbox[1] - 1, 8), 12)

                        positions.append({
                            "profileKey": profile_key,
                            "page": page_num + 1,
                            "x": fill_x,
                            "y": fill_y,
                            "font_size": font_size,
                        })
                        break

    return positions


# ─────────────────────────────────────────────────────────────
# 3. Unified fill entry point
# ─────────────────────────────────────────────────────────────

def fill_pdf_form(
    source_pdf_path: str,
    output_path: str,
    field_values: dict,
    form_fields: list = None,
    field_positions: list = None,
) -> dict:
    """Fill a PDF form using the best available strategy.

    Strategy order:
    1. AcroForm filling (if PDF has interactive form fields)
    2. Text overlay (if positions provided or auto-detected)
    3. Returns failure (caller should fall back to generating new PDF)

    Args:
        source_pdf_path: Path to the original government PDF
        output_path: Where to save the filled PDF
        field_values: User's profile data {profileKey: value}
        form_fields: Field definitions from FormTemplate.extractedFields
        field_positions: Optional manual positions for overlay mode

    Returns:
        dict with: success, method, filled_count, total_fields, etc.
    """
    if not _HAS_FITZ:
        return {"success": False, "error": "PyMuPDF not available", "method": "none"}

    if not os.path.exists(source_pdf_path):
        return {"success": False, "error": f"Source PDF not found", "method": "none"}

    # Strategy 1: Try AcroForm filling
    acro_result = fill_acroform_pdf(source_pdf_path, output_path, field_values, form_fields)
    if acro_result.get("success") and acro_result.get("filled_count", 0) > 0:
        logger.info(f"AcroForm fill successful: {acro_result['filled_count']}/{acro_result['total_fields']} fields")
        return acro_result

    # Strategy 2: Try text overlay
    overlay_result = fill_overlay_pdf(
        source_pdf_path, output_path, field_values, form_fields, field_positions
    )
    if overlay_result.get("success") and overlay_result.get("filled_count", 0) > 0:
        logger.info(f"Overlay fill successful: {overlay_result['filled_count']}/{overlay_result['total_positions']} positions")
        return overlay_result

    # Neither strategy worked
    return {
        "success": False,
        "error": "Could not fill PDF — no AcroForm fields and no overlay positions detected. "
                 "Falling back to generated form.",
        "method": "none",
        "acroform_result": acro_result,
        "overlay_result": overlay_result,
    }
