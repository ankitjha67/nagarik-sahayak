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

import form_geometry

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
    # What was actually written, for the post-fill check. Recorded here rather
    # than recomputed later because the font size and text can both change
    # during writing (shrink to fit, truncation), and the check must see the
    # final state, not the plan.
    written: list[dict] = []
    # Space already used on each page, so a second value is never planned on
    # top of a first. Placement is computed from the unfilled page, so without
    # this two fields whose labels sit close together can be given overlapping
    # room.
    claimed: dict[int, list] = {}
    for pos in sorted(positions, key=lambda p: (p.get("page", 1), p.get("y", 0),
                                                p.get("x", 0))):
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

            width = fitz.get_text_length(formatted, "helv", font_size)
            candidate = {"x": x, "y": y, "width": width, "font_size": font_size}

            # Never write over a value already placed on this page.
            if any(_collides(candidate, other)
                   for other in claimed.get(page_num, [])):
                logger.info("Skipped '%s': would overlap a value already placed",
                            profile_key)
                continue

            text_point = fitz.Point(x, y)
            page.insert_text(
                text_point,
                formatted,
                fontsize=font_size,
                fontname="helv",  # Helvetica (built-in PDF font)
                color=(0, 0, 0.5),  # Dark blue to distinguish from printed text
            )
            claimed.setdefault(page_num, []).append(candidate)
            written.append({
                "profileKey": profile_key,
                "page": page_num + 1,
                "x": x, "y": y,
                "width": width,
                "font_size": font_size,
                "text": formatted,
            })
            filled_count += 1
        except Exception as e:
            logger.warning(f"Failed to overlay text for '{profile_key}' at ({x},{y}): {e}")

    try:
        doc.save(output_path)
        doc.close()
    except Exception as e:
        doc.close()
        return {"success": False, "error": f"Failed to save overlay PDF: {e}", "method": "overlay"}

    placed_keys = [w["profileKey"] for w in written]
    result = {
        "success": filled_count > 0,
        "filled_count": filled_count,
        "total_positions": len(positions),
        "method": "overlay",
        "written": written,
        "unplaced": _unplaced_report(
            [{"profileKey": k} for k in placed_keys], field_values, form_fields),
    }
    # Check the file that now exists, not the plan that produced it.
    result["verification"] = verify_filled_pdf(output_path, written)
    return result


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
    # "medal won" is deliberately absent. It is the *header* of a Gold /
    # Silver / Bronze grid on the Haryana form, not a field, and matching it
    # wrote the word "First" across the column headings. A grid like that has
    # no slot for a word, so the field is reported unplaced and hand-written.
    "achievement_position": ("position obtained", "position secured",
                             "rank obtained", "प्राप्त स्थान"),
    "bank_name": ("bank's name", "banks name", "name of bank", "bank name",
                  "बैंक का नाम"),
    "bank_account_number": ("bank account number", "account no", "a/c no",
                            "account number", "खाता संख्या"),
    "ifsc_code": ("ifsc code", "ifsc", "आईएफएससी"),
    "branch_name": ("branch name", "name of branch", "शाखा"),
    "father_occupation": ("father's occupation", "fathers occupation",
                          "occupation of father", "पिता का व्यवसाय"),
    "mother_occupation": ("mother's occupation", "mothers occupation",
                          "occupation of mother", "माता का व्यवसाय"),
    "state_family_id": ("parivar pahchan patra no", "parivar pehchan patra",
                        "family id", "samagra id", "jan aadhaar",
                        "ration card no", "परिवार पहचान पत्र"),
    "current_class": ("class", "standard", "कक्षा"),
    "academic_session": ("session", "academic session", "सत्र"),
    "admission_number": ("admission no", "admission number", "प्रवेश संख्या"),
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
    # Sentence markers only mean prose in a line long enough to be prose. OCR
    # leaves stray letters — this form yields "I Mother's Occupation:" — and
    # matching " i " in a 23-character label threw the field away.
    if len(stripped) > 25 and any(m in lowered for m in _SENTENCE_MARKERS):
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


# How close an OCR-mangled label must be to count as a match.
#
# The floor is high, and it is high because of a specific near-miss:
# "fathersname" and "mothersname" differ by two characters in eleven and score
# 0.82, so a looser floor put the mother's name on the father's row. Anything
# that changes who a value refers to is worse than not matching at all.
OCR_TOKEN_SIMILARITY = 0.86


def _normalise_token(token: str) -> str:
    """Strip everything an OCR layer might have invented."""
    return re.sub(r"[^0-9a-z\u0900-\u097f]", "", str(token).lower())


def _token_ratio(a: str, b: str) -> float:
    """Normalised edit similarity between two words, 1.0 identical."""
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
    if abs(len(a) - len(b)) > max(2, min(len(a), len(b)) // 3):
        return 0.0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
        prev = cur
    return 1.0 - prev[len(b)] / max(len(a), len(b))


def _fuzzy_label_rects(page, alias: str):
    """Find a label the OCR layer has mangled.

    Exact search fails on real scans in ways that are invisible until you print
    the text. This form carries "Mother's·Name:" — a middle dot where the space
    should be, which makes it a *single* token, so no word-by-word window can
    match it — and "Name ofTournament" with the space missing. Both are
    perfectly legible on the page and neither is findable with `search_for`.

    So each printed line is reduced to one string of alphanumerics with a map
    back to the words it came from, and the alias is reduced the same way and
    sought inside it. Tokenisation stops mattering: whether the form prints
    "Mother's Name", "Mother's·Name" or "MothersName", all three become
    "mothersname". A bounded edit distance on top absorbs single-character
    misreads such as "lnstitutioi" for "Institution".
    """
    target = "".join(_normalise_token(t) for t in alias.split())
    if len(target) < 4:
        # Too short to match safely by concatenation: "class" would hit inside
        # "classification". Exact search already had its chance.
        return []

    try:
        words = page.get_text("words")
    except Exception:  # noqa: BLE001
        return []

    lines: dict[tuple, list] = {}
    for w in words:
        lines.setdefault((w[5], w[6]), []).append(w)

    hits = []
    for line_words in lines.values():
        line_words.sort(key=lambda w: w[7])
        joined = ""
        owner: list[int] = []   # which word each character came from
        for idx, w in enumerate(line_words):
            token = _normalise_token(w[4])
            joined += token
            owner.extend([idx] * len(token))
        if len(joined) < len(target):
            continue

        start = joined.find(target)
        if start == -1:
            # Nothing exact — slide the window and allow OCR-level error.
            best, best_start = 0.0, -1
            for i in range(len(joined) - len(target) + 1):
                score = _token_ratio(joined[i:i + len(target)], target)
                if score > best:
                    best, best_start = score, i
            # The first character must survive as well. Father/mother,
            # his/her and son/daughter all differ at the front and are
            # otherwise close enough to trade places, and a label that names
            # the wrong person is worse than one that matches nothing.
            if (best < OCR_TOKEN_SIMILARITY
                    or joined[best_start:best_start + 1] != target[:1]):
                continue
            start = best_start

        end = start + len(target) - 1
        matched = sorted({owner[start], owner[end]})
        covered = line_words[matched[0]:matched[-1] + 1]
        if not covered:
            continue
        hits.append(fitz.Rect(
            min(w[0] for w in covered), min(w[1] for w in covered),
            max(w[2] for w in covered), max(w[3] for w in covered)))
    return hits


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
    # Nothing matched literally. On a scan that usually means the OCR layer
    # mangled the label rather than that the label is absent.
    return _fuzzy_label_rects(page, alias)


def _right_bound(words, rect, page_width: float) -> float:
    """Fallback bound when no printed grid could be read.

    Used only for unruled documents. Where the form has ruled cells,
    form_geometry.writable_span is authoritative because it knows the border a
    clerk actually sees.
    """
    band_top, band_bottom = rect.y0 - 2, rect.y1 + 2
    edge = page_width - 18
    for x0, y0, x1, y1, *_ in words:
        centre = (y0 + y1) / 2
        if band_top <= centre <= band_bottom and x0 > rect.x1 + 2:
            edge = min(edge, x0 - 3)
    return edge


def _collides(a: dict, b: dict) -> bool:
    """Do two written values occupy the same place on the page?

    Compared by baseline distance rather than by rectangle overlap. A glyph box
    a full font-height tall is taller than the gap between two table rows —
    rows on this form sit 13 points apart with 9.7-point text — so rectangle
    intersection reported every vertical neighbour as a collision and refused
    to write Mother's Name because Father's Name was on the row above.

    Two values clash when their horizontal extents overlap *and* their
    baselines are close enough to be on the same visual line.
    """
    if a["x"] >= b["x"] + b["width"] or b["x"] >= a["x"] + a["width"]:
        return False
    same_line = min(a["font_size"], b["font_size"]) * 0.6
    return abs(a["y"] - b["y"]) < same_line


def _needed_width(profile_key: str, field_values: dict, form_fields: list,
                  font_size: float) -> float:
    """Width in points the formatted value would occupy, or 0 if unknown."""
    value = (field_values or {}).get(profile_key)
    if not value:
        return 0.0
    field_type = next((f.get("type", "text") for f in (form_fields or [])
                       if f.get("profileKey") == profile_key), "text")
    try:
        return fitz.get_text_length(
            _format_value_for_fill(value, field_type), "helv", font_size)
    except Exception:  # noqa: BLE001 — an unmeasurable value is placed anyway
        return 0.0


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
        # The ruled grid, read off the scan. Empty for an unruled document, in
        # which case bounds fall back to the next printed word.
        cells = form_geometry.build_cells(page)
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

                    y = rect.y1 - 1.5
                    height = rect.y1 - rect.y0
                    font_size = min(max(height - 2, 6.5), 10.5)

                    needed = _needed_width(pk, field_values, form_fields, font_size)

                    if cells:
                        # First gap the value actually fits, so a short value
                        # sits beside its label and only a long one is pushed
                        # to a wider space further along the row.
                        gaps = form_geometry.writable_gaps(
                            cells, rect, words, page_width)
                        chosen = next(
                            (g for g in gaps if g[1] - g[0] >= needed), None)
                        if chosen is None and gaps:
                            chosen = max(gaps, key=lambda g: g[1] - g[0])
                        if chosen is None:
                            continue
                        x, x_end = chosen
                        available = max(x_end - x, 0)
                    else:
                        x = rect.x1 + 5
                        available = max(
                            _right_bound(words, rect, page_width) - x, 0)

                    # Enough room for most of the value, not merely enough to
                    # start it. A college name shrunk to 6pt and cut to
                    # "…nt College for Women, Bahadur…" is not information a
                    # clerk can use; the citizen is better served being told to
                    # write it in the space provided.
                    if needed and available < needed * MIN_LEGIBLE_FRACTION:
                        continue

                    # The floor applies only when the value's width is
                    # unknown. "B.A. II" fits in 27 points; refusing it because
                    # 27 is under a generic 34-point minimum leaves a field
                    # blank that would have been perfectly legible.
                    if not needed and available < MIN_USABLE_WIDTH:
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

# ─────────────────────────────────────────────────────────────
# Pre-flight: what does the form ask for, and can we answer it?
# ─────────────────────────────────────────────────────────────

def _addressable_fields(doc, form_fields: list) -> set[str]:
    """Catalog fields whose label appears somewhere on this form."""
    found: set[str] = set()
    for f in form_fields or []:
        pk = f.get("profileKey", "")
        if not pk or pk in found:
            continue
        aliases = list(FIELD_ALIASES.get(pk, ())) + [
            str(lbl).strip().rstrip(":")
            for lbl in (f.get("labelEnglish"), f.get("labelHindi"))
            if lbl
        ]
        for page in doc:
            if any(_label_rects(page, a) for a in aliases if a):
                found.add(pk)
                break
    return found


def audit_form(source_pdf_path: str, form_fields: list,
               field_values: dict | None = None) -> dict:
    """Check a form against the catalog *before* writing anything to it.

    Answers three questions a filler cannot answer once it has started:

    * **Which catalog fields can actually be placed?** A field with no
      matching label, or none with room, will silently come out blank.
    * **What does the form ask for that the catalog does not model?** This is
      the gap that produced blank Father's Occupation, Mother's Occupation and
      Parivar Pehchan Patra lines on every application, with nothing reporting
      it — the catalog had no such fields, so nothing was ever missing.
    * **What did the citizen not supply?** Separated from the above, because a
      blank the citizen can fix is a different problem from one they cannot.
    """
    if not _HAS_FITZ or not os.path.exists(source_pdf_path):
        return {"available": False,
                "error": "PDF unavailable or PyMuPDF not installed"}

    try:
        doc = fitz.open(source_pdf_path)
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "error": f"Cannot open PDF: {exc}"}

    try:
        positions = _detect_fill_positions(doc, form_fields, field_values)
        placeable = {p["profileKey"] for p in positions}

        # Which labels the form carries at all, independent of whether this
        # citizen's particular value fits beside one. Computed from label
        # matching alone, because whether a value fits depends on the value —
        # and reporting a field as "not on this form" when it plainly is, only
        # because one long value would not fit, is a different and misleading
        # claim.
        addressable = _addressable_fields(doc, form_fields)

        printed_labels = _unmapped_labels(doc, form_fields)
        grid = [form_geometry.describe(doc[i]) for i in range(len(doc))]
    finally:
        doc.close()

    supplied = {f.get("profileKey") for f in form_fields
                if (field_values or {}).get(f.get("profileKey")) not in (None, "")}
    required = {f.get("profileKey") for f in form_fields if f.get("required")}

    return {
        "available": True,
        "totalFields": len(form_fields),
        "addressableOnForm": sorted(addressable),
        "notAddressableOnForm": sorted(
            {f.get("profileKey") for f in form_fields} - addressable),
        "suppliedAndPlaceable": sorted(supplied & placeable),
        "suppliedButUnplaceable": sorted(supplied - placeable),
        "requiredAndMissing": sorted(required - supplied),
        "labelsWithNoCatalogField": printed_labels,
        "grid": grid,
        "gridDetected": any(g.get("gridDetected") for g in grid),
    }


# Words that head a printed label but carry no field of their own.
_LABEL_STOPWORDS = {
    "the", "of", "and", "or", "for", "in", "to", "a", "an", "name", "no",
    "date", "details", "please", "enclose", "attach", "copy", "signature",
    "declaration", "certified", "application", "form", "yes", "no.", "seal",
}


def _unmapped_labels(doc, form_fields: list) -> list[str]:
    """Printed labels on the form that no catalog field claims.

    Heuristic and deliberately conservative: a short line ending in a colon is
    a label, and if no alias for any catalog field appears in it, the catalog
    has nothing to put there. It over-reports on decorative colons and
    under-reports on labels printed without one — which is the right way round,
    because the output is a prompt for a human to look, not an automated edit.
    """
    # Compared after the same normalisation the matcher uses, or a label the
    # fuzzy path *does* map — "Mother's·Name", with a middle dot — gets
    # reported as unmapped and sends someone looking for a bug that is not
    # there.
    known: list[str] = []
    for f in form_fields or []:
        pk = f.get("profileKey", "")
        known.extend(FIELD_ALIASES.get(pk, ()))
        for lbl in (f.get("labelEnglish"), f.get("labelHindi")):
            if lbl:
                known.append(str(lbl).lower())
    known_norm = [
        "".join(_normalise_token(t) for t in alias.split())
        for alias in known if alias
    ]

    unmapped: list[str] = []
    seen: set[str] = set()
    for page in doc:
        for raw in page.get_text().splitlines():
            line = raw.strip()
            if not line or ":" not in line or not _looks_like_a_label(line):
                continue
            head = line.split(":")[0].strip()
            if len(head) < 3 or len(head) > 44:
                continue
            lowered = head.lower()
            if lowered in seen:
                continue
            head_norm = "".join(_normalise_token(t) for t in head.split())
            if not head_norm or len(head_norm) < 4:
                continue
            if any(k and (k in head_norm or head_norm in k) for k in known_norm):
                continue
            # A single mangled word is OCR noise, not a label the catalog has
            # missed. Two or more words is a real heading worth reporting.
            if len(head.split()) < 2:
                continue
            words = [w for w in re.findall(r"[A-Za-z]+", lowered)
                     if w not in _LABEL_STOPWORDS]
            if not words:
                continue
            seen.add(lowered)
            unmapped.append(head)
    return unmapped


# ─────────────────────────────────────────────────────────────
# Post-flight: did anything land where it should not?
# ─────────────────────────────────────────────────────────────

def verify_filled_pdf(output_path: str, written: list[dict]) -> dict:
    """Re-open the written PDF and check nothing spilled over.

    Placement is computed from the *unfilled* page, so two values can be
    planned into overlapping space, a long value can run past the box it was
    measured for, and a font substitution can widen text after the fact. None
    of that is visible until the file exists. So it is opened again and checked
    against what it actually contains:

    * every value that was written is present in the text layer;
    * no written value overlaps another written value;
    * no written value crosses the cell border it was placed inside.

    A failure here is reported, not silently repaired. A form with two values
    on top of each other is one a clerk will reject, and the citizen needs to
    know that before they travel, not after.
    """
    if not _HAS_FITZ or not os.path.exists(output_path):
        return {"verified": False, "error": "Output PDF unavailable"}

    try:
        doc = fitz.open(output_path)
    except Exception as exc:  # noqa: BLE001
        return {"verified": False, "error": f"Cannot reopen PDF: {exc}"}

    problems: list[dict] = []
    missing: list[str] = []
    try:
        by_page: dict[int, list[dict]] = {}
        for item in written:
            by_page.setdefault(item["page"] - 1, []).append(item)

        for page_index, items in by_page.items():
            if page_index < 0 or page_index >= len(doc):
                continue
            page = doc[page_index]
            text = page.get_text()
            cells = form_geometry.build_cells(page)

            for item in items:
                if item["text"] not in text:
                    missing.append(item["profileKey"])

                right = item["x"] + item["width"]
                cell = form_geometry.cell_containing(
                    cells, item["x"] + 1, item["y"] - item["font_size"] / 2)
                if cell is not None and right > cell.x1 + 1:
                    problems.append({
                        "kind": "crossed_cell_border",
                        "profileKey": item["profileKey"],
                        "page": page_index + 1,
                        "detail": (f"value extends {right - cell.x1:.0f}pt past "
                                   f"the printed cell border"),
                    })

            for i, a in enumerate(items):
                for b in items[i + 1:]:
                    if _collides(a, b):
                        problems.append({
                            "kind": "values_overlap",
                            "profileKey": a["profileKey"],
                            "collidesWith": b["profileKey"],
                            "page": page_index + 1,
                            "detail": "two written values occupy the same space",
                        })
    finally:
        doc.close()

    for pk in missing:
        problems.append({
            "kind": "value_not_in_output",
            "profileKey": pk,
            "detail": "the value was written but is absent from the text layer",
        })

    return {
        "verified": True,
        "checked": len(written),
        "problems": problems,
        "clean": not problems,
    }


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
