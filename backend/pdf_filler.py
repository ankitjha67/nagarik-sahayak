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


# ── Fonts ───────────────────────────────────────────────────────────────
#
# Everything written onto a form used the base-14 "helv", which is encoded in
# Latin-1 and has no glyph beyond it. PyMuPDF does not refuse such a string —
# it writes a middle dot for every character it cannot draw. So a citizen who
# gave their name as प्रिया शर्मा, in an app that offers full language support,
# got "······ ·····" on the official form, and nothing anywhere reported a
# problem: the page had text on it, in the right box, the right width.
#
# The Noto faces are already bundled for the generated PDF. The chain below is
# tried in order and the first face that can draw *every* character of the
# value is used. "helv" stays first so an ASCII value is written exactly as
# before, embedding nothing.
FONTS_DIR = Path(__file__).parent / "fonts"
_FONT_CHAIN = (
    ("helv", None),
    ("nagarik-latin", FONTS_DIR / "NotoSans-Regular.ttf"),
    ("nagarik-deva", FONTS_DIR / "NotoSansDevanagari-Regular.ttf"),
)
_FONT_OBJECTS: dict = {}


def _font_object(name: str, path):
    """The measurable Font for a chain entry, or None if it cannot be loaded."""
    if name not in _FONT_OBJECTS:
        try:
            _FONT_OBJECTS[name] = (fitz.Font(fontname=name) if path is None
                                   else fitz.Font(fontfile=str(path)))
        except Exception:  # noqa: BLE001 — a missing face is not a crash
            _FONT_OBJECTS[name] = None
    return _FONT_OBJECTS[name]


def _font_for(text: str):
    """The first bundled face that can draw every character of `text`.

    Returns (fontname, fontfile_or_None, font_object), or None when no face
    covers the value — a Tamil or Gurmukhi name, say, for which nothing here
    has glyphs. The caller must then decline to write it rather than lay down
    a row of dots that reads as an answer.
    """
    chars = {c for c in str(text) if not c.isspace()}
    if not chars:
        return _FONT_CHAIN[0][0], None, _font_object(*_FONT_CHAIN[0])
    for name, path in _FONT_CHAIN:
        if path is not None and not path.exists():
            continue
        font = _font_object(name, path)
        if font is None:
            continue
        if all(font.has_glyph(ord(c)) for c in chars):
            return name, (str(path) if path else None), font
    return None


def _text_width(text: str, font, size: float) -> float:
    """Width of `text` in the face that will actually draw it."""
    try:
        return font.text_length(str(text), size)
    except Exception:  # noqa: BLE001
        return fitz.get_text_length(str(text), "helv", size)


def _format_value_for_fill(value, field_type: str = "text") -> str:
    """Format a value for writing into a PDF form field (no masking — full values needed)."""
    if value is None or value == "":
        return ""
    # One line, single-spaced, whatever arrived. A form field is a line on a
    # page: a value that is only whitespace is not a value at all, and an
    # embedded newline cannot be drawn — it comes out as a box glyph in the
    # middle of the citizen's address.
    val = " ".join(str(value).split())
    if not val:
        return ""
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
    field_values = _resolve_fallbacks(field_values, form_fields)

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
    # Discarding None matters: a catalog entry need not carry a fieldName, and
    # a position built from a profileKey alone has none either. Left in, the
    # two Nones matched and every such field was counted as already placed —
    # which silently emptied the very report a citizen relies on.
    placed_fields = {p.get("fieldName") for p in positions} - {None}
    out = []
    for f in form_fields:
        pk = f.get("profileKey")
        if not pk or pk in placed:
            continue
        if f.get("fieldName") and f["fieldName"] in placed_fields:
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


def _resolve_fallbacks(field_values: dict, form_fields: list) -> dict:
    """Fill in fields that borrow another field's answer when they have none.

    A form sometimes asks a narrower version of a question it has already
    asked: the Haryana achievements grid wants the *event*, having already
    asked for the *sport*. They are different questions — Athletics and the
    100m — so they are different fields, and the citizen may answer only the
    broader one. `fallbackProfileKey` says which answer stands in.

    The citizen's own answer always wins; this only supplies what they left
    blank, and never overwrites.
    """
    if not form_fields:
        return field_values or {}
    resolved = dict(field_values or {})
    for f in form_fields:
        pk, fallback = f.get("profileKey"), f.get("fallbackProfileKey")
        if not pk or not fallback or resolved.get(pk):
            continue
        borrowed = (field_values or {}).get(fallback)
        if borrowed:
            resolved[pk] = borrowed
    return resolved


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
    field_values = _resolve_fallbacks(field_values, form_fields)

    def _gave_up(error: str) -> dict:
        """A failure the citizen can still act on: every value, listed."""
        return {
            "success": False,
            "error": error,
            "method": "overlay",
            "total_positions": 0,
            "written": [],
            "unplaced": _unplaced_report([], field_values, form_fields),
        }

    if not _HAS_FITZ:
        return _gave_up("PyMuPDF not available")

    if not os.path.exists(source_pdf_path):
        return _gave_up(f"Source PDF not found: {source_pdf_path}")

    try:
        doc = fitz.open(source_pdf_path)
    except Exception as e:
        return _gave_up(f"Cannot open PDF: {e}")

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
            "written": [],
            # Nothing could be placed, which is exactly when the citizen most
            # needs to be told what the form still wants from them. An empty
            # report here would hand them a blank form and no list.
            "unplaced": _unplaced_report([], field_values, form_fields),
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

        # A value belongs beside its label, or just under it. Anything further
        # away is in another field's box — and on the Kisan Credit Card form
        # that meant a loan amount on the "Name of the Applicant" line, which
        # is a false statement on a signed declaration. Enforced here, at the
        # single point every placement rule passes through.
        label_y1 = pos.get("label_y1")
        if label_y1 is not None and not (
                pos.get("label_y0", label_y1) - 4 <= y <= label_y1 + MAX_BELOW_DROP):
            logger.info("Dropped '%s': placed %.0fpt from its label",
                        profile_key, y - label_y1)
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

        # Which face can actually draw this. None means no bundled font has
        # glyphs for it, and writing it would put dots on the page where the
        # citizen's name belongs — so it is left for the unplaced report.
        chosen = _font_for(formatted)
        if chosen is None:
            logger.warning("Dropped '%s': no bundled font can draw it; "
                           "reported for the citizen to write by hand",
                           profile_key)
            continue
        font_name, font_file, font = chosen

        # A composite box takes the parts that belong with it — the district,
        # state and PIN code that go in an address, the date that the
        # "Name of Tournament, Venue & Date" heading asks for. Only where the
        # box is tall enough to hold them; a one-line slot keeps the primary
        # value alone.
        satisfied = [profile_key]
        lines = [formatted]
        box = pos.get("box")
        max_width = pos.get("max_width") or 0
        if profile_key in COMPOSITE_FIELDS and box and max_width:
            room_for = int((box["y1"] - box["y0"]) // (font_size + 1.5))
            if room_for >= 2:
                combined, satisfied = _composite_text(
                    profile_key, field_values, form_fields)
                wrapped = _wrap_to_width(combined, max_width, font_size, room_for)
                if wrapped:
                    lines = wrapped
                    # Only the parts that actually made it onto the page count
                    # as filled. A line dropped for want of room is a value the
                    # citizen still has to write.
                    rendered = " ".join(wrapped)
                    satisfied = [
                        k for k in satisfied
                        if k == profile_key or _format_value_for_fill(
                            field_values.get(k),
                            next((f.get("type", "text") for f in form_fields or []
                                  if f.get("profileKey") == k), "text")) in rendered
                    ]
                else:
                    satisfied = [profile_key]
        elif box and max_width and not pos.get("comb"):
            # Not a composite, just too long for the width. Shrinking is the
            # first resort below, but a box two lines tall does not need a
            # value shrunk to 6pt — it needs it wrapped, which is what a person
            # filling the form in by hand would do.
            room_for = int((box["y1"] - box["y0"]) // (font_size + 1.5))
            if (room_for >= 2
                    and _text_width(formatted, font, font_size) > max_width):
                wrapped = _wrap_to_width(formatted, max_width, font_size,
                                         room_for, font)
                # Only when the whole value fits. A half-written name is worse
                # than one the citizen is told to write themselves.
                if wrapped and "".join(wrapped).replace(" ", "") == \
                        formatted.replace(" ", ""):
                    lines = wrapped

        page = doc[page_num]
        try:
            # Shrink to fit the space beside the label rather than running over
            # the cell border into the next column.
            #
            # And if shrinking is not enough, do not write at all. An earlier
            # version cut the value and appended an ellipsis, on the reasoning
            # that a visibly cut value tells the citizen to write it by hand.
            # It does not. "Government College for Women, B…" in the school
            # box of an admission form reads as an answer, and the citizen
            # signs beneath it; the ellipsis is three points wide and nobody
            # looks for it. The unplaced report already names the field, in
            # the citizen's own language, where they will actually read it.
            if max_width and not pos.get("comb"):
                def _widest(size):
                    return max(_text_width(ln, font, size) for ln in lines)

                while font_size > 6 and _widest(font_size) > max_width:
                    font_size -= 0.5
                if _widest(font_size) > max_width:
                    logger.info("Dropped '%s': needs %.0fpt in %.0fpt of space "
                                "even at %.1fpt type",
                                profile_key, _widest(font_size), max_width,
                                font_size)
                    continue
                formatted = lines[0]

            width = max(_text_width(ln, font, font_size) for ln in lines)
            candidate = {"x": x, "y": y, "width": width, "font_size": font_size}

            # Never write over a value already placed on this page.
            if any(_collides(candidate, other)
                   for other in claimed.get(page_num, [])):
                logger.info("Skipped '%s': would overlap a value already placed",
                            profile_key)
                continue

            comb_boxes = pos.get("comb")
            overflowed = False
            if comb_boxes:
                # One character to a box. The font is sized to the box, not to
                # the row, or a wide character spills over its own square.
                box_width = comb_boxes[0]["x1"] - comb_boxes[0]["x0"]
                font_size = min(font_size, box_width * 0.85)
                # An identifier's separators are noise the boxes replace; a
                # name's spaces are part of the name and take a box of their
                # own. Which of the two this is comes from the field's type.
                # A date's slashes go too: the boxes are DDMMYYYY, eight of
                # them, and "14/08/2005" is ten characters. Counting the
                # slashes made the value too long for its own comb, so the
                # date of birth went unplaced on a form that draws a box per
                # digit.
                numeric = field_type in ("aadhaar", "phone", "number", "date")
                glyphs, overflowed = _comb_glyphs(formatted, comb_boxes,
                                                  font_size, numeric=numeric,
                                                  font=font)
                for glyph in glyphs:
                    page.insert_text(
                        fitz.Point(glyph["x"], y), glyph["char"],
                        fontsize=font_size, fontname=font_name,
                        fontfile=font_file, color=(0, 0, 0.5),
                    )
                lines = [_comb_text(formatted, comb_boxes, numeric)]
            else:
                for offset, line in enumerate(lines):
                    page.insert_text(
                        fitz.Point(x, y + offset * (font_size + 1.5)),
                        line,
                        fontsize=font_size,
                        # The face chosen for this value: "helv" for anything
                        # Latin-1, an embedded Noto for the rest. Writing every
                        # value in helv turned Devanagari into middle dots.
                        fontname=font_name,
                        fontfile=font_file,
                        color=(0, 0, 0.5),  # Dark blue, distinct from print
                    )
            claimed.setdefault(page_num, []).append(candidate)
            written.append({
                "profileKey": profile_key,
                "fieldName": pos.get("fieldName", profile_key),
                "page": page_num + 1,
                "x": x, "y": y,
                "width": width,
                "font_size": font_size,
                # All of it. A value wrapped across two lines of a tall box is
                # fully on the page, but recording only the first line made
                # every summary the citizen reads — and the presence check
                # below — describe "Rajesh" where "Rajesh Sharma" was written.
                # `lines` keeps the geometry; `text` is what is on the form.
                "text": " ".join(lines),
                "lines": lines,
                "satisfies": satisfied,
                "comb_boxes": len(comb_boxes) if comb_boxes else 0,
                "truncated": overflowed,
                "box": pos.get("box"),
            })
            filled_count += 1
        except Exception as e:
            logger.warning(f"Failed to overlay text for '{profile_key}' at ({x},{y}): {e}")

    try:
        doc.save(output_path)
        doc.close()
    except Exception as e:
        doc.close()
        return _gave_up(f"Failed to save overlay PDF: {e}")

    placed_keys = [k for w in written for k in w.get("satisfies", [w["profileKey"]])]
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
    # "Full Name of Father" is the Daman & Diu phrasing, and "name of father"
    # does not begin that line, so the anchor test rejected the only match on
    # the page and the field went to the signature block instead.
    #
    # Father leads. A form that splits this combined field into separate
    # Father / Husband / Mother rows — as the Daman & Diu form does — offers a
    # blank husband row a student will not fill, and aliases are tried longest
    # first, so a "full name of husband" variant would be reached before "full
    # name of father" and claim the value for the wrong row. The generic
    # "father / husband" label still covers a form that prints the two
    # together; a husband-only form is left for the citizen to write, which is
    # the safe outcome for a field this ambiguous.
    "father_husband_name": ("full name of father",
                            "father's name", "fathers name", "father / husband",
                            "father's / husband's name",
                            "name of father", "पिता का नाम"),
    "mother_name": ("full name of mother", "mother's name", "mothers name",
                    "name of mother", "माता का नाम"),
    "guardian_name": ("guardian's name", "name of guardian"),
    "name": ("name of the applicant", "name of applicant", "applicant's name",
             "full name", "name of the student", "student's name",
             "आवेदक का नाम", "पूरा नाम"),
    "date_of_birth": ("date of birth", "dob", "जन्म तिथि", "जन्म दिनांक"),
    "gender": ("sex", "gender", "लिंग"),
    "category": ("category", "caste category", "श्रेणी", "जाति"),
    # "Aadhar Card No" is the Daman & Diu spelling, and neither "aadhar no"
    # nor "aadhar number" is a substring of it, so the field went unplaced on
    # a form that plainly asks for it. Longest first, as everywhere here.
    "aadhaar_number": ("aadhar card no", "aadhaar card no", "aadhar card number",
                       "aadhar no", "aadhaar no", "aadhar number",
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
    "institution_name": ("name of the college/institute",
                         "name of college/institute",
                         "name of the college/school", "name of college/school",
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
    "bank_name": ("name of the bank", "bank's name", "banks name",
                  "name of bank", "bank name", "बैंक का नाम"),
    "bank_account_number": ("saving bank account number", "bank account number",
                            "account no", "a/c no",
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
    "applied_other_scholarship": ("has the applicant applied for any other",
                                  "applied for any other sports scholarship",
                                  "any other sports scholarship"),
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

# A value written below its heading must stay close to it. Without a cap the
# two-row walk drifted out of one section of the Kisan Credit Card form and
# into the next, putting the loan amount on the "Name of the Applicant" line —
# which is worse than leaving it blank, because a wrong value on a signed form
# is a false declaration.
MAX_BELOW_DROP = 40.0

# A horizontal gap wider than this between two printed words means they belong
# to different columns, not to one label.
COLUMN_GAP = 22.0

# How far a data cell may start to the right of the heading it belongs to.
# A few points absorbs the padding a form leaves inside a cell; more than that
# means the cell belongs to something else.
COLUMN_ALIGN_TOLERANCE = 8.0
# A ruled cell holding no more than this many words is form furniture — a
# heading, a label, a pair of column titles — not a paragraph. Prose needs
# more words than this to be prose.
MAX_WORDS_IN_A_LABEL_CELL = 8

_SENTENCE_MARKERS = (
    " that ", " have ", " has been", " shall ", " will ", " are to ",
    " is to ", " i ", " my ", " been ", " enclose", " submitted",
)


def _printed_choice_pair(line: str, options: list) -> bool:
    """True when a line ends by printing this field's choices for ticking.

    "Yes/No", "Yes / No", "Male / Female" — the form offers the answers and
    leaves the space after them blank. Anchored to the end of the line so an
    option word appearing mid-sentence in a declaration does not qualify.
    """
    values = [str(o).strip().lower() for o in options if str(o).strip()]
    if len(values) < 2:
        return False
    tail = _normalise_token(line[-40:])
    for i, a in enumerate(values):
        for b in values[i + 1:]:
            if (_normalise_token(a + b) in tail
                    or _normalise_token(b + a) in tail):
                return True
    return False


_ITEM_NUMBER = re.compile(r"^\s*(?:\(?[0-9ivxa-z]{1,4}[).\]]\s*)+", re.IGNORECASE)


def _looks_like_a_label(text: str, options: list | None = None,
                        alias: str | None = None) -> bool:
    """True if this line is plausibly a field label rather than prose.

    Length and sentence structure decide it, not punctuation. An earlier
    version rejected anything ending in a full stop, which threw away
    "IFSC Code: --ll." — a perfectly good label followed by scan noise.
    """
    stripped = text.strip()
    if not stripped:
        return False

    # An instruction in brackets is not prose. "Date of Birth (Please write as
    # per Leaving Certificate of HSC)" is sixty-one characters, one over the
    # cap, and every one of them past "Birth" is telling the citizen how to
    # fill the field rather than adding a clause to a sentence.
    without_asides = re.sub(r"\([^)]*\)", "", stripped).strip()
    if without_asides and without_asides != stripped:
        return _looks_like_a_label(without_asides, options, alias)

    # A question printed on a form is a field, however long: "Has the applicant
    # applied for any other sports scholarship …?" is item 15 of the Haryana
    # form with a Yes/No box beside it, and rejecting it as prose left the box
    # blank on every application.
    if stripped.endswith("?"):
        return True
    # The same question when the "?" is on the next printed line. Item 15 wraps
    # as "…any other sports scholarship from Yes/No" / "SAI/Central Govt. …
    # achievements?", so the line carrying the answer slot has no question mark
    # at all — it ends in the choices themselves. A line offering this field's
    # own options as a printed pair is a question awaiting an answer, whatever
    # its punctuation, and the space just past them is where a person writes.
    if options and _printed_choice_pair(stripped, options):
        return True

    # A line that begins with the label being looked for may run past the
    # length cap — government forms write the instructions into the label
    # itself, and "a) Name of the College/Institute where Girl student is
    # pursing Diploma, P.G. Diploma, Graduation, Post-graduation course." is
    # one field on the Daman & Diu form, thrown away as prose by length alone.
    #
    # It lifts the cap and nothing else. Lifting the prose tests as well was a
    # mistake with teeth: a paragraph wraps where it likes, and the Daman & Diu
    # undertaking has a line beginning "State Government/ Union Territory
    # Administration that the information given by me…" — which starts with
    # "state", is not a field, and took the applicant's state into the middle
    # of a signed declaration.
    starts_with_alias = False
    if alias:
        opening = _ITEM_NUMBER.sub("", stripped).lower()
        starts_with_alias = opening.startswith(str(alias).strip().lower())
    if not starts_with_alias and len(stripped) > MAX_LABEL_CHARS:
        return False
    lowered = f" {stripped.lower()} "
    # Sentence markers only mean prose in a line long enough to be prose. OCR
    # leaves stray letters — this form yields "I Mother's Occupation:" — and
    # matching " i " in a 23-character label threw the field away.
    if len(stripped) > 25 and any(m in lowered for m in _SENTENCE_MARKERS):
        return False
    # Prose runs to several clauses; a label does not.
    return stripped.count(",") < 3 and stripped.count(".") < 3


def _alias_is_outranked(line: str, alias: str, profile_key: str) -> bool:
    """Does a longer label for a *different* field start at the same place?

    "full name" is one of the applicant's own aliases, and the Daman & Diu form
    prints "1. Full Name of Father", "2. Full Name of Husband", "3. Full Name
    of Mother". Each of those begins with "full name", each is anchored, and
    each has a comb of its own beneath it — so the applicant's name was written
    into the father's boxes, and the father's name was then dropped for
    colliding with it. The form was signed by a girl student under her father's
    name.

    Longest match at the same offset wins, and if it belongs to another field
    this occurrence is not ours. The same principle as `_alias_hit`, applied
    where the aliases are actually tried.
    """
    low = str(line).lower()
    own = str(alias).strip().lower()
    start = low.find(own)
    if start == -1:
        return False
    for other_key, aliases in FIELD_ALIASES.items():
        if other_key == profile_key:
            continue
        for other in aliases:
            candidate = str(other).strip().lower()
            if len(candidate) > len(own) and low.find(candidate) == start:
                return True
    return False


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


# Below this many characters a page is treated as having no text layer at all
# and is put through OCR. A scanned form with a handful of stray marks is not
# a form with text on it.
MIN_TEXT_LAYER_CHARS = 40

# Rendering resolution for OCR. 300 dpi is what Tesseract is tuned for; lower
# loses the small print that carries the field labels.
OCR_DPI = 300

# Cached on the Document itself, not in a module-level dict keyed by id().
# CPython reuses the address of a garbage-collected object, so an id()-keyed
# cache hands a *new* document the text page of a closed one — which raises on
# every lookup and silently reports a form as having no readable labels at all.
_OCR_ATTR = "_nagarik_ocr_pages"

# A second cache, across documents, keyed by the file itself.
#
# Auditing a form and then filling it opens the same PDF twice, and a Document
# cache cannot span the two. On the Daman & Diu form — fourteen legal-size
# pages, seven of them pure scans — that meant OCR ran twice over the same
# images: 298 seconds to audit and 267 to fill, for one application.
#
# Keyed on path, size and mtime together, so an edited or replaced file is
# re-read rather than answered from a stale entry. Words and text only: a
# TextPage belongs to the Document that made it and cannot outlive it, so what
# is kept here is the *result* of OCR, and searches are served from the words.
_OCR_FILE_CACHE: dict = {}
_OCR_FILE_CACHE_LIMIT = 64


def _file_key(doc):
    """Identity of the file behind a document, or None if it has no file."""
    path = getattr(doc, "name", None)
    if not path:
        return None
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (path, st.st_size, st.st_mtime_ns)


def clear_ocr_cache() -> None:
    """Forget every cached OCR result. For tests and long-running processes."""
    _OCR_FILE_CACHE.clear()


def _text_source(page):
    """A text page for `page`, running OCR when the PDF carries no text.

    Many published forms are pure images — the Kisan Credit Card form has
    exactly zero extractable characters. Without this every label lookup
    returns nothing, no value can be placed, and the form comes back blank
    with no explanation. Tesseract gives it a text layer to work from.

    OCR is never run over a substantial text layer that already exists: it
    would be slower and worse.

    A *thin* text layer is the awkward case. A one-line cover page, or a form
    whose only typed text is four field labels, falls under the threshold
    without being a scan — and OCR of a sparse page is dreadful, because there
    is little context to disambiguate a glyph. "Mobile No" came back as
    "wovieno", so the label was never found and the field went unfilled on a
    page whose real text layer said exactly what was wanted.

    So a thin layer is not discarded on trust: OCR runs, and its result is
    adopted only if it reads *more* words than the page already offers. On a
    genuine scan the native layer has nothing and OCR wins outright; on a
    sparse but typed page the native layer wins and is kept.

    Returns (words, text) when OCR is to be used, and None to mean "the page's
    own text is fine". The OCR *result* is what is cached rather than the
    TextPage that produced it, because a TextPage belongs to the Document that
    made it and dies with it — and auditing a form then filling it opens the
    same file twice.
    """
    doc = page.parent
    try:
        cache = getattr(doc, _OCR_ATTR)
    except AttributeError:
        cache = {}
        try:
            setattr(doc, _OCR_ATTR, cache)
        except Exception:  # noqa: BLE001 — cache is an optimisation, not a need
            cache = None
    if cache is not None and page.number in cache:
        return cache[page.number]

    file_key = _file_key(doc)
    entry = (file_key, page.number)
    if file_key is not None and entry in _OCR_FILE_CACHE:
        result = _OCR_FILE_CACHE[entry]
        if cache is not None:
            cache[page.number] = result
        return result

    def remember(result):
        if cache is not None:
            cache[page.number] = result
        if file_key is not None:
            if len(_OCR_FILE_CACHE) >= _OCR_FILE_CACHE_LIMIT:
                _OCR_FILE_CACHE.clear()
            _OCR_FILE_CACHE[entry] = result
        return result

    try:
        native_words = page.get_text("words")
    except Exception:  # noqa: BLE001
        native_words = [1]  # unreadable: assume text and leave the page alone
    try:
        native_chars = len(page.get_text().strip())
    except Exception:  # noqa: BLE001
        native_chars = MIN_TEXT_LAYER_CHARS
    if native_chars >= MIN_TEXT_LAYER_CHARS:
        return remember(None)

    try:
        textpage = page.get_textpage_ocr(dpi=OCR_DPI, full=True)
        ocr_words = page.get_text("words", textpage=textpage)
        # Decisively more, not merely more. A page carrying a handful of real
        # typed words and a page that is a scan with a stray mark on it both
        # fall under the character threshold, and only the second should be
        # re-read. OCR of a sparse page invents words — "Mobile No" came back
        # as "wovieno" — so on a near-tie the page's own text wins. A genuine
        # scan is not a near-tie: it reads nothing natively and hundreds of
        # words under OCR.
        if len(native_words) < 2 or len(ocr_words) >= 3 * len(native_words):
            logger.info("Page %d had a %d-character text layer; OCR read %d "
                        "words against %d and was used instead",
                        page.number, native_chars, len(ocr_words),
                        len(native_words))
            return remember((ocr_words, page.get_text(textpage=textpage)))
        logger.info("Page %d has a thin text layer (%d characters) but OCR "
                    "read no more than it; keeping the page's own text",
                    page.number, native_chars)
    except Exception as exc:  # noqa: BLE001 — tesseract may be absent
        logger.warning("Thin text layer and OCR unavailable (%s): the form "
                       "will be filled from what text there is and the rest "
                       "reported as unplaced", type(exc).__name__)
    return remember(None)


def _search_words(words, needle: str) -> list:
    """Find `needle` in a words list, the way search_for finds it in a page.

    Needed because the OCR result outlives the TextPage it came from, and
    `search_for` requires a TextPage. Matching is done on each line's
    concatenated text, so a needle spanning several words — or sitting inside
    one, as "name" sits inside "Surname" — is found exactly as before.
    """
    target = str(needle or "").lower()
    if not target:
        return []
    lines: dict = {}
    for w in words:
        lines.setdefault((w[5], w[6]), []).append(w)

    out = []
    for row in lines.values():
        row.sort(key=lambda w: w[0])
        text, spans = "", []
        for w in row:
            if text:
                text += " "
                spans.append((w, None, 0))
            piece = str(w[4])
            for i in range(len(piece)):
                spans.append((w, i, len(piece)))
            text += piece
        lowered = text.lower()
        start = lowered.find(target)
        while start != -1:
            covered = [s for s in spans[start:start + len(target)]
                       if s[1] is not None]
            if covered:
                # Interpolated across the word, not snapped to its edges. A
                # needle matching the front of a longer printed word — "Name"
                # inside "Name:-" — must not push the value out past the whole
                # word, or every value drifts right of where it belongs.
                first, last = covered[0], covered[-1]
                x0 = first[0][0] + (first[0][2] - first[0][0]) * (
                    first[1] / first[2])
                x1 = last[0][0] + (last[0][2] - last[0][0]) * (
                    (last[1] + 1) / last[2])
                out.append(fitz.Rect(x0, min(c[0][1] for c in covered),
                                     x1, max(c[0][3] for c in covered)))
            start = lowered.find(target, start + 1)
    out.sort(key=lambda r: (r.y0, r.x0))
    return out


def _page_words(page):
    """Words on a page, from OCR when the PDF has no text of its own."""
    ocr = _text_source(page)
    if ocr is not None:
        return ocr[0]
    try:
        return page.get_text("words")
    except Exception:  # noqa: BLE001
        return []


def _page_text(page) -> str:
    ocr = _text_source(page)
    if ocr is not None:
        return ocr[1]
    try:
        return page.get_text()
    except Exception:  # noqa: BLE001
        return ""


def _page_search(page, needle: str):
    ocr = _text_source(page)
    if ocr is not None:
        return _search_words(ocr[0], needle)
    try:
        return page.search_for(needle, quads=False)
    except Exception:  # noqa: BLE001
        return []


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

    words = _page_words(page)
    if not words:
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
            best, best_start, best_len = 0.0, -1, len(target)
            # Window length varies by two either way. OCR drops and doubles
            # characters — "Parti~ipation" loses one — and a fixed-length
            # window can never line up with a string that is shorter than the
            # thing it is meant to match.
            for length in range(max(4, len(target) - 2), len(target) + 3):
                for i in range(len(joined) - length + 1):
                    score = _token_ratio(joined[i:i + length], target)
                    if score > best:
                        best, best_start, best_len = score, i, length
            # The first character must survive as well. Father/mother,
            # his/her and son/daughter all differ at the front and are
            # otherwise close enough to trade places, and a label that names
            # the wrong person is worse than one that matches nothing.
            if (best < OCR_TOKEN_SIMILARITY
                    or joined[best_start:best_start + 1] != target[:1]):
                continue
            start = best_start
            end = start + best_len - 1
        else:
            end = start + len(target) - 1

        end = min(end, len(owner) - 1)
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
        rects = _page_search(page, variant)
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


def _comb_text(value: str, boxes: list, numeric: bool) -> str:
    """What a comb actually ends up carrying, spaces and truncation included.

    Reported back as the written text, so the verification check and the
    citizen's summary both describe the page rather than the intention.
    """
    text = str(value)
    cleaned = re.sub(r"[\s\-/.]", "", text) if numeric else " ".join(text.split())
    return cleaned[:len(boxes)]


def _comb_glyphs(value: str, boxes: list[dict], font_size: float,
                 numeric: bool = True, font=None) -> list[dict]:
    """One character per box, each centred in its own square.

    For a number, separators are dropped first. A citizen types
    "2345 6789 0124" or "PUNB0123456" and the form's twelve squares expect the
    characters alone; writing the spaces would push the last digits out of the
    comb entirely.

    For a name it is the opposite. A comb for a name leaves an empty box where
    the space goes — that is how everyone fills one in, and how a data-entry
    operator reads it back. Stripping the space wrote "SnehaFernandes" across
    the boxes of the Daman & Diu form: one character to a square, perfectly
    aligned, and not the applicant's name.

    A value longer than the comb is truncated rather than overflowed — running
    past the last box puts characters on whatever is printed beside it — and
    the caller is told, because a truncated identifier is worse than none and
    the citizen must be sent to complete it by hand.
    """
    if font is None:
        font = _font_object(*_FONT_CHAIN[0])
    text = str(value)
    cleaned = re.sub(r"[\s\-/.]", "", text) if numeric else " ".join(text.split())
    glyphs = []
    for char, box in zip(cleaned, boxes):
        if char == " ":
            continue          # the empty box is the separator
        width = _text_width(char, font, font_size)
        centre = (box["x0"] + box["x1"]) / 2
        glyphs.append({"char": char, "x": centre - width / 2})
    return glyphs, len(cleaned) > len(boxes)


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


# Fields a printed form gathers into one box, with the parts it absorbs.
#
# A form has one "Address:" area, not four lines for address, district, state
# and PIN code — a person writes the lot into the box. Treating them as four
# fields left State and PIN Code permanently unfillable on a form that has
# obvious room for them. The same is true of "Name of Tournament, Venue &
# Date", whose own heading says it wants the date as well.
#
# Only ever used where the box has room for the extra lines; a single-line slot
# still gets the primary value alone.
COMPOSITE_FIELDS: dict[str, tuple[str, ...]] = {
    "address_line": ("district", "state", "pincode"),
    "event_name": ("event_date",),
}


def _composite_text(primary: str, field_values: dict,
                    form_fields: list) -> tuple[str, list[str]]:
    """The full text for a composite box, and the keys it accounts for."""
    parts = COMPOSITE_FIELDS.get(primary, ())
    base = _format_value_for_fill(
        field_values.get(primary),
        next((f.get("type", "text") for f in (form_fields or [])
              if f.get("profileKey") == primary), "text"))
    if not parts:
        return base, [primary]

    satisfied = [primary]
    pieces = [base]
    for key in parts:
        value = (field_values or {}).get(key)
        if value in (None, ""):
            continue
        field_type = next((f.get("type", "text") for f in (form_fields or [])
                           if f.get("profileKey") == key), "text")
        rendered = _format_value_for_fill(value, field_type)
        if not rendered or rendered in base:
            continue
        # A PIN code reads as "- 124507" after the place names, which is how
        # an Indian address is written.
        pieces.append(f"- {rendered}" if key == "pincode" else rendered)
        satisfied.append(key)
    return ", ".join(pieces).replace(", - ", " - "), satisfied


def _wrap_to_width(text: str, width: float, font_size: float,
                   max_lines: int, font=None) -> list[str]:
    """Break text into lines that fit the box, longest-first, never mid-word.

    Measured in the face that will draw it — a Devanagari name is a different
    width in Noto Devanagari than the Latin fallback would suggest.
    """
    if font is None:
        font = _font_object(*_FONT_CHAIN[0])
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if current and _text_width(trial, font, font_size) > width:
            lines.append(current)
            current = word
            if len(lines) >= max_lines:
                break
        else:
            current = trial
    if current and len(lines) < max_lines:
        lines.append(current)
    return lines


# Values a form records by *which printed column you write under*, rather than
# by a line of its own.
#
# The Haryana form has no "Position Obtained" field. It has a Medal Won grid
# with Gold / Silver / Bronze / Participation columns, and a first place is
# recorded by writing under Gold. Both lists describe the same podium in the
# same order, so the mapping is a correspondence rather than a guess.
#
# The citizen's own word is written under the matching column, not a tick. A
# tick asserts the medal and is unattributable; "First" written under Gold
# carries exactly what the citizen said and lets a clerk see the mapping and
# correct it. Clause 16 of this form makes false information a criminal
# matter, so the form must never say more than the applicant did.
OPTION_GRIDS: dict[str, dict] = {
    "achievement_position": {
        # A heading that survives OCR and identifies the grid.
        "anchor": ("medal won", "medal"),
        # Column order, left to right, matching the field's own options.
        "order": ("First", "Second", "Third", "Participation"),
    },
}


def _grid_columns(page, anchor_rect, words, horizontals):
    """The columns of the sub-heading row beneath a grid's parent heading.

    Read from where the columns *are*, not from what they say. On this form the
    medal headings OCR as ".G.Qkl", "SilY.er" and "Brnnze" — unreadable by any
    threshold that also keeps "father" and "mother" apart. Their positions are
    exact, and their left-to-right order is the order of the field's options.

    The parent's own cell is not used to bound the search: "Medal Won" spans
    two cells on this form, so its rect covers only half the grid. The row
    below the anchor's row is taken whole, and the caller's requirement that
    the column count match the option count exactly is what stops this reading
    an unrelated row.
    """
    rows = sorted(horizontals or [])
    below = [y for y in rows if y > anchor_rect.y1 - 1]
    if len(below) < 2:
        return []
    top, bottom = below[0], below[1]
    if bottom - top < 6:
        return []

    inside = sorted((w for w in words
                     if top - 1 <= (w[1] + w[3]) / 2 <= bottom + 1),
                    key=lambda w: w[0])
    columns: list[list[float]] = []
    for wx0, _, wx1, *_ in inside:
        if columns and wx0 - columns[-1][1] < 6:
            columns[-1][1] = max(columns[-1][1], wx1)
        else:
            columns.append([wx0, wx1])
    band = form_geometry.Cell(
        min(c[0] for c in columns) if columns else 0, top,
        max(c[1] for c in columns) if columns else 0, bottom)
    return [(a, b, band) for a, b in columns]


def _option_column_position(page, cells, horizontals, words, profile_key: str,
                            value, form_fields: list, page_number: int):
    """Place a value under the printed column that stands for it.

    Only fires when the grid can be identified by a heading that survived OCR
    *and* its column count matches the field's declared options exactly. Both
    conditions matter: without the anchor this would write into any grid it
    found, and without the count check a misread column would shift every
    value one place along — which on a scholarship form means claiming a
    different medal than the applicant won.

    The citizen's own word is written, never a tick. Clause 16 of this form
    makes false information a criminal matter, so the page must never assert
    more than the applicant did: "First" under the Gold column says exactly
    what they said, and a clerk can see the mapping and correct it.
    """
    spec = OPTION_GRIDS.get(profile_key)
    if not spec or value in (None, ""):
        return None
    order = spec["order"]
    try:
        index = [o.lower() for o in order].index(str(value).strip().lower())
    except ValueError:
        return None

    for anchor in spec["anchor"]:
        rects = _label_rects(page, anchor)
        if not rects:
            continue
        columns = _grid_columns(page, rects[0], words, horizontals)
        if len(columns) != len(order):
            continue
        left, right, band = columns[index]

        # Bounded by this column's own printed heading, not by whatever cell
        # the grid happens to have been divided into. The row under this grid
        # is split into three cells for four columns, so snapping to a cell
        # put "First" and "Second" in the same place.
        below = sorted(y for y in (horizontals or []) if y > band.y1 + 1)
        bottom = below[0] if below else band.y1 + 16
        write_area = form_geometry.Cell(left, band.y1, right,
                                        min(bottom, band.y1 + 20))
        if not form_geometry.is_blank(write_area, words):
            continue
        font_size = min(max(band.height - 3, 6.5), 9.5)
        if write_area.width < 12:
            continue
        return {
            "profileKey": profile_key,
            "page": page_number,
            "x": write_area.x0 + 2,
            "y": write_area.y0 + min(font_size + 1,
                                     max(write_area.height - 1, font_size)),
            "font_size": font_size,
            "max_width": write_area.width - 4,
            "box": write_area.as_dict(),
            "under_column": index,
        }
    return None


class _Rect:
    """Minimal rectangle for passing a synthesised column to form_geometry."""

    def __init__(self, x0, y0, x1, y1):
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1


def _line_at(words, rect, tolerance: float = 2.0) -> str:
    """The printed phrase a rectangle belongs to.

    Two things this has to avoid, and they pull in opposite directions.

    Searching the page text for the label returns the *first* line containing
    it, so a label that appears twice — "Amount of loan required" sits in a
    section heading and again as a field on the Kisan Credit Card form — is
    judged by the wrong one, and the real field gets thrown away with the
    heading.

    Grouping by the extractor's own block and line is no better: PyMuPDF
    merged the row-14 prose of the Haryana form with the table heading beneath
    it, so "Name of Tournament, Venue & Date" arrived interleaved with a
    sentence and was rejected as prose.

    So: the words on this rect's own visual row, expanded outward only while
    they stay close together. A wide horizontal gap is the next column, not
    more of this label.
    """
    band_top, band_bottom = rect.y0 - tolerance, rect.y1 + tolerance
    on_row = sorted((w for w in words
                     if band_top <= (w[1] + w[3]) / 2 <= band_bottom),
                    key=lambda w: w[0])
    if not on_row:
        return ""

    inside = [i for i, w in enumerate(on_row)
              if not (w[2] < rect.x0 - tolerance or w[0] > rect.x1 + tolerance)]
    if not inside:
        return " ".join(w[4] for w in on_row)

    start, end = min(inside), max(inside)
    while start > 0 and on_row[start][0] - on_row[start - 1][2] < COLUMN_GAP:
        start -= 1
    while end + 1 < len(on_row) and on_row[end + 1][0] - on_row[end][2] < COLUMN_GAP:
        end += 1
    # Scan specks are dropped from the phrase but kept in the gap arithmetic
    # above: "10·. .. Bank's Name:" carries three stray dots, and counting them
    # as punctuation made a plain label look like prose.
    return " ".join(w[4] for w in on_row[start:end + 1]
                    if not form_geometry._is_scan_noise(w[4]))


def _place_in_grid(cells, horizontals, label_rect, words, page_width: float,
                   needed: float, font_size: float, options=None,
                   comb_chars: int = 0):
    """Where to write a value on a ruled form, as (x, baseline_y, width).

    Two placements, tried in the order a person would:

    1. **Beside the label**, in the first gap the value actually fits. A short
       value belongs next to its own label, not in whatever space happens to be
       widest on the row.
    2. **Below the label**, when it is a column heading with a blank box under
       it. "Name of the College/School | Class | Session | Admission No." is a
       header row with nothing beside the headings and an empty row waiting
       underneath. Placing beside-only reported the college name unfillable on
       a form that plainly has room for it, and crushed the class into the
       25 points before the next column.

    Returns None when neither works, so the caller reports the field unplaced
    rather than writing it somewhere a clerk will not look.
    """
    # A comb comes first. A row of small squares is unmistakable, and a value
    # written across it as one string produces a form a clerk will reject —
    # the characters do not line up with the boxes, and an operator keying from
    # the squares reads nonsense.
    comb = form_geometry.comb_for(cells, label_rect, words)
    # Only if the value fits it. Filling the boxes one character at a time and
    # stopping when they run out writes a different number — or a different
    # name — from the one the citizen gave, aligned so neatly that nothing on
    # the page suggests anything is missing. On the Daman & Diu form that put
    # "Anthony" where "Anthony Fernandes" belonged. A comb too short is not
    # this field's box: step past it and let the other rules look, and if none
    # finds a home the field is reported for the citizen to write by hand.
    if comb is not None and comb_chars and comb_chars > len(comb):
        logger.info("Comb of %d boxes cannot hold a %d-character value; "
                    "looking elsewhere on the row", len(comb), comb_chars)
        comb = None
    if comb is not None:
        return {"x": comb[0].x0, "y": comb[0].y1 - 4,
                "width": comb[-1].x1 - comb[0].x0,
                "box": form_geometry.Cell(comb[0].x0, comb[0].y0,
                                          comb[-1].x1, comb[0].y1),
                "below": False,
                "comb": [c.as_dict() for c in comb]}

    # A cell beside the label holding only this field's own choices — "Yes/No"
    # next to a question — is the answer cell, not an occupied one.
    choice = form_geometry.option_cell_right_of(cells, label_rect, words,
                                                options or [])
    if choice is not None:
        cell, start = choice
        return {"x": start, "y": label_rect.y1 - 1.5,
                "width": cell.x1 - start - 3, "box": cell, "below": False}

    # An empty cell on the label's own row settles it: that is the field's box,
    # whatever else the page offers. Checked before the gap arithmetic because
    # a row whose cells came out fragmented can hide a perfectly good box from
    # the gap calculation, and a blank cell below in the *next section* then
    # looks like the better answer. It is not.
    own_row = form_geometry.blank_cell_right_of(cells, label_rect, words)
    if own_row is not None:
        return {"x": own_row.x0 + 3, "y": label_rect.y1 - 1.5,
                "width": own_row.width - 6, "box": own_row, "below": False}

    gaps = form_geometry.writable_gaps(cells, label_rect, words, page_width)
    fits = next((g for g in gaps if g[1] - g[0] >= needed), None)
    if fits is not None:
        box = form_geometry.cell_containing(
            cells, fits[0] + 1, (label_rect.y0 + label_rect.y1) / 2)
        return {"x": fits[0], "y": label_rect.y1 - 1.5,
                "width": fits[1] - fits[0], "box": box, "below": False}

    # A label too long to leave room beside itself. The colon that ends it, on
    # the line below, is the form saying where the answer goes — and the rule
    # drawn after that colon is where a person would write.
    anchor = form_geometry.colon_anchor(cells, label_rect, words)
    if anchor is not None:
        left, right, baseline = anchor
        if right - left >= max(needed * MIN_LEGIBLE_FRACTION,
                               form_geometry.MIN_DATA_CELL_WIDTH):
            # One line tall, deliberately. The enclosing cell holds the label
            # as well, and a box reported as its full height would let a long
            # value wrap downward out of the cell — or, worse, upward through
            # the printed label it answers.
            box = form_geometry.Cell(left, baseline - font_size - 1,
                                     right, baseline + 1)
            return {"x": left, "y": baseline, "width": right - left,
                    "box": box, "below": True}

    # Two rows deep, because a table can carry a two-line heading: the Kisan
    # Credit Card form prints "Name of the | Survey/ Khasra | Title | Area in
    # acres" and then "Village | No. | Owned Leased Share Cropper | ..." before
    # the blank data row. Safe at this depth because every candidate row must
    # be blank across all its cells, and MAX_BELOW_DROP caps how far a value
    # may travel from its own heading.
    data_cell = form_geometry.header_data_cell(
        cells, label_rect, words, max_depth=2, horizontals=horizontals)
    # A column heading sits *above* its data cell, so the cell must start at or
    # before the label does. Without this the Kisan Credit Card form put the
    # loan amount in the "Name of the Applicant" box: that cell is blank and
    # directly below, but it begins 90 points to the right of the label, which
    # is what gives it away as a different field's box.
    aligned = (data_cell is not None
               and data_cell.x0 <= label_rect.x0 + COLUMN_ALIGN_TOLERANCE)
    if aligned and data_cell.y0 - label_rect.y1 <= MAX_BELOW_DROP:
        # Bounded to this heading's own column, so "Session" and "Admission
        # No." sharing one undivided box still write under their own headings
        # instead of on top of each other.
        left = max(data_cell.x0 + 3, label_rect.x0)
        right = data_cell.x1 - 3
        # A data row under column headings is usually two or three lines tall,
        # because the form expects a long entry — an institution's full name in
        # a 170-point column. The value is wrapped when it is written, so the
        # width it must satisfy is the width per line, not the whole value on
        # one line. Judging it as a single line rejected the cell the form drew
        # for exactly this purpose and left the field blank.
        rows = max(1, int(data_cell.height // (font_size + 1.5)))
        if right - left >= max(needed * MIN_LEGIBLE_FRACTION / rows,
                               form_geometry.MIN_DATA_CELL_WIDTH):
            baseline = data_cell.y0 + min(font_size + 1, data_cell.height - 1)
            if baseline - label_rect.y1 <= MAX_BELOW_DROP:
                return {"x": left, "y": baseline, "width": right - left,
                        "box": data_cell, "below": True}

    if gaps:
        widest = max(gaps, key=lambda g: g[1] - g[0])
        box = form_geometry.cell_containing(
            cells, widest[0] + 1, (label_rect.y0 + label_rect.y1) / 2)
        return {"x": widest[0], "y": label_rect.y1 - 1.5,
                "width": widest[1] - widest[0], "box": box, "below": False}
    return None


def _place_beside_label(cells, label_rect, words, page_width: float,
                        needed: float):
    """The blank space on the label's own line, for a label outside the grid.

    A ruled form is not ruled all the way down. The Haryana form's last two
    questions are printed as running text below the final table, with the
    answer space left blank at the end of the line — no cell within a hundred
    points. Requiring a cell there meant a question the citizen had answered
    was left off the form entirely.

    The bounds are `writable_gaps`', so this is the same discipline as the
    gridded path minus the cell: never over a printed word, never past the
    next label, never off the page.
    """
    gaps = form_geometry.writable_gaps(cells, label_rect, words, page_width)
    want = max(needed, MIN_USABLE_WIDTH) if needed else MIN_USABLE_WIDTH
    fits = next((g for g in gaps if g[1] - g[0] >= want), None)
    if fits is None:
        return None
    return {"x": fits[0], "y": label_rect.y1 - 1.5,
            "width": fits[1] - fits[0], "box": None, "below": False}


def _needed_width(profile_key: str, field_values: dict, form_fields: list,
                  font_size: float) -> float:
    """Width in points the formatted value would occupy, or 0 if unknown."""
    value = (field_values or {}).get(profile_key)
    if not value:
        return 0.0
    field_type = next((f.get("type", "text") for f in (form_fields or [])
                       if f.get("profileKey") == profile_key), "text")
    formatted = _format_value_for_fill(value, field_type)
    chosen = _font_for(formatted)
    if chosen is None:
        return 0.0
    try:
        return _text_width(formatted, chosen[2], font_size)
    except Exception:  # noqa: BLE001 — an unmeasurable value is placed anyway
        return 0.0


def _answer_marker_after(words, label_rect, options=None) -> bool:
    """Does something on this line mark where an answer goes?

    A form without printed rules still says where to write: it puts a colon
    after the label, draws a leader of dots or underscores, or prints the
    choices to tick. This is what separates "Full Name: ______" from a
    sentence that happens to contain the word "name".

    Checked only on the label's own line and only to its right, because that
    is where the marker for *this* label would be.
    """
    centre_y = (label_rect.y0 + label_rect.y1) / 2
    after = [w for w in words
             if label_rect.y0 - 2 <= (w[1] + w[3]) / 2 <= label_rect.y1 + 2
             and w[2] > label_rect.x1 - 2]
    if not after:
        return False
    after.sort(key=lambda w: w[0])

    for w in after[:3]:
        text = str(w[4]).strip()
        if not text:
            continue
        # A colon, or the label's own trailing colon carried in the same token.
        if text.startswith(":") or text.endswith(":") or text.endswith(":-"):
            return True
        # A leader: a run of dots, underscores or dashes is the line to write
        # on, not something to write around.
        if len(text) >= 2 and all(c in "._-–—…·" for c in text):
            return True
    line = " ".join(str(w[4]) for w in after)
    if options and _printed_choice_pair(line, options):
        return True
    # Or the whole line ends at a colon, with the answer space beyond it.
    own = (_line_at(words, label_rect) or "").rstrip()
    return own.endswith(":") or own.endswith(":-")


def _label_is_anchored(cells, words, label_rect, alias: str, options=None) -> bool:
    """Is this occurrence of the alias a field label, or a word in a sentence?

    Every field label on a printed form is anchored: it begins its line, or
    begins its cell, or is followed by the mark that says an answer goes here.
    A word inside a paragraph is none of those, and the same word is often
    both. The Daman & Diu form carries

        "…that the information given by me is true…"
        "…thereby reducing gender disparity…"

    and matching "state" and "gender" in them wrote "Haryana" and "Female"
    into the middle of a declaration the citizen signs. That is not a
    misplaced value, it is a false statement, and it is the one outcome this
    filler must never produce.

    Item numbers are stripped before the start test, because "15. Has the
    applicant…" and "a) Name of the College…" are labels that begin their
    line as far as a form is concerned.
    """
    text = str(alias).strip().lower()
    if not text:
        return False

    line = (_line_at(words, label_rect) or "").strip().lower()
    if line:
        opening = _ITEM_NUMBER.sub("", line)
        if opening.startswith(text):
            return True

    cell = form_geometry.cell_containing(
        cells, (label_rect.x0 + label_rect.x1) / 2,
        (label_rect.y0 + label_rect.y1) / 2)
    if cell is not None:
        inside = [w for w in words
                  if cell.x0 - 1 <= w[0] and w[2] <= cell.x1 + 1
                  and cell.y0 - 1 <= (w[1] + w[3]) / 2 <= cell.y1 + 1
                  and not form_geometry._is_scan_noise(str(w[4]))]
        if inside:
            first = min(inside, key=lambda w: (round(w[1] / 4), w[0]))
            if label_rect.x0 <= first[0] + 2:
                return True
            # Or the cell holds only a heading or two. A ruled cell with a
            # handful of words in it is a form's own furniture, not a
            # paragraph — "Session Admission No." is one box carrying two
            # column headings on the Haryana form, and requiring the label to
            # come first in the cell lost the second of them. Prose fills a
            # cell with sentences, and is excluded by the count.
            if len(inside) <= MAX_WORDS_IN_A_LABEL_CELL:
                return True

    return _answer_marker_after(words, label_rect, options)


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

    # Keyed by fieldName, not profileKey. A form can ask for one value twice —
    # the Haryana sports table wants the discipline under "Game/Sport" and
    # again in the "Event" column of the achievements grid — and keying by
    # profileKey filled only the first and silently dropped the second.
    catalog_labels: dict[str, tuple] = {}
    field_key: dict[str, str] = {}
    for f in form_fields:
        pk = f.get("profileKey", "")
        name = f.get("fieldName") or pk
        if not pk or not name:
            continue
        field_key[name] = pk
        # The field's printed labels only. `fieldName` is an internal
        # identifier — "academic_session", "event_discipline" — and feeding it
        # to the fuzzy matcher had it land on unrelated words halfway up the
        # page. A name nobody prints cannot be found on a printed form.
        catalog_labels[name] = tuple(
            str(lbl).strip().rstrip(":")
            for lbl in (f.get("labelEnglish"), f.get("labelHindi"))
            if lbl
        )

    wanted = [name for name, pk in field_key.items()
              if not field_values or field_values.get(pk) not in (None, "")]

    best: dict[str, dict] = {}

    for page_num in range(len(doc)):
        page = doc[page_num]
        page_width = page.rect.width
        words = _page_words(page)
        # The ruled grid, read off the scan. Empty for an unruled document, in
        # which case bounds fall back to the next printed word.
        cells = form_geometry.build_cells(page)
        horizontals, _ = form_geometry.detect_rules(page)
        # Full lines, used only to decide whether a hit sits inside prose.
        lines = [ln for ln in _page_text(page).splitlines() if ln.strip()]

        for name in wanted:
            pk = field_key[name]
            # The field's own labels are tried before the aliases it shares
            # through its profileKey. "Event" and "Game/Sport" are two columns
            # asking for the discipline, and ranking by length alone sent both
            # to the same printed label — so one filled and the other was
            # dropped as an overlap.
            own = sorted({c for c in catalog_labels[name] if c},
                         key=len, reverse=True)
            shared = sorted({c for c in FIELD_ALIASES.get(pk, ()) if c
                             and c not in catalog_labels[name]},
                            key=len, reverse=True)
            candidates = own + shared
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
                options = next((f.get("options") for f in form_fields
                                if f.get("fieldName") == name), None)
                ftype = next((f.get("type", "text") for f in form_fields
                              if f.get("fieldName") == name), "text")
                comb_chars = len(_comb_text(
                    _format_value_for_fill(field_values.get(pk), ftype),
                    [None] * 10_000,
                    ftype in ("aadhaar", "phone", "number", "date")))
                for rect in rects:
                    # This rect's own line, so two occurrences of one label are
                    # judged separately.
                    context = _line_at(words, rect) or alias
                    if not _looks_like_a_label(context, options, alias):
                        continue
                    # And it must be anchored as a label, not merely present in
                    # a sentence. See _label_is_anchored: this is what keeps a
                    # value out of the middle of a signed declaration.
                    # Not ours if a longer label for another field starts in
                    # the same place. "Full Name of Father" outranks the
                    # applicant's own "full name".
                    if _alias_is_outranked(context, alias, pk):
                        logger.info(
                            "Dropped '%s': %r is outranked on %r by a longer "
                            "label for another field", pk, alias, context[:60])
                        continue
                    if not _label_is_anchored(cells, words, rect, alias,
                                              options):
                        logger.info(
                            "Dropped '%s': %r appears mid-sentence in %r, with "
                            "nothing marking it as a field",
                            pk, alias, context[:70])
                        continue

                    y = rect.y1 - 1.5
                    height = rect.y1 - rect.y0
                    font_size = min(max(height - 2, 6.5), 10.5)

                    needed = _needed_width(pk, field_values, form_fields, font_size)

                    if cells:
                        spot = _place_in_grid(cells, horizontals, rect, words,
                                              page_width, needed, font_size,
                                              options=options,
                                              comb_chars=comb_chars)
                        # A ruled form still carries prose questions in its
                        # margins — item 15 of the Haryana form sits below the
                        # last table with no cell anywhere near it. Falling
                        # through to the ungridded rule places it in the blank
                        # space its own row offers, instead of abandoning the
                        # field because the *page* happens to have a grid.
                        if spot is None and form_geometry.cell_containing(
                                cells, rect.x1 + 1,
                                (rect.y0 + rect.y1) / 2) is None:
                            spot = _place_beside_label(
                                cells, rect, words, page_width, needed)
                        if spot is None:
                            continue
                        x, y, available = spot["x"], spot["y"], spot["width"]
                        box = spot["box"]
                        comb = spot.get("comb")

                        # Last line of defence, independent of which rule
                        # produced the position: a value belongs beside or just
                        # under the label it answers. Anything further away is
                        # in someone else's box, and a wrong value on a signed
                        # form is a false declaration — so it is dropped and
                        # reported unplaced instead.
                        if not (rect.y0 - 4 <= y <= rect.y1 + MAX_BELOW_DROP):
                            logger.info(
                                "Dropped '%s': placement %.0fpt from its label",
                                pk, y - rect.y1)
                            continue
                    else:
                        # No grid on this page, so there is no cell structure
                        # to confirm that this is a field at all — and a page
                        # of prose will happily hand over a match. The Daman &
                        # Diu scheme note reads "…thereby reducing gender
                        # disparity", and "Female" was written into the middle
                        # of that sentence because "gender" is an alias and the
                        # line was short enough to pass for a label.
                        #
                        # Without rules, a form marks its fields the only other
                        # way it can: a colon, a dotted or underscored leader,
                        # or its printed choices. One of those must follow the
                        # label. Prose has none of them.
                        x = rect.x1 + 5
                        available = max(
                            _right_bound(words, rect, page_width) - x, 0)
                        box = None
                        comb = None

                    # Enough room for most of the value, not merely enough to
                    # start it. A college name shrunk to 6pt and cut to
                    # "…nt College for Women, Bahadur…" is not information a
                    # clerk can use; the citizen is better served being told to
                    # write it in the space provided.
                    # Measured per line. A data row under a column heading is
                    # often two or three lines tall precisely because the entry
                    # is long, and the value is wrapped when written, so judging
                    # it as one unbroken line rejects the box the form drew for
                    # it. Only the space actually available counts: a one-line
                    # slot still has to hold the value on one line.
                    rows = 1
                    if box is not None and not comb:
                        rows = max(1, int((box.y1 - box.y0) // (font_size + 1.5)))
                    if needed and available * rows < needed * MIN_LEGIBLE_FRACTION:
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
                        "fieldName": name,
                        "page": page_num + 1,
                        "x": x, "y": y,
                        "font_size": font_size,
                        "max_width": available,
                        "box": box.as_dict() if box is not None else None,
                        "comb": comb,
                        # Kept so the writer can re-check proximity. The
                        # detector has several placement rules and each has
                        # been wrong at least once; the writer enforcing one
                        # invariant over all of them is worth more than trying
                        # to make every rule individually infallible.
                        "label_y0": rect.y0,
                        "label_y1": rect.y1,
                        # Prefer a longer alias (more specific) and more room.
                        # A label that *is* the line beats one buried inside a
                        # heading: on the KCC form "Amount of loan required"
                        # appears in a section heading and again as the field
                        # itself, and only the second has a box beside it.
                        # Exactness first, then how specific the alias is,
                        # then the earlier page, and only then the room
                        # available. Room came too high: "Session" appears in
                        # the table on page 1 and again on the annexure page,
                        # and the annexure had more space beside it, so the
                        # value was written on the wrong page entirely.
                        "_score": (_normalise_token(context)
                                   == _normalise_token(alias),
                                   len(alias), -page_num, available),
                    }
                    if name not in best or candidate["_score"] > best[name]["_score"]:
                        best[name] = candidate
                    placed = True
                # Stop once this field's label has been located on the page,
                # placed or not. Falling through to a looser alias writes a
                # value across the wrong words — on the KCC form "Amount of
                # loan required" appears in a section heading and again as the
                # field, and only the second has a box; letting a later alias
                # match the heading put the amount in the applicant's name box.
                # The alias list is ordered so the field's primary label comes
                # first (father before the combined father/husband label), so
                # the first genuine match is the right one.
                if placed or found_here:
                    break

    # Values recorded by which printed column they sit under, handled after the
    # ordinary pass so a field with a label of its own always prefers it.
    for page_num in range(len(doc)):
        page = doc[page_num]
        cells = form_geometry.build_cells(page)
        if not cells:
            continue
        words = _page_words(page)
        horizontals, _ = form_geometry.detect_rules(page)
        for name in wanted:
            pk = field_key[name]
            if name in best or pk not in OPTION_GRIDS:
                continue
            spot = _option_column_position(
                page, cells, horizontals, words, pk,
                (field_values or {}).get(pk), form_fields, page_num + 1)
            if spot is not None:
                spot["fieldName"] = name
                best[name] = spot

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
        for raw in _page_text(page).splitlines():
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
    unconfirmed: list[str] = []
    try:
        by_page: dict[int, list[dict]] = {}
        for item in written:
            by_page.setdefault(item["page"] - 1, []).append(item)

        for page_index, items in by_page.items():
            if page_index < 0 or page_index >= len(doc):
                continue
            page = doc[page_index]
            page_text = _page_text(page)
            cells = form_geometry.build_cells(page)

            # A page with no text of its own is re-read by OCR, and OCR reads
            # our own overlay back imperfectly — "2.5" comes back as "25". So
            # on such a page the text checks are done on normalised text, and
            # a value that still cannot be found is reported as unconfirmed
            # rather than missing. The geometric checks below are unaffected:
            # they use the coordinates the value was written at.
            native_text = len(page.get_text().strip()) >= MIN_TEXT_LAYER_CHARS
            normalised_page = _normalise_token(page_text)

            own_text = [ln for it in items for ln in it.get("lines", [it["text"]])]
            own_normalised = [_normalise_token(ln) for ln in own_text]

            for item in items:
                # Line by line, because a value wrapped inside a tall box is
                # written as two separate lines and the joined string is on the
                # page nowhere. Every line must be found, so a dropped one is
                # still caught.
                item_lines = item.get("lines") or [item["text"]]
                present = all(ln in page_text for ln in item_lines)
                # A comb writes one character per square, each its own drawing
                # operation, so the text layer reads the value back as
                # "9 8 1 2 3 4 5 6 7 8" — correct on the page, absent from a
                # substring search. Normalising strips the gaps the boxes put
                # there. Without this every comb field on a form was reported
                # missing from a page it is plainly written on.
                if not present and (item.get("comb_boxes") or not native_text):
                    present = all(_normalise_token(ln) in normalised_page
                                  for ln in item_lines)
                if not present:
                    (missing if native_text else unconfirmed).append(
                        item["profileKey"])

                right = item["x"] + item["width"]

                # Checked against the box the value was placed into, when one
                # was recorded. Re-deriving it here found a different, tighter
                # cell than placement used and reported four perfectly
                # well-placed values as spilling — a check that cries wolf is
                # one an operator learns to ignore.
                box = item.get("box")
                limit = box["x1"] if box else None
                if limit is None:
                    cell = form_geometry.cell_containing(
                        cells, item["x"] + 1, item["y"] - item["font_size"] / 2)
                    limit = cell.x1 if cell is not None else None
                if limit is not None and right > limit + 1:
                    problems.append({
                        "kind": "crossed_cell_border",
                        "profileKey": item["profileKey"],
                        "page": page_index + 1,
                        "detail": (f"value extends {right - limit:.0f}pt past "
                                   f"the printed cell border"),
                    })

                # The symptom a clerk actually sees: a value sitting on top of
                # the form's own printing.
                #
                # Only on a page that has its own text. On a scan the verifier
                # must re-OCR the filled page, and OCR merges our ink with the
                # print beneath it — "Punjab N" over a dotted leader comes back
                # as "BanRutiab.N", which matches neither side and looks like a
                # collision that is not there. The geometric checks above stay
                # valid on such pages because they use recorded coordinates.
                if not native_text:
                    continue
                # `word` rather than `text`: the outer check reads the whole
                # page's text, and rebinding that name here made every field
                # after the first compare itself against a single word.
                for wx0, wy0, wx1, wy1, word, *_ in _page_words(page):
                    if form_geometry._is_scan_noise(word):
                        continue
                    # The file is re-opened after writing, so its text layer
                    # now contains our own values. A word that is part of
                    # anything this run wrote is not "printed text".
                    if any(word in line for line in own_text):
                        continue
                    if not native_text:
                        # OCR of our own overlay comes back altered, so an
                        # exact comparison would report every value we wrote as
                        # printed text it collides with.
                        norm = _normalise_token(word)
                        if norm and any(norm in own for own in own_normalised):
                            continue
                    printed = {"x": wx0, "y": wy1, "width": wx1 - wx0,
                               "font_size": max(wy1 - wy0, 6)}
                    if _collides(item, printed):
                        problems.append({
                            "kind": "overlaps_printed_text",
                            "profileKey": item["profileKey"],
                            "page": page_index + 1,
                            "detail": f"value sits on top of the printed word "
                                      f"{word!r}",
                        })
                        break

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
        # Written, placed correctly, but not findable when the page was read
        # back — which on a scan means the OCR could not read our own ink, not
        # that the value is absent. Reported separately so a real omission is
        # never hidden inside it.
        "unconfirmed": unconfirmed,
        "textCheckReliable": not unconfirmed,
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
    # Every return from here carries `written` and `unplaced`, success or not.
    # The caller renders both: what went onto the page, and what the citizen
    # must still write by hand. A failure with neither is the one outcome that
    # helps nobody — it hands back a blank form and no explanation.
    def _gave_up(error: str, **extra) -> dict:
        return {
            "success": False,
            "error": error,
            "method": "none",
            "written": [],
            "unplaced": _unplaced_report([], field_values, form_fields),
            **extra,
        }

    if not _HAS_FITZ:
        return _gave_up("PyMuPDF not available")

    if not os.path.exists(source_pdf_path):
        return _gave_up("Source PDF not found")

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

    # Neither strategy worked. The overlay's own report is the better one when
    # it got far enough to build it — it knows which fields it tried and why
    # each failed — so it is preferred over the blanket list.
    return _gave_up(
        "Could not fill PDF — no AcroForm fields and no overlay positions "
        "detected. Falling back to generated form.",
        acroform_result=acro_result,
        overlay_result=overlay_result,
        unplaced=(overlay_result.get("unplaced")
                  or _unplaced_report([], field_values, form_fields)),
    )
