"""Reading the ruled grid off a scanned government form.

A printed Indian government form is a table. The value for "District" belongs
inside one specific cell, and a value that runs past that cell's border lands
on top of the next field — which on a scholarship form means the applicant's
college name printed across the Class, Session and Admission No. columns.

Knowing where the cell borders are is therefore the difference between a form
a clerk can read and one they will hand back. The trouble is that these forms
are scans: the borders are dark pixels, not vector lines, so
``page.get_drawings()`` returns nothing at all. This module recovers them from
the rendered image.

The method is deliberately simple and has no OpenCV dependency:

1. Render the page greyscale at a fixed scale.
2. Threshold to ink/no-ink.
3. A row of pixels that is mostly ink across a long run is a horizontal rule;
   the same down a column is a vertical rule.
4. Merge adjacent runs into single lines, then take every pair of neighbouring
   rules as a candidate cell.

It degrades honestly. A form with no detectable grid — a plain typed letter,
or a scan too poor to threshold — yields no cells, and the caller falls back to
bounding by the next printed word. That is worse but not wrong, and it is
reported rather than assumed.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Render scale for line detection. Higher finds fainter rules but costs time
# and memory; 2x is enough for a 150-300 dpi scan, which is what departments
# publish.
RENDER_SCALE = 2.0

# A pixel darker than this counts as ink on a 0-255 greyscale page. Scans carry
# grey speckle and JPEG ringing, so the threshold sits well below mid-grey.
INK_THRESHOLD = 160

# A rule must span this fraction of the page's width (or height) to count. Low
# enough to catch a single table column's divider, high enough to ignore the
# underline of a word.
MIN_RULE_FRACTION = 0.08

# Slight skew is universal in scans: a "vertical" rule drifts a pixel or two
# across its height. Detection is widened by this many pixels so a drifting
# line is still found in one column.
SKEW_TOLERANCE_PX = 2

# A row must be at least this many rendered pixels tall to be searched for
# column dividers. Below it, the "row" is the gap between a rule and its own
# smeared edge.
MIN_ROW_PIXELS = 10

# Within a row, a column divider must run this fraction of the row's height.
# Not 1.0: a scan loses the last pixel or two at a join.
MIN_VERTICAL_RUN_FRACTION = 0.72

# Cells thinner than this in points are dividers or artefacts, not cells.
MIN_CELL_POINTS = 8.0

# A blank cell under a column heading must be at least this big to be worth
# writing in. Smaller ones are the sliver between a rule and its own smear.
MIN_DATA_CELL_WIDTH = 26.0
MIN_DATA_CELL_HEIGHT = 9.0

# How far below a heading's cell its data row may begin. A printed table puts
# them flush; anything more means a row was skipped.
ADJACENT_ROW_TOLERANCE = 4.0

# How far to the right of a label its box may begin before it is somebody
# else's box rather than a wide gap after the colon.
MAX_LABEL_TO_BOX_GAP = 40.0

# How far the next cell may start from the end of the label's own cell before
# it is a different part of the form rather than this field's box.
ADJACENT_CELL_TOLERANCE = 4.0


@dataclass(frozen=True)
class Cell:
    """One rectangle of the printed grid, in PDF points."""
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    def contains(self, x: float, y: float) -> bool:
        return self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1

    def as_dict(self) -> dict:
        return {"x0": round(self.x0, 1), "y0": round(self.y0, 1),
                "x1": round(self.x1, 1), "y1": round(self.y1, 1)}


def _normalise_token(token: str) -> str:
    """Lower-case alphanumerics only — the same reduction the matcher uses."""
    return re.sub(r"[^0-9a-z\u0900-\u097f]", "", str(token).lower())


def _longest_run(mask) -> int:
    """Length of the longest unbroken stretch of True in a 1-D boolean array."""
    import numpy as np

    if not mask.any():
        return 0
    # Boundaries of each True stretch, found by differencing the padded mask.
    padded = np.concatenate(([False], mask, [False]))
    edges = np.flatnonzero(padded[1:] != padded[:-1])
    return int((edges[1::2] - edges[::2]).max())


def _spans_full_height(mask, tolerance: int = 2) -> bool:
    """True when an ink run reaches both ends of the band.

    A printed column divider is drawn from one rule to the next, so it touches
    both. A capital letter in an 11-point row occupies about three quarters of
    the row's height — enough to pass a fractional test, which is how the
    strokes of "Amount of Loan required" came to be read as four column
    dividers, chopping the row into slivers and hiding the empty box beside it.
    Letters leave a gap above and below; a rule does not.
    """
    import numpy as np

    if mask.size < 3 or not mask[:tolerance + 1].any() or not mask[-(tolerance + 1):].any():
        return False
    # Contiguous from top to bottom, allowing the scan to drop a pixel or two.
    gaps = np.flatnonzero(~mask)
    if gaps.size == 0:
        return True
    runs = _merge_runs([int(g) for g in gaps], gap=1)
    return all(end - start + 1 <= tolerance for start, end in runs)


def _merge_runs(indices: list[int], gap: int = 3) -> list[tuple[int, int]]:
    """Collapse consecutive indices into (start, end) runs.

    A printed rule is two or three pixels thick and a scan smears it further,
    so the raw detection returns several adjacent rows for one line.
    """
    if not indices:
        return []
    runs = []
    start = prev = indices[0]
    for i in indices[1:]:
        if i - prev <= gap:
            prev = i
            continue
        runs.append((start, prev))
        start = prev = i
    runs.append((start, prev))
    return runs


def _bridge_segments(segments, x_gap: float = 2.0, max_gap: float = 60.0):
    """Rejoin a printed divider the scan lost in the middle.

    A ruled line does not stop for one row and start again below it. Where the
    same x carries a segment above a gap and another below it, the gap is ink
    the threshold missed — faint print, a fold, a compression artefact — and
    bridging it recovers the cell.

    Only ever between two segments at the same x, so a divider that genuinely
    ends — the Class / Session columns, which exist for two rows and no more —
    is never extended into rows it does not belong to.

    Without this the Address row had no detected border on either side, formed
    no cell, and the state and PIN code stayed unfillable on a box with three
    lines of room in it.
    """
    if not segments:
        return []
    by_x: dict[float, list[list[float]]] = {}
    for x, y0, y1 in sorted(segments):
        for key in by_x:
            if abs(key - x) <= x_gap:
                by_x[key].append([y0, y1])
                break
        else:
            by_x[x] = [[y0, y1]]

    out: list[tuple[float, float, float]] = []
    for x, spans in by_x.items():
        spans.sort()
        merged = [spans[0]]
        for y0, y1 in spans[1:]:
            if y0 - merged[-1][1] <= max_gap:
                merged[-1][1] = max(merged[-1][1], y1)
            else:
                merged.append([y0, y1])
        out.extend((x, a, b) for a, b in merged)
    return out


def _merge_segments(segments, x_gap: float = 2.0, y_gap: float = 3.0):
    """Collapse the raw per-pixel hits into one segment per printed divider.

    Merged only where segments are close in x *and* touch in y. Merging on x
    alone would join the Class divider in row 13 to an unrelated divider forty
    rows below, producing one tall segment that appears to divide every row
    between them.
    """
    if not segments:
        return []
    merged: list[list[float]] = []
    for x, y0, y1 in sorted(segments):
        for existing in merged:
            if (abs(x - existing[0]) <= x_gap
                    and y0 <= existing[2] + y_gap
                    and y1 >= existing[1] - y_gap):
                existing[1] = min(existing[1], y0)
                existing[2] = max(existing[2], y1)
                break
        else:
            merged.append([x, y0, y1])
    return [tuple(m) for m in merged]


def detect_rules(page, scale: float = RENDER_SCALE):
    """Find the rules on a page, in PDF points.

    Returns (horizontal_y, vertical_segments) where each vertical segment is
    (x, y_top, y_bottom). Empty lists mean no grid was found, which is a
    legitimate answer for an unruled document.
    """
    try:
        import numpy as np
    except ImportError:
        logger.info("numpy not installed — grid detection unavailable")
        return [], []

    try:
        import pymupdf
    except ImportError:  # pragma: no cover - exercised only without PyMuPDF
        try:
            import fitz as pymupdf  # noqa: F401
        except ImportError:
            return [], []

    try:
        matrix = pymupdf.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=matrix, colorspace=pymupdf.csGRAY, alpha=False)
    except Exception:  # noqa: BLE001 — a page that will not render has no grid
        logger.warning("Could not rasterise a page for grid detection")
        return [], []

    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    ink = img < INK_THRESHOLD

    # Tolerate skew by smearing ink sideways/downwards a couple of pixels, so a
    # rule that drifts across a column is still contiguous within one.
    if SKEW_TOLERANCE_PX:
        widened = ink.copy()
        for shift in range(1, SKEW_TOLERANCE_PX + 1):
            widened[:, shift:] |= ink[:, :-shift]
            widened[shift:, :] |= ink[:-shift, :]
    else:
        widened = ink

    h_min = max(int(pix.width * MIN_RULE_FRACTION), 20)

    # A rule is a long *contiguous* run of ink, not merely a lot of ink. A line
    # of printed text has plenty of ink and no run; scoring on totals made 55
    # rules out of a form that has about a dozen.
    h_rows = [i for i in range(widened.shape[0])
              if _longest_run(widened[i]) >= h_min]
    horizontal_px = [(a + b) / 2 for a, b in _merge_runs(h_rows)]

    # Verticals are looked for *inside each row*, between one horizontal rule
    # and the next, rather than down the page or in fixed bands.
    #
    # Both earlier attempts failed on the same form. Down the whole page, scan
    # skew walks a "vertical" line several pixels sideways and no single column
    # of pixels holds it. In fixed 12%-of-page bands, a divider that exists in
    # only one 25-point row — the Class / Session / Admission No. columns —
    # never fills enough of a 92-point band to register, so the row came back
    # as one undivided cell and a value written in it ran across three columns.
    #
    # Rows are short, so skew inside one is negligible, and a divider that
    # exists for exactly one row is found exactly where it is.
    segments: list[tuple[float, float, float]] = []
    for top, bottom in zip(horizontal_px, horizontal_px[1:]):
        row_top, row_bottom = int(top) + 1, int(bottom)
        if row_bottom - row_top < MIN_ROW_PIXELS:
            continue
        # Raw ink, not the skew-widened copy. Widening ORs each pixel two
        # columns sideways, which turns the stroke of a letter into a
        # full-height column — that is how "Amount of Loan required" came to be
        # read as four column dividers. Inside a single row the skew is under a
        # pixel anyway, so there is nothing to compensate for.
        band = ink[row_top:row_bottom, :]
        needed = max(int(band.shape[0] * MIN_VERTICAL_RUN_FRACTION), 6)
        for j in range(band.shape[1]):
            column = band[:, j]
            if _longest_run(column) >= needed and _spans_full_height(column):
                segments.append((j / scale, row_top / scale, row_bottom / scale))

    horizontals = [y / scale for y in horizontal_px]
    return horizontals, _bridge_segments(_merge_segments(segments))


def build_cells(page, scale: float = RENDER_SCALE) -> list[Cell]:
    """Every cell of the printed grid, as rectangles in PDF points.

    A vertical rule bounds a row only where it is actually printed. On this
    form the Class/Session/Admission dividers exist on two rows; treating them
    as page-wide boundaries shrank unrelated cells to half their real width.
    """
    horizontals, segments = detect_rules(page, scale)
    if len(horizontals) < 2 or len(segments) < 2:
        return []

    cells: list[Cell] = []
    for top, bottom in zip(horizontals, horizontals[1:]):
        if bottom - top < MIN_CELL_POINTS:
            continue
        # Only rules that run through most of this row's height divide it.
        span = bottom - top
        xs = sorted(
            x for x, y0, y1 in segments
            if min(y1, bottom) - max(y0, top) >= span * 0.6
        )
        for left, right in zip(xs, xs[1:]):
            if right - left < MIN_CELL_POINTS:
                continue
            cells.append(Cell(left, top, right, bottom))
    return cells


def cell_containing(cells: list[Cell], x: float, y: float) -> Cell | None:
    """The smallest cell that contains this point.

    Smallest, because adjacent-pair detection produces overlapping candidates
    where rules are close together, and the tightest one is the real cell.
    """
    hits = [c for c in cells if c.contains(x, y)]
    if not hits:
        return None
    return min(hits, key=lambda c: c.width * c.height)


def _is_scan_noise(token: str) -> bool:
    """True for the specks an OCR layer reports as words.

    A real hint on a form ("(Enclose Certificate)") must bound a value. A
    three-character smear of punctuation must not.
    """
    stripped = (token or "").strip()
    if not stripped:
        return True
    letters = sum(c.isalnum() for c in stripped)
    if letters == 0:
        return True
    # Mostly punctuation: "--ll." is a speck between two rules, and bounding a
    # value against it left three points of writing room beside a perfectly
    # good IFSC label. Length is not the test — ":,.!F-'" is seven characters
    # of nothing — so the ratio decides, with a looser bar for short tokens
    # where one stray mark is proportionally larger.
    # An initialism is punctuation-heavy and perfectly real: "B.A.", "M.Sc.".
    if re.fullmatch(r"(?:[A-Za-z]\.){2,}", stripped):
        return False

    punctuation = (len(stripped) - letters) / len(stripped)
    if punctuation >= 0.6:
        return True
    if len(stripped) <= 6 and punctuation >= 0.4:
        return True
    return len(stripped) <= 4 and letters <= 1


def cell_below(cells: list[Cell], cell: Cell, tolerance: float = 3.0,
               prefer=None) -> Cell | None:
    """The cell directly beneath this one in the same column.

    A column-header row — "Name of the College/School | Class | Session |
    Admission No." — has no room beside its headings and a blank row under
    them. That blank row is where a person writes, and finding it is the
    difference between a value crammed illegibly beside a heading and one
    sitting in its own box.
    """
    # A candidate must sit under this cell — inside its span — and, when a
    # label is given, actually overlap it. Requiring half the *header's* width
    # was too coarse: "Session | Admission No." share one printed header box,
    # so the session's own column below it covers only 39% of that box and was
    # filtered out before the preference could choose it.
    target = prefer if prefer is not None else cell
    below = [
        c for c in cells
        if abs(c.y0 - cell.y1) <= tolerance
        and c.x0 >= cell.x0 - tolerance and c.x1 <= cell.x1 + tolerance
        and min(c.x1, target.x1) - max(c.x0, target.x0) > 0
    ]
    if not below:
        return None
    # Lined up against `prefer` — the label itself — when one is given.
    return max(below,
               key=lambda c: min(c.x1, target.x1) - max(c.x0, target.x0))


def _is_content(token: str) -> bool:
    """True when a token is something a person wrote or printed.

    Stricter than :func:`_is_scan_noise`, and deliberately so. Deciding whether
    a cell is *blank* is a different question from deciding whether a token may
    bound a value: an empty data cell on this scan reads as
    ``[":,.!F-'", '..']``, and one stray letter inside seven characters of
    punctuation is a speck, not content. Treating it as content hid every
    writable box on the table.
    """
    stripped = (token or "").strip()
    if not stripped:
        return False
    alnum = sum(c.isalnum() for c in stripped)
    if alnum >= 2:
        return True
    # A lone character counts only if that is all it is — "1" or "A" in a grid.
    return alnum == 1 and stripped.isalnum()


def is_blank(cell: Cell, words, padding: float = 1.0) -> bool:
    """True when a cell holds nothing a person would call content."""
    for wx0, wy0, wx1, wy1, text, *_ in words:
        if not _is_content(text):
            continue
        if (cell.x0 - padding <= (wx0 + wx1) / 2 <= cell.x1 + padding
                and cell.y0 - padding <= (wy0 + wy1) / 2 <= cell.y1 + padding):
            return False
    return True


def _synthesised_below(header: Cell, horizontals, words) -> Cell | None:
    """A writable region under a heading whose box has no drawn left border.

    Real scans lose rules. The tournament box on this form has a top, a right
    and a bottom but its left border never crosses the ink threshold, so no
    cell forms and a heading with obvious empty space beneath it looked like a
    heading with nowhere to write.

    Bounded by the two horizontal rules under the heading and by the heading's
    own column, so the region can never be wider than the column it belongs to
    — a missing border loosens the evidence, it must not loosen the bounds.
    """
    below = sorted(y for y in (horizontals or []) if y > header.y1 + 1)
    if len(below) < 2:
        return None
    # The region must begin where the heading's own cell ends. Taking the next
    # two rules regardless let it skip a whole row — on the Kisan Credit Card
    # form, past the "Amount of Loan required" row and into "Name of the
    # Applicant", where writing a loan amount is a false statement on a signed
    # declaration.
    # A row may be skipped only if the strip being skipped is itself empty in
    # this column. The tournament box on the Haryana form sits below a
    # Gold/Silver/Bronze sub-heading that occupies other columns and leaves
    # this one clear, so skipping is right there. On the Kisan Credit Card form
    # the strip carries the "Amount of Loan required" label itself, so skipping
    # it would put the value in the next field's box — a false statement on a
    # signed declaration.
    # The strip between the heading and the first rule below it must be clear
    # too, or the region begins past something already printed.
    if (below[0] - header.y1 > ADJACENT_ROW_TOLERANCE
            and not is_blank(Cell(header.x0, header.y1, header.x1, below[0]),
                             words)):
        return None

    start = 0
    while (start + 1 < len(below)
           and not is_blank(Cell(header.x0, below[start], header.x1,
                                 below[start + 1]), words)):
        start += 1
    if start + 1 >= len(below):
        return None
    region = Cell(header.x0, below[start], header.x1, below[start + 1])
    if region.height < MIN_DATA_CELL_HEIGHT or region.width < MIN_DATA_CELL_WIDTH:
        return None
    return region if is_blank(region, words) else None


def row_is_blank(cells: list[Cell], row_top: float, row_bottom: float,
                 words, tolerance: float = 2.0) -> bool:
    """True when every cell of a row is empty.

    This is what separates a column-header row from an ordinary label. Under
    "Name of the College/School | Class | Session | Admission No." the whole
    next row is empty — it is the data row for those headings. Under "Amount of
    Loan required" the next row says "Name of the Applicant", which is a
    different field in a different section, and writing the loan amount there
    put a wrong number on a signed declaration.

    Checking only the column under the heading was not enough: that one cell is
    empty in both cases.
    """
    row = [c for c in cells
           if abs(c.y0 - row_top) <= tolerance and abs(c.y1 - row_bottom) <= tolerance]
    if not row:
        return False
    return all(is_blank(c, words) for c in row)


# ── Comb fields: one character to a box ──────────────────────────────────
#
# A great many Indian government forms record a number as a row of small
# squares — twelve for an Aadhaar, ten for a mobile, sixteen for an account.
# Writing "39281746503921" as one string across them produces a form a clerk
# will reject: the digits do not line up with the boxes, and a data-entry
# operator keying from the squares reads nonsense.
#
# A comb is recognised by shape rather than by any label: a run of adjacent
# cells on one row, all blank, all about the same width, and narrow.

# A comb box is at most this wide. Wider and it is an ordinary cell.
#
# Thirty points was too tight. The Daman & Diu form prints its date of birth as
# eight squares of thirty-three points each, unmistakable to the eye and
# rejected here, so the field went unplaced on a form that draws a box per
# digit. What makes a comb recognisable is not smallness but *repetition* —
# many adjacent boxes of the same width — and that is already tested for. The
# cap is now backed by the shape test below rather than doing the work alone.
MAX_COMB_BOX_WIDTH = 42.0

# And a comb box is roughly square, or taller than it is wide. This is what
# separates eight date squares from a row of narrow table columns: a column is
# a slot for a word and is drawn much wider than the line is tall, while a box
# meant for one character is not. Loosening the width cap without this would
# have turned every narrow table into a comb.
MAX_COMB_ASPECT = 1.8

# Box widths within a comb vary by no more than this fraction of the median.
# A printed comb is drawn by repetition and is very regular; a row of ordinary
# cells that happen to be narrow is not.
COMB_WIDTH_TOLERANCE = 0.28

# Fewer boxes than this is not a comb — two or three narrow cells side by side
# happen by accident all over a form.
MIN_COMB_BOXES = 4

# Boxes must sit within this many points of each other to be one comb.
MAX_COMB_BOX_GAP = 4.0


def find_combs(cells: list[Cell], words, min_boxes: int = MIN_COMB_BOXES
               ) -> list[list[Cell]]:
    """Every run of small equal boxes on the page, left to right.

    Returned as lists of cells so the caller can write one character per box.
    """
    by_row: dict[tuple, list[Cell]] = {}
    for cell in cells:
        if cell.width > MAX_COMB_BOX_WIDTH or cell.width < 4:
            continue
        if cell.height <= 0 or cell.width / cell.height > MAX_COMB_ASPECT:
            continue
        if not is_blank(cell, words):
            continue
        by_row.setdefault((round(cell.y0, 1), round(cell.y1, 1)), []).append(cell)

    combs: list[list[Cell]] = []
    for row in by_row.values():
        row.sort(key=lambda c: c.x0)
        run: list[Cell] = []
        for cell in row:
            if run and cell.x0 - run[-1].x1 > MAX_COMB_BOX_GAP:
                if len(run) >= min_boxes:
                    combs.extend(_split_uneven(run, min_boxes))
                run = []
            run.append(cell)
        if len(run) >= min_boxes:
            combs.extend(_split_uneven(run, min_boxes))
    return combs


def _split_uneven(run: list[Cell], min_boxes: int) -> list[list[Cell]]:
    """Break a run wherever the box width changes, and keep the long parts.

    Two combs printed side by side — a date as DD MM YYYY, say — are adjacent
    but differently grouped, and treating them as one long comb would spread a
    value across both.
    """
    widths = sorted(c.width for c in run)
    median = widths[len(widths) // 2]
    out, current = [], []
    for cell in run:
        if abs(cell.width - median) <= median * COMB_WIDTH_TOLERANCE:
            current.append(cell)
            continue
        if len(current) >= min_boxes:
            out.append(current)
        current = []
    if len(current) >= min_boxes:
        out.append(current)
    return out


def comb_for(cells: list[Cell], label_rect, words,
             max_drop: float = 30.0) -> list[Cell] | None:
    """The comb this label writes into, if there is one.

    Looked for on the label's own row first, then just below it — the two
    places a form puts one. Bounded by `max_drop` so a comb further down the
    page, belonging to another field, is never claimed.
    """
    combs = find_combs(cells, words)
    if not combs:
        return None

    centre_y = (label_rect.y0 + label_rect.y1) / 2
    same_row = [c for c in combs
                if c[0].y0 - 2 <= centre_y <= c[0].y1 + 2
                and c[0].x0 >= label_rect.x1 - 4]
    if same_row:
        return min(same_row, key=lambda c: c[0].x0)

    below = [c for c in combs
             if 0 <= c[0].y0 - label_rect.y1 <= max_drop
             and c[-1].x1 >= label_rect.x0
             and c[0].x0 <= label_rect.x1 + MAX_LABEL_TO_BOX_GAP]
    if below:
        return min(below, key=lambda c: (c[0].y0, c[0].x0))
    return None


def blank_cell_right_of(cells: list[Cell], label_rect, words,
                        min_width: float = MIN_DATA_CELL_WIDTH) -> Cell | None:
    """The empty cell that comes straight after the label's own cell.

    This is the ordinary shape of a form: a label in one cell, its box in the
    next. Finding it settles the question that "beside or below?" otherwise
    leaves open — "Amount of Loan required" has a wide empty box beside it and
    a blank-looking cell beneath it in the *next section*, and only the first
    is the field's own.

    Two things are measured from the label's **cell**, not from its text. A
    short label in a wide cell — "Full Name" in 160 points — leaves the box a
    long way from the words, so measuring from the text missed it entirely.
    And the box must share the cell's top and bottom: the photograph panel on
    the Haryana form is blank, starts right where the "Game/Sport" cell ends,
    and spans three rows, which is exactly what gives it away as something
    else.
    """
    centre_y = (label_rect.y0 + label_rect.y1) / 2
    own = cell_containing(cells, (label_rect.x0 + label_rect.x1) / 2, centre_y)
    if own is None:
        return None

    candidates = [
        c for c in cells
        if abs(c.y0 - own.y0) <= 2 and abs(c.y1 - own.y1) <= 2
        and abs(c.x0 - own.x1) <= ADJACENT_CELL_TOLERANCE
        and c.width >= min_width
        and is_blank(c, words)
    ]
    return min(candidates, key=lambda c: c.x0) if candidates else None


def option_cell_right_of(cells: list[Cell], label_rect, words,
                         options: list[str]) -> tuple[Cell, float] | None:
    """An adjacent cell whose only content is this field's own choices.

    "Yes/No" printed in the cell beside a question is not an empty box and not
    a label — it is the answer cell, with the choices offered. Writing the
    answer in the space left over is what a person does, and treating the cell
    as occupied left every such question blank.

    Returns the cell and the x to start writing at, just past the printed
    choices.
    """
    if not options:
        return None
    wanted = {_normalise_token(o) for o in options if o}
    centre_y = (label_rect.y0 + label_rect.y1) / 2
    own = cell_containing(cells, (label_rect.x0 + label_rect.x1) / 2, centre_y)
    if own is None:
        return None

    for cell in cells:
        if abs(cell.x0 - own.x1) > ADJACENT_CELL_TOLERANCE:
            continue
        if not (cell.y0 - 2 <= centre_y <= cell.y1 + 2):
            continue
        inside = [w for w in words
                  if cell.x0 - 1 <= (w[0] + w[2]) / 2 <= cell.x1 + 1
                  and cell.y0 - 1 <= (w[1] + w[3]) / 2 <= cell.y1 + 1
                  and not _is_scan_noise(w[4])]
        if not inside:
            continue
        # Every printed word must be one of the offered choices, or part of
        # one — "Yes/No" arrives as a single token on many forms.
        joined = _normalise_token("".join(w[4] for w in inside))
        if not joined or not all(o in joined for o in wanted):
            continue
        right_edge = max(w[2] for w in inside)
        if cell.x1 - right_edge < MIN_DATA_CELL_WIDTH:
            continue
        return cell, right_edge + 4
    return None


def header_data_cell(cells: list[Cell], label_rect, words,
                     max_depth: int = 1, horizontals=None) -> Cell | None:
    """The blank cell a column heading writes into, if this label is one.

    Two conditions, and both are needed. The cell below must be blank — and so
    must every other cell on that row, because a row that carries any label of
    its own belongs to a different field. Dropping a value into the first blank
    cell it found put the loan amount on the "Name of the Applicant" line of
    the Kisan Credit Card form, which is worse than leaving it blank: a wrong
    value on a signed form is a false declaration.
    """
    header = cell_containing(cells, (label_rect.x0 + label_rect.x1) / 2,
                             (label_rect.y0 + label_rect.y1) / 2)
    if header is None:
        return None

    # The label's row must actually look like a row of headings: two or more
    # cells, every one of them carrying text. A row that is one label beside an
    # empty box is an ordinary field, and the blank cell under it belongs to
    # whatever comes next — on the Kisan Credit Card form, to "Name of the
    # Applicant" in the following section. Writing a loan amount there is a
    # false statement on a signed declaration, so coverage gives way to
    # correctness here: the field is reported unplaced instead.
    row = [c for c in cells
           if abs(c.y0 - header.y0) <= 2 and abs(c.y1 - header.y1) <= 2]
    if len(row) < 2 or any(is_blank(c, words) for c in row):
        return None

    current = header
    for _ in range(max_depth):
        target = cell_below(cells, current, prefer=label_rect)
        if target is None:
            return _synthesised_below(header, horizontals, words)
        if (is_blank(target, words)
                and target.width >= MIN_DATA_CELL_WIDTH
                and target.height >= MIN_DATA_CELL_HEIGHT
                and row_is_blank(cells, target.y0, target.y1, words)):
            return target
        current = target

    return _synthesised_below(header, horizontals, words)


def colon_anchor(cells: list[Cell], label_rect, words,
                 max_drop: float = MAX_LABEL_TO_BOX_GAP):
    """The space opened by the colon that ends a label running onto its own line.

    A long label does not always leave room beside itself. The Daman & Diu form
    prints

        a) Name of the College/Institute where Girl student is pursing Diploma,
           P.G. Diploma, Graduation, Post-graduation course.
                                    :-______________________________________

    — three lines of label, and the answer goes on the rule after the ":-",
    which is on none of them. Reading only the label's own row found no space
    at all and reported a field unplaced that the form gives half a line for.

    The colon is the form telling you where the answer starts. Only a colon
    *below* the label counts here: one beside it is already the ordinary case
    and `writable_gaps` handles it. Returns (x0, x1, baseline) or None.
    """
    cell = cell_containing(cells, (label_rect.x0 + label_rect.x1) / 2,
                           (label_rect.y0 + label_rect.y1) / 2)
    if cell is None:
        return None

    best = None
    for w in words:
        text = str(w[4]).strip()
        if not text.endswith(":") and not text.endswith(":-"):
            continue
        wx0, wy0, wx1, wy1 = w[0], w[1], w[2], w[3]
        # Contained by its centre, not its glyph box. A colon's descender
        # reaches 1.2 points past the rule that closes the cell it sits in, and
        # requiring the whole box inside rejected the one marker on the page
        # that mattered.
        if not (cell.x0 <= wx0 and wx1 <= cell.x1
                and cell.y0 - 2 <= (wy0 + wy1) / 2 <= cell.y1 + 2):
            continue
        drop = wy0 - label_rect.y1
        if drop <= 1 or drop > max_drop:
            continue
        if best is None or drop < best[0]:
            best = (drop, w)
    if best is None:
        return None

    _, marker = best
    left = marker[2] + 3
    right = cell.x1 - 3
    # Never over anything else printed on that line.
    centre_y = (marker[1] + marker[3]) / 2
    for w in words:
        if w[0] <= marker[2] or w[0] >= right:
            continue
        if not (marker[1] - 2 <= (w[1] + w[3]) / 2 <= marker[3] + 2):
            continue
        if _is_scan_noise(str(w[4])):
            continue
        right = min(right, w[0] - 3)
    if right - left < MIN_DATA_CELL_WIDTH:
        return None
    return left, right, marker[3] - 1.5


def writable_gaps(cells: list[Cell], label_rect, words, page_width: float,
                  padding: float = 4.0) -> list[tuple[float, float]]:
    """Every run of blank space beside a label, best candidate first.

    Bounded by, in order of authority:

    1. the next field's label on the same row. A colon on an Indian government
       form marks a label, so "8. Mobile No: | Email ID:" is two fields on one
       row and the space past "Email ID:" belongs to the email. Without this
       the mobile number was written on top of the email address.
    2. the right border of the printed cell — the line a clerk sees, and
       crossing it is what "spilling over" means;
    3. the printed words already on the row, so a value never lands on a hint
       like "(Enclose Certificate)";
    4. the page margin.

    Order matters as much as the bounds. The gap immediately after the label
    comes first, because that is where a person writes; the remaining gaps
    follow widest-first. Returning only the widest put "OBC" at the far right
    of the Category row, past "(Enclose copy of SC Certificate)", where no
    clerk would look for it. The caller takes the first gap the value fits.
    """
    centre_y = (label_rect.y0 + label_rect.y1) / 2

    right_limit = page_width - 18
    left_limit = label_rect.x1 + padding
    cell = cell_containing(cells, label_rect.x1 + 1, centre_y)
    if cell is not None:
        right_limit = min(right_limit, cell.x1 - padding / 2)

    band_top, band_bottom = label_rect.y0 - 2, label_rect.y1 + 2
    on_row = [w for w in words
              if band_top <= (w[1] + w[3]) / 2 <= band_bottom]

    for w in sorted(on_row):
        if w[0] > label_rect.x1 + 2 and str(w[4]).rstrip().endswith(":"):
            right_limit = min(right_limit, w[0] - 3)
            break

    occupied = []
    for w in on_row:
        wx0, wy0, wx1, wy1, text = w[0], w[1], w[2], w[3], w[4]
        if _is_scan_noise(text):
            continue
        if wx1 <= left_limit or wx0 >= right_limit:
            continue
        occupied.append((max(wx0, left_limit), min(wx1, right_limit)))

    occupied.sort()
    gaps: list[tuple[float, float]] = []
    cursor = left_limit
    for start, end in occupied:
        if start - cursor > 1:
            gaps.append((cursor, start - 3))
        cursor = max(cursor, end + padding)
    if right_limit - cursor > 1:
        gaps.append((cursor, right_limit))

    if not gaps:
        return []
    first, rest = gaps[0], gaps[1:]
    rest.sort(key=lambda g: g[1] - g[0], reverse=True)
    return [first] + rest


def writable_span(cells: list[Cell], label_rect, words, page_width: float,
                  padding: float = 4.0) -> tuple[float, float]:
    """The single best gap beside a label. Kept for callers that want one."""
    gaps = writable_gaps(cells, label_rect, words, page_width, padding)
    if not gaps:
        start = label_rect.x1 + padding
        return (start, start)
    return max(gaps, key=lambda g: g[1] - g[0])


def describe(page) -> dict:
    """Summary of what was found, for diagnostics and the demo script."""
    horizontals, segments = detect_rules(page)
    cells = build_cells(page)
    return {
        "horizontalRules": len(horizontals),
        "verticalRules": len(segments),
        "cells": len(cells),
        "gridDetected": bool(cells),
    }
