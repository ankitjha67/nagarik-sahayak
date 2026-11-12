"""Per-form coordinate templates for the official PDFs we fill.

Generic label-matching (pdf_filler.FIELD_ALIASES) tops out around a third of the
fields on a real government form: it cannot place a value whose printed label it
does not recognise, it will not tick a Yes/No box, and it has no way to know that
a field the catalogue lists (gender, address) is simply not on a given form.

A template fixes that for one specific form. Each field is anchored to text the
form actually prints, found at fill time with `page.search_for`, so the template
follows the real layout rather than hard-coded pixels. Three kinds of field:

* text   - write the profile value just past its label.
* tick   - put an X in the Yes/No (or similar) box the profile value selects.
* choose - mark the one printed option (e.g. a pension amount) the profile picks.

The resolver returns explicit `field_positions` for pdf_filler.fill_overlay_pdf,
plus any synthetic "X" values the ticks need. A form with no template is filled
the generic way, exactly as before - templates are purely additive.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _fmt_date(value: str) -> str:
    """dd/mm/yyyy from an ISO or already-formatted date; original on no match."""
    import re
    s = str(value or "").strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    return s


# ---------------------------------------------------------------------------
# Templates. Coordinates are never hard-coded; every field names the text it
# sits next to. `page` is 0-indexed. For text fields the value is written at
# (anchor.x1 + dx, anchor.baseline + dy). `ymax`/`ymin` disambiguate a label
# that appears more than once (e.g. APY prints "Bank Branch" twice - once for
# the applicant, once in the bank-only acknowledgement slip at the foot).
# ---------------------------------------------------------------------------

# Atal Pension Yojana - everything the applicant fills is on page 1.
_APY = {
    "page": 0,
    # Keep placements above the bank-only acknowledgement slip (which starts
    # ~y=649) while still covering the pension row at ~y=453-463.
    "ymax": 480.0,
    "text": [
        # key, anchor label, dx, size, optional overrides
        {"key": "name", "anchor": "Full Name*", "dx": 6, "size": 9},
        {"key": "bank_account_number", "anchor": "Bank A/c Number*", "dx": 6, "size": 9},
        {"key": "bank_name", "anchor": "Bank Name*", "dx": 6, "size": 9},
        {"key": "branch_name", "anchor": "Bank Branch*", "dx": 6, "size": 9, "ymax": 200.0},
        {"key": "date_of_birth", "anchor": "Date of Birth*", "dx": 6, "size": 8,
         "fmt": "date", "ymin": 225.0, "ymax": 246.0},
        # "Age" is a short, common string; pin it to the personal-details line
        # (~y=231) so it never matches a stray "...age..." higher up the page.
        {"key": "age", "anchor": "Age", "dx": 4, "size": 9, "ymin": 225.0, "ymax": 244.0},
        {"key": "mobile_number", "anchor": "Mobile No", "dx": 6, "size": 9},
        {"key": "aadhaar_number", "anchor": "Aadhaar*", "dx": 6, "size": 9},
        {"key": "nominee_name_aps", "anchor": "Nominee’s Name*", "dx": 6, "size": 9},
    ],
    "tick": [
        # key, row label, option->anchor. The X goes in the box printed just
        # before each option word; we place it a little left of the word.
        {"key": "is_income_tax_payer", "row": "Whether  Income Tax Payer",
         "options": {"No": "No", "Yes": "Yes"}, "size": 9, "dx": -14},
    ],
    "choose": [
        # key, row label, and the printed options to mark (value must match one).
        {"key": "pension_amount_chosen", "row": "Pension Amount",
         "options": ["1000", "2000", "3000", "4000", "5000"], "size": 10, "dx": 20},
    ],
}

# Pradhan Mantri Ujjwala Yojana KYC - applicant fields on page 1. The form
# splits the name into First/Middle/Last; we write the whole name in the First
# Name blank (the usual way a single-field name is entered on it). The bank block
# at the foot repeats the holder name.
_UJJWALA = {
    "page": 0,
    "text": [
        {"key": "name", "anchor": "First Name", "dx": 10, "size": 8, "ymax": 154.0},
        {"key": "date_of_birth", "anchor": "Date of Birth", "dx": 8, "size": 7,
         "fmt": "date", "ymax": 145.0},
        {"key": "aadhaar_number", "anchor": "Aadhaar Number", "dx": 10, "size": 9, "ymax": 205.0},
        {"key": "category", "anchor": "Caste", "dx": 10, "size": 9, "ymax": 214.0},
        {"key": "mobile_number", "anchor": "Mobile number", "dx": 8, "size": 8, "ymax": 245.0},
        {"key": "address_line", "anchor": "House/Flat Number", "dx": 8, "size": 8, "ymax": 255.0},
        {"key": "pincode", "anchor": "Pin code", "dx": 8, "size": 9, "ymin": 270.0, "ymax": 290.0},
        {"key": "district", "anchor": "District", "dx": 8, "size": 9, "ymin": 305.0, "ymax": 322.0},
        {"key": "name", "anchor": "Name as per Bank", "dx": 10, "size": 8,
         "ymin": 560.0, "ymax": 578.0},
        {"key": "bank_name", "anchor": "Bank Name", "dx": 10, "size": 9,
         "ymin": 582.0, "ymax": 601.0},
        {"key": "branch_name", "anchor": "Branch Name", "dx": 10, "size": 9,
         "ymin": 598.0, "ymax": 616.0},
        {"key": "bank_account_number", "anchor": "Bank Account", "dx": 10, "size": 9,
         "ymin": 610.0, "ymax": 630.0},
    ],
}

# Sukanya Samriddhi - the India Post POSB account-opening form. The account
# holder is the girl child; the guardian's name sits in the father/husband row.
# Name goes under the "First Name" grid header; Aadhaar and first deposit are on
# page 2.
_SUKANYA = {
    "page": 0,
    "text": [
        {"key": "girl_child_name", "anchor": "First Name", "below": True, "dx": 2,
         "dy": 13, "size": 8, "ymin": 200.0, "ymax": 220.0},
        {"key": "father_husband_name", "anchor": "Full Name of father", "below": True,
         "dx": 2, "dy": 12, "size": 8, "ymax": 285.0},
        # The address rows are a table; data goes in the "First Applicant" column.
        {"key": "address_line", "anchor": "Flat No", "x_abs": 190.0, "size": 8, "ymax": 338.0},
        {"key": "district", "anchor": "City and District", "x_abs": 190.0, "size": 8, "ymax": 380.0},
        {"key": "state", "anchor": "State", "x_abs": 190.0, "size": 8, "ymin": 378.0, "ymax": 393.0},
        {"key": "pincode", "anchor": "Pin Code", "x_abs": 190.0, "size": 9, "ymax": 408.0},
        {"key": "mobile_number", "anchor": "Mobile", "x_abs": 190.0, "size": 9, "ymin": 405.0, "ymax": 422.0},
        # Item 5 is a grid; the date goes in row 1, under the header.
        {"key": "girl_child_dob", "anchor": "Applicant’s Date of Birth", "below": True,
         "dx": 60, "dy": 16, "size": 8, "fmt": "date", "ymax": 465.0},
        # First-deposit amount (item 8, page 1) - anchored to "Rs.(figures)" so it
        # is never confused with the RD "Amount of Monthly Installment" on page 2.
        {"key": "initial_deposit", "anchor": "Rs.(figures)", "dx": 6, "size": 9,
         "ymin": 630.0, "ymax": 700.0},
        # page 2
        {"key": "aadhaar_number", "anchor": "AADHAR NUMBER", "page": 1, "dx": 10,
         "size": 9, "ymax": 45.0},
    ],
}

# Pradhan Mantri Matru Vandana Yojana - national Form 1-A (bilingual). The
# beneficiary name and Aadhaar sit on the ruled line beneath their labels
# (page 1); the address block and contact details are page 2.
_PMMVY = {
    "page": 0,
    "text": [
        {"key": "name", "anchor": "Name of Beneficiary", "below": True, "dx": 2,
         "dy": 24, "size": 9, "ymax": 380.0},
        {"key": "aadhaar_number", "anchor": "Aadhaar Number", "below": True, "dx": 2,
         "dy": 12, "size": 9, "ymax": 412.0},
        # page 2 contact + dates. The address cells carry long bilingual labels
        # with no room for an overlay, so only the clearly-blank fields are filled.
        {"key": "district", "anchor": "District", "page": 1, "dx": 130, "size": 8,
         "ymin": 480.0, "ymax": 498.0},
        {"key": "pincode", "anchor": "PIN CODE", "page": 1, "dx": 90, "size": 9, "ymax": 525.0},
        {"key": "mobile_number", "anchor": "Mobile No", "page": 1, "dx": 90, "size": 9,
         "ymax": 562.0},
        {"key": "lmp_date", "anchor": "Last Menstrual", "page": 1, "dx": 345, "size": 8,
         "fmt": "date", "ymax": 612.0},
    ],
}

TEMPLATES = {
    "Atal Pension Yojana": _APY,
    "Pradhan Mantri Ujjwala Yojana": _UJJWALA,
    "Sukanya Samriddhi Yojana": _SUKANYA,
    "Pradhan Mantri Matru Vandana Yojana": _PMMVY,
}


def has_template(scheme_name: str) -> bool:
    return scheme_name in TEMPLATES


def _search(page, text, ymin=None, ymax=None):
    try:
        rects = page.search_for(text)
    except Exception:
        return []
    out = []
    for r in rects:
        if ymin is not None and r.y0 < ymin:
            continue
        if ymax is not None and r.y1 > ymax:
            continue
        out.append(r)
    return out


def _norm(value) -> str:
    return str(value if value is not None else "").strip()


def positions_for(scheme_name: str, doc, profile: dict):
    """Build (field_positions, extra_values) for a templated form.

    field_positions feeds pdf_filler.fill_overlay_pdf directly. extra_values
    carries the synthetic "X" marks ticks need, merged into field_values by the
    caller. Returns (None, {}) when the scheme has no template.
    """
    tpl = TEMPLATES.get(scheme_name)
    if not tpl:
        return None, {}

    page_idx = tpl.get("page", 0)
    if page_idx >= len(doc):
        return None, {}
    page = doc[page_idx]
    default_ymax = tpl.get("ymax")

    positions = []
    extra_values = {}

    # --- text fields ---
    for spec in tpl.get("text", []):
        val = _norm(profile.get(spec["key"]))
        if not val:
            continue
        pno = spec.get("page", page_idx)
        if pno >= len(doc):
            continue
        tgt = doc[pno]
        rects = _search(tgt, spec["anchor"],
                        spec.get("ymin"), spec.get("ymax") if "ymax" in spec else
                        (default_ymax if pno == page_idx else None))
        if not rects:
            logger.info("%s template: anchor %r not found", scheme_name, spec["anchor"])
            continue
        r = rects[0]
        if spec.get("fmt") == "date":
            val = _fmt_date(val)
        # "below" writes under the label (a grid header, or a field whose blank
        # line sits on the next row); otherwise the value goes to its right.
        if spec.get("below"):
            x = r.x0 + spec.get("dx", 2)
            y = r.y1 + spec.get("dy", 13)
            guard0, guard1 = r.y0, y  # allow the drop to the line below
        else:
            # x_abs puts the value in a fixed column (a ruled table whose data
            # cell is nowhere near the row label); otherwise just past the label.
            x = spec["x_abs"] if "x_abs" in spec else r.x1 + spec.get("dx", 6)
            y = r.y1 + spec.get("dy", -1)
            guard0, guard1 = r.y0, r.y1
        positions.append({
            "profileKey": spec["key"],
            "page": pno + 1,
            "x": x,
            "y": y,
            "font_size": spec.get("size", 9),
            "label_y0": guard0,
            "label_y1": guard1,
        })

    # --- tick (Yes/No style) fields ---
    for spec in tpl.get("tick", []):
        val = _norm(profile.get(spec["key"]))
        if not val:
            continue
        rows = _search(page, spec["row"], ymax=default_ymax)
        if not rows:
            continue
        row = rows[0]
        anchor = spec["options"].get(val) or spec["options"].get(val.title())
        if not anchor:
            continue
        # the option word on the same row as the question
        opts = [o for o in _search(page, anchor)
                if abs(o.y0 - row.y0) < 8 and o.x0 > row.x0]
        if not opts:
            continue
        o = opts[0]
        synth = f"_tick_{spec['key']}"
        extra_values[synth] = "X"
        positions.append({
            "profileKey": synth,
            "page": page_idx + 1,
            "x": o.x0 + spec.get("dx", -11),
            "y": o.y1 + spec.get("dy", -1),
            "font_size": spec.get("size", 10),
            "label_y0": o.y0,
            "label_y1": o.y1,
        })

    # --- choose one printed option (mark it) ---
    for spec in tpl.get("choose", []):
        val = _norm(profile.get(spec["key"]))
        val_digits = "".join(ch for ch in val if ch.isdigit())
        if not val_digits:
            continue
        match = next((o for o in spec["options"] if o == val_digits), None)
        if not match:
            continue
        rows = _search(page, spec["row"], ymax=default_ymax)
        if not rows:
            continue
        row = rows[0]
        opts = [o for o in _search(page, match)
                if abs(o.y0 - row.y0) < 8 and o.x0 > row.x0]
        if not opts:
            continue
        o = opts[0]
        synth = f"_choose_{spec['key']}"
        extra_values[synth] = "X"
        positions.append({
            "profileKey": synth,
            "page": page_idx + 1,
            "x": o.x1 + spec.get("dx", 20),
            "y": o.y1 + spec.get("dy", -1),
            "font_size": spec.get("size", 10),
            "label_y0": o.y0,
            "label_y1": o.y1,
        })

    return positions, extra_values
