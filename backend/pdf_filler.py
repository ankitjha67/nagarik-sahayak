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
        # Masked, never full — and this is deliberate even though the printed
        # form asks for the whole number.
        #
        # Aadhaar Act s29(4) makes publishing an Aadhaar number an offence, and
        # an entity that is not a Requesting Entity must not store one. This
        # file is produced by the application, encrypted at rest, and
        # downloaded; writing twelve digits into it puts the number somewhere
        # the citizen no longer controls, which is exactly what the rest of
        # this codebase refuses to do (see dpdp/aadhaar_policy.py). The last
        # four digits identify the record; the citizen writes the remaining
        # eight by hand on the copy they hand over, which is theirs to write.
        from dpdp.aadhaar_policy import mask
        return mask(val)
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

def _unplaced_report(positions, field_values: dict, form_fields: list) -> list[dict]:
    """Values the citizen supplied that no slot on the printed form could take.

    A printed form rarely has a labelled box for every field the catalog knows.
    This one has no "PIN Code" line at all, records the medal in a grid rather
    than a "Position" field, and butts "(Enclose Certificate)" hard against the
    date of birth.

    Returning the shortfall is the whole point. Silence would hand a citizen a
    form that looks finished and is not, and they would find out at the counter.
    Told which lines to complete by hand, they can do it before they travel.
    """
    if not form_fields:
        return []
    placed = {p.get("profileKey") for p in positions}
    out = []
    for f in form_fields:
        pk = f.get("profileKey")
        if not pk or pk in placed:
            continue
        if (field_values or {}).get(pk) in (None, ""):
            continue
        out.append({
            "profileKey": pk,
            "label": f.get("labelEnglish", pk),
            "labelHindi": f.get("labelHindi", ""),
            "required": bool(f.get("required")),
            "reason": "No labelled space for this was found on the printed form.",
            "reasonHindi": "मुद्रित फॉर्म पर इसके लिए कोई चिह्नित स्थान नहीं मिला।",
        })
    return out


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
            # Shrink to fit the space beside the label rather than running over
            # the cell border into the next column. Below 6pt the text stops
            # being readable, so it is truncated with an ellipsis instead —
            # a visibly cut value tells the citizen to write it by hand, where
            # an illegible one does not.
            max_width = pos.get("max_width")
            if max_width:
                while (font_size > 6
                       and fitz.get_text_length(formatted, "helv", font_size) > max_width):
                    font_size -= 0.5
                if fitz.get_text_length(formatted, "helv", font_size) > max_width:
                    while (len(formatted) > 4
                           and fitz.get_text_length(formatted + "…", "helv",
                                                    font_size) > max_width):
                        formatted = formatted[:-1]
                    formatted += "…"

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
        "unplaced": _unplaced_report(positions, field_values, form_fields),
    }


# Label phrasings real government forms use, per profileKey. The catalog's own
# labels are written for the app's UI ("Full Name (as per Aadhaar)"); the
# printed form says "Name of the Applicant". Matching only on the catalog label
# left the single most important field on the page — the applicant's name —
# blank, which is how this table came to exist.
#
# Ordered most specific first: "father's name" must be tried before "name", or
# every name field on the form collects the applicant's own.
FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "father_husband_name": ("father's name", "fathers name", "father / husband",
                            "father's / husband's name", "husband's name",
                            "name of father", "पिता का नाम"),
    "mother_name": ("mother's name", "mothers name", "name of mother",
                    "माता का नाम"),
    "guardian_name": ("guardian's name", "name of guardian"),
    "name": ("name of the applicant", "name of applicant", "applicant's name",
             "full name", "name of the student", "student's name",
             "आवेदक का नाम", "पूरा नाम"),
    "date_of_birth": ("date of birth", "dob", "जन्म तिथि", "जन्म दिनांक"),
    "gender": ("sex", "gender", "लिंग"),
    "category": ("category", "caste category", "श्रेणी", "जाति"),
    "aadhaar_number": ("aadhar no", "aadhaar no", "aadhar number",
                       "aadhaar number", "uid no", "आधार संख्या"),
    "mobile_number": ("mobile no", "mobile number", "contact no", "phone no",
                      "मोबाइल"),
    "email": ("email id", "e-mail id", "email address", "ईमेल"),
    "address_line": ("address", "residential address", "पता"),
    "district": ("district", "जिला"),
    "state": ("state", "राज्य"),
    "pincode": ("pin code", "pincode", "postal code", "पिन कोड"),
    "village": ("village", "town", "vtc", "गाँव"),
    "tehsil": ("tehsil", "taluka", "तहसील"),
    "institution_name": ("name of the college/school", "name of college/school",
                         "name of the institution", "name of the college",
                         "name of college", "name of the school",
                         "name of institution", "college/school",
                         "institution", "विद्यालय", "संस्थान का नाम"),
    "sport_name": ("game/sport", "game / sport", "name of game", "sport",
                   "discipline", "खेल"),
    "event_name": ("name of tournament", "name of event", "tournament",
                   "competition", "प्रतियोगिता"),
    "achievement_position": ("position obtained", "medal won", "position",
                             "rank obtained"),
    "bank_name": ("bank's name", "banks name", "name of bank", "bank name",
                  "बैंक का नाम"),
    "bank_account_number": ("bank account number", "account no", "a/c no",
                            "account number", "खाता संख्या"),
    "ifsc_code": ("ifsc code", "ifsc", "आईएफएससी"),
    "branch_name": ("branch name", "name of branch", "शाखा"),
    "annual_income": ("annual income", "family income", "वार्षिक आय"),
    "ration_card_number": ("ration card no", "ration card number",
                           "राशन कार्ड"),
    "domicile_certificate_number": ("domicile certificate", "residence certificate",
                                    "अधिवास प्रमाण"),
    "roll_number": ("roll no", "roll number", "enrollment no", "registration no"),
    "course_name": ("course", "class", "stream"),
}

# A line is treated as a form label only if it looks like one. Without this a
# value lands in the middle of a printed declaration — "date of birth" appears
# inside "Self-attested copy of my sports achievements, date of birth, Bank
# Pass Book …", and a date written there is both wrong and alarming to whoever
# reads the form at the counter.
MAX_LABEL_CHARS = 60

# Below this many points there is no room to write anything a person could
# read. A field with less space is reported as unplaced, so the citizen is told
# to write it by hand — which is far better than a 6pt smear across a label.
MIN_USABLE_WIDTH = 34

# A value squeezed below this fraction of the width it needs comes out cut and
# unreadable. Reported unplaced instead, so the citizen writes it by hand.
MIN_LEGIBLE_FRACTION = 0.6
_SENTENCE_MARKERS = (
    " that ", " have ", " has been", " shall ", " will ", " are to ",
    " is to ", " i ", " my ", " been ", " enclose", " submitted",
)


def _looks_like_a_label(text: str) -> bool:
    """True if this line is plausibly a field label rather than prose.

    Length and sentence structure decide it, not punctuation. An earlier
    version rejected anything ending in a full stop, which threw away
    "IFSC Code: --ll." — a perfectly good label followed by scan noise.
    """
    stripped = text.strip()
    if not stripped or len(stripped) > MAX_LABEL_CHARS:
        return False
    lowered = f" {stripped.lower()} "
    if any(marker in lowered for marker in _SENTENCE_MARKERS):
        return False
    # Prose runs to several clauses; a label does not.
    return stripped.count(",") < 3 and stripped.count(".") < 3


def _alias_hit(line_lower: str, profile_key: str, catalog_labels: tuple) -> str | None:
    """The alias or catalog label this line matches, longest first.

    Longest-first matters: "father's name" and "name" both appear in
    "Father's Name:", and picking the shorter one writes the applicant's own
    name onto their father's line.
    """
    candidates = list(FIELD_ALIASES.get(profile_key, ())) + list(catalog_labels)
    for candidate in sorted({c for c in candidates if c}, key=len, reverse=True):
        if candidate in line_lower:
            return candidate
    return None


def _search_variants(alias: str) -> list[str]:
    """The spellings of one label a real document might carry.

    Scanned forms come through an OCR layer that uses typographic apostrophes
    and irregular spacing, so a literal search for "mother's name" finds
    nothing on a page that plainly says Mother’s Name. Each variant is tried
    until one hits.
    """
    variants = [alias]
    if "'" in alias:
        variants.append(alias.replace("'", "\u2019"))
        variants.append(alias.replace("'", ""))
    if "/" in alias:
        variants.append(alias.replace("/", " / "))
        variants.append(alias.replace("/", ""))
    # Deliberately no single-word fallback. Searching for just "mother" matches
    # the first word of "Mother's Name:" and anchors the value mid-label, so
    # the form came back reading "Mother's Kamla Sharma"; "domicile" did the
    # same to a printed hint. A field left unplaced is reported to the citizen
    # and can be written by hand. A defaced form cannot be undone.
    seen, out = set(), []
    for v in variants:
        v = v.strip()
        if v and v.lower() not in seen:
            seen.add(v.lower())
            out.append(v)
    return out


def _label_rects(page, alias: str):
    """Where this label appears on the page, as rectangles.

    `search_for` is used rather than walking spans because PDF text is split
    into spans arbitrarily — "Name of the Applicant" can arrive as four spans
    or one — and anchoring to a span boundary wrote values on top of the label
    they belonged beside.
    """
    for variant in _search_variants(alias):
        try:
            rects = page.search_for(variant, quads=False)
        except Exception:  # noqa: BLE001 — a malformed page must not stop the fill
            continue
        if rects:
            return rects
    return []


def _right_bound(words, rect, page_width: float) -> float:
    """How far right a value may extend before it collides with something.

    Bounded by the next printed word on the same visual row, which is what
    stops a college name from running across the Class, Session and Admission
    No. columns of a table.
    """
    band_top, band_bottom = rect.y0 - 2, rect.y1 + 2
    edge = page_width - 18
    for x0, y0, x1, y1, *_ in words:
        centre = (y0 + y1) / 2
        if band_top <= centre <= band_bottom and x0 > rect.x1 + 2:
            edge = min(edge, x0 - 3)
    return edge


def _detect_fill_positions(doc, form_fields: list = None, field_values: dict = None) -> list:
    """Find where on a printed form each value should be written.

    Government forms are almost never fillable AcroForms — they are scans or
    flat prints — so the only way to put a value in the right box is to find
    the printed label and write beside it.

    Four things this has to get right, each of which it once got wrong:

    * **Match the form's words, not the app's.** The catalog says "Full Name
      (as per Aadhaar)"; the printed form says "Name of the Applicant". With
      only the catalog label to go on, the most important field on the page
      came out blank. FIELD_ALIASES carries the phrasings forms actually use.
    * **Refuse prose.** "date of birth" also appears inside "Self-attested copy
      of my sports achievements, date of birth, Bank Pass Book …", and a date
      written there lands in the middle of a legal undertaking.
    * **Anchor to the label, not to the line.** PDF spans break arbitrarily, so
      writing after a span boundary printed the value on top of its own label.
    * **Stop at the next column.** Without a right bound a long value runs
      across the neighbouring cells of a table.
    """
    if not form_fields:
        return []

    catalog_labels: dict[str, tuple] = {}
    for f in form_fields:
        pk = f.get("profileKey", "")
        if not pk:
            continue
        labels = tuple(
            str(lbl).strip().rstrip(":")
            for lbl in (f.get("labelEnglish"), f.get("labelHindi"), f.get("fieldName"))
            if lbl
        )
        catalog_labels[pk] = catalog_labels.get(pk, ()) + labels

    wanted = [pk for pk in catalog_labels
              if not field_values or field_values.get(pk) not in (None, "")]

    best: dict[str, dict] = {}

    for page_num in range(len(doc)):
        page = doc[page_num]
        page_width = page.rect.width
        words = page.get_text("words")
        # Full lines, used only to decide whether a hit sits inside prose.
        lines = [" ".join(w[4] for w in words)]  # fallback
        try:
            lines = [ln for ln in page.get_text().splitlines() if ln.strip()]
        except Exception:  # noqa: BLE001
            pass

        for pk in wanted:
            candidates = sorted(
                {c for c in (list(FIELD_ALIASES.get(pk, ())) + list(catalog_labels[pk])) if c},
                key=len, reverse=True,
            )
            for alias in candidates:
                rects = _label_rects(page, alias)
                if not rects:
                    continue

                # The label was located. Whether or not a value fits beside it,
                # do not fall through to a shorter alias: "name of the college"
                # is a substring of "Name of the College/School", and its rect
                # ends mid-label, so the value would be written across the
                # printed words. Found-but-no-room is reported as unplaced.
                placed = False
                found_here = True
                for rect in rects:
                    # The line this hit sits on, so prose can be rejected.
                    context = next(
                        (ln for ln in lines if alias.lower() in ln.lower()), alias)
                    if not _looks_like_a_label(context):
                        continue

                    x = rect.x1 + 5
                    y = rect.y1 - 1.5
                    height = rect.y1 - rect.y0
                    font_size = min(max(height - 2, 6.5), 10.5)
                    available = max(_right_bound(words, rect, page_width) - x, 0)

                    # Enough room for most of the value, not merely enough to
                    # start it. A college name shrunk to 6pt and cut to
                    # "…nt College for Women, Bahadur…" is not information a
                    # clerk can use; the citizen is better served being told to
                    # write it in the space provided.
                    value = (field_values or {}).get(pk)
                    if value:
                        try:
                            needed = fitz.get_text_length(
                                _format_value_for_fill(
                                    value, next((f.get("type", "text")
                                                 for f in form_fields
                                                 if f.get("profileKey") == pk),
                                                "text")),
                                "helv", font_size)
                        except Exception:  # noqa: BLE001
                            needed = 0
                        if needed and available < needed * MIN_LEGIBLE_FRACTION:
                            continue

                    if available < MIN_USABLE_WIDTH:
                        # No usable room beside this occurrence — a heading, or
                        # a label butted hard against the next column. Try the
                        # next occurrence; if none has room the field is
                        # reported unplaced rather than crammed in illegibly.
                        continue

                    candidate = {
                        "profileKey": pk,
                        "page": page_num + 1,
                        "x": x, "y": y,
                        "font_size": font_size,
                        "max_width": available,
                        # Prefer a longer alias (more specific) and more room.
                        "_score": (len(alias), available),
                    }
                    if pk not in best or candidate["_score"] > best[pk]["_score"]:
                        best[pk] = candidate
                    placed = True
                if placed or found_here:
                    break

    positions = []
    for pos in best.values():
        pos.pop("_score", None)
        positions.append(pos)
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
        acro_result.setdefault("unplaced", [])
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
