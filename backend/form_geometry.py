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

# Height of each band used for vertical-rule detection, as a fraction of the
# page. Small enough that scan skew inside one band is under a pixel.
VERTICAL_BAND_FRACTION = 0.12

# Within a band, a vertical rule must run this fraction of the band's height.
MIN_VERTICAL_RUN_FRACTION = 0.7

# Cells thinner than this in points are dividers or artefacts, not cells.
MIN_CELL_POINTS = 8.0


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


def _merge_segments(segments, x_gap: float = 2.0):
    """Collapse near-identical vertical segments into one per printed rule."""
    if not segments:
        return []
    merged: list[list[float]] = []
    for x, y0, y1 in sorted(segments):
        if merged and x - merged[-1][0] <= x_gap:
            merged[-1][1] = min(merged[-1][1], y0)
            merged[-1][2] = max(merged[-1][2], y1)
            continue
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

    # Verticals are detected in horizontal bands rather than down the whole
    # page. Every scan is slightly rotated, and over the height of an A4 page
    # even half a degree walks a "vertical" rule several pixels sideways — so
    # no single column of pixels contains the whole line, and the table's outer
    # border went undetected. Inside a band the drift is under a pixel.
    band_px = max(int(pix.height * VERTICAL_BAND_FRACTION), 40)
    v_min = max(int(band_px * MIN_VERTICAL_RUN_FRACTION), 15)
    # Recorded as segments, not bare x positions. The "Class / Session /
    # Admission No." dividers exist on two rows of this form and nowhere else;
    # treating their x as a boundary for the whole page capped the Address cell
    # at 56% of its real width and pushed good values out as unplaceable.
    band_hits: dict[int, list[int]] = {}
    bands: list[tuple[int, int]] = []
    for top in range(0, widened.shape[0], band_px):
        bottom = min(top + band_px, widened.shape[0])
        if bottom - top < v_min:
            continue
        bands.append((top, bottom))
        band = widened[top:bottom, :]
        for j in range(band.shape[1]):
            if _longest_run(band[:, j]) >= v_min:
                band_hits.setdefault(j, []).append(len(bands) - 1)

    segments: list[tuple[float, float, float]] = []
    for j, band_indices in band_hits.items():
        for run_start, run_end in _merge_runs(sorted(band_indices), gap=1):
            y0 = bands[run_start][0] / scale
            y1 = bands[run_end][1] / scale
            segments.append((j / scale, y0, y1))

    horizontals = [((a + b) / 2) / scale for a, b in _merge_runs(h_rows)]
    verticals = _merge_segments(segments)
    return horizontals, verticals


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
            if min(y1, bottom) - max(y0, top) >= span * 0.5
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
    # Mostly punctuation and short: "--ll." is a speck between two rules, and
    # bounding a value against it left three points of writing room beside a
    # perfectly good IFSC label.
    if len(stripped) <= 6 and (len(stripped) - letters) / len(stripped) >= 0.4:
        return True
    return len(stripped) <= 4 and letters <= 1


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
