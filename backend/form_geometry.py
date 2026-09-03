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


def _longest_run(mask) -> int:
    """Length of the longest unbroken stretch of True in a 1-D boolean array."""
    import numpy as np

    if not mask.any():
        return 0
    # Boundaries of each True stretch, found by differencing the padded mask.
    padded = np.concatenate(([False], mask, [False]))
    edges = np.flatnonzero(padded[1:] != padded[:-1])
    return int((edges[1::2] - edges[::2]).max())


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
        band = widened[row_top:row_bottom, :]
        needed = max(int(band.shape[0] * MIN_VERTICAL_RUN_FRACTION), 6)
        for j in range(band.shape[1]):
            if _longest_run(band[:, j]) >= needed:
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


def cell_below(cells: list[Cell], cell: Cell, tolerance: float = 3.0) -> Cell | None:
    """The cell directly beneath this one in the same column.

    A column-header row — "Name of the College/School | Class | Session |
    Admission No." — has no room beside its headings and a blank row under
    them. That blank row is where a person writes, and finding it is the
    difference between a value crammed illegibly beside a heading and one
    sitting in its own box.
    """
    below = [
        c for c in cells
        if abs(c.y0 - cell.y1) <= tolerance
        and min(c.x1, cell.x1) - max(c.x0, cell.x0) > cell.width * 0.5
    ]
    if not below:
        return None
    # The one that lines up best with this column.
    return max(below, key=lambda c: min(c.x1, cell.x1) - max(c.x0, cell.x0))


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
    region = Cell(header.x0, below[0], header.x1, below[1])
    if region.height < MIN_DATA_CELL_HEIGHT or region.width < MIN_DATA_CELL_WIDTH:
        return None
    return region if is_blank(region, words) else None


def header_data_cell(cells: list[Cell], label_rect, words,
                     max_depth: int = 2, horizontals=None) -> Cell | None:
    """The blank cell a column heading writes into, if this label is one.

    Walks down at most `max_depth` rows. One step finds the ordinary case —
    "Name of the College/School" over a blank row. Two are needed where a
    heading has a sub-heading: "Medal Won" sits above "Gold | Silver | Bronze |
    Participation", and the writable space is below both. Any deeper and the
    walk would start dropping values into unrelated parts of the table.
    """
    header = cell_containing(cells, (label_rect.x0 + label_rect.x1) / 2,
                             (label_rect.y0 + label_rect.y1) / 2)
    if header is None:
        return None

    current = header
    for _ in range(max_depth):
        target = cell_below(cells, current)
        if target is None:
            return _synthesised_below(header, horizontals, words)
        if (is_blank(target, words)
                and target.width >= MIN_DATA_CELL_WIDTH
                and target.height >= MIN_DATA_CELL_HEIGHT):
            return target
        current = target

    return _synthesised_below(header, horizontals, words)


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
