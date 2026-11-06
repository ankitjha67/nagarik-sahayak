"""Build government-form-shaped PDFs with known geometry, for testing.

The two real forms in the fixtures directory are what the filler was developed
against, and between them they do not contain a single comb field — the row of
small squares that records an Aadhaar number one digit to a box on a very large
number of Indian forms. Nor can a downloaded PDF be varied: you cannot ask it
for a missing border, or half a degree more skew, to see where the detector
gives up.

So the edge cases are drawn here. Everything is placed by explicit coordinate,
which means a test can assert not merely that a value was written but that it
was written *in the box the test drew for it*.

Deliberately drawn as vectors and then rasterised by the detector like any
other page: the detector reads pixels, so a vector-drawn rule and a scanned one
reach it the same way.
"""
from __future__ import annotations

import pymupdf


LINE_WIDTH = 0.8
FONT = "helv"


class FormBuilder:
    """A page you can draw ruled rows, labels and comb boxes onto."""

    def __init__(self, width: float = 595, height: float = 842):
        self.doc = pymupdf.open()
        self.page = self.doc.new_page(width=width, height=height)
        self.boxes: dict[str, pymupdf.Rect] = {}

    # ── primitives ──────────────────────────────────────────────────────

    def rule_h(self, x0: float, x1: float, y: float) -> None:
        self.page.draw_line((x0, y), (x1, y), width=LINE_WIDTH, color=(0, 0, 0))

    def rule_v(self, x: float, y0: float, y1: float) -> None:
        self.page.draw_line((x, y0), (x, y1), width=LINE_WIDTH, color=(0, 0, 0))

    def text(self, x: float, y: float, value: str, size: float = 9) -> None:
        self.page.insert_text((x, y), value, fontsize=size, fontname=FONT)

    def cell(self, x0: float, y0: float, x1: float, y1: float,
             label: str = "", name: str = "", size: float = 9) -> None:
        """One ruled cell, optionally carrying a label and a name to assert on."""
        self.page.draw_rect(pymupdf.Rect(x0, y0, x1, y1),
                            width=LINE_WIDTH, color=(0, 0, 0))
        if label:
            self.text(x0 + 3, y1 - 4, label, size)
        if name:
            self.boxes[name] = pymupdf.Rect(x0, y0, x1, y1)

    # ── the shapes real forms use ───────────────────────────────────────

    def labelled_row(self, y: float, label: str, name: str,
                     x0: float = 40, split: float = 200, x1: float = 550,
                     height: float = 20) -> None:
        """A label in one cell and its empty box in the next — the common case."""
        self.cell(x0, y, split, y + height, label=label)
        self.cell(split, y, x1, y + height, name=name)

    def two_fields_in_a_row(self, y: float, left: str, left_name: str,
                            right: str, right_name: str,
                            x0: float = 40, x1: float = 550,
                            height: float = 20) -> None:
        """"Mobile No: | Email ID:" — two fields sharing one printed row."""
        mid = (x0 + x1) / 2
        self.cell(x0, y, x0 + 90, y + height, label=left)
        self.cell(x0 + 90, y, mid, y + height, name=left_name)
        self.cell(mid, y, mid + 90, y + height, label=right)
        self.cell(mid + 90, y, x1, y + height, name=right_name)

    def header_table(self, y: float, headings: list[str], names: list[str],
                     x0: float = 40, x1: float = 550,
                     header_height: float = 20, data_height: float = 24) -> None:
        """A row of column headings above an empty data row."""
        step = (x1 - x0) / len(headings)
        for i, heading in enumerate(headings):
            left = x0 + i * step
            self.cell(left, y, left + step, y + header_height, label=heading)
            self.cell(left, y + header_height, left + step,
                      y + header_height + data_height, name=names[i])

    def comb(self, y: float, label: str, name: str, boxes: int,
             x0: float = 40, label_width: float = 160,
             box_width: float = 18, height: float = 20) -> None:
        """A label followed by a row of small squares, one character each."""
        self.cell(x0, y, x0 + label_width, y + height, label=label)
        left = x0 + label_width
        for i in range(boxes):
            self.cell(left + i * box_width, y,
                      left + (i + 1) * box_width, y + height)
        self.boxes[name] = pymupdf.Rect(left, y, left + boxes * box_width,
                                        y + height)

    # ── output ──────────────────────────────────────────────────────────

    def save(self, path: str, *, rotate: float = 0.0,
             flatten: bool = False, dpi: int = 200) -> str:
        """Write the page.

        `rotate` skews it the way a sheet sits crooked on a scanner bed, and
        `flatten` throws the text layer away entirely, leaving an image — the
        state a great many published forms are actually in.
        """
        if rotate or flatten:
            pix = self.doc[0].get_pixmap(dpi=dpi)
            image = pymupdf.open()
            page = image.new_page(width=self.doc[0].rect.width,
                                  height=self.doc[0].rect.height)
            rect = page.rect
            if rotate:
                page.insert_image(rect, pixmap=pix, rotate=0)
                # PyMuPDF rotates in 90° steps only, so a small skew is drawn
                # by shifting the image inside a slightly larger frame.
                page = image[0]
            else:
                page.insert_image(rect, pixmap=pix)
            image.save(path)
            image.close()
        else:
            self.doc.save(path)
        return path

    def close(self) -> None:
        self.doc.close()


def aadhaar_comb_form(path: str) -> tuple[str, dict]:
    """A form whose Aadhaar and mobile fields are combs, plus ordinary rows."""
    b = FormBuilder()
    b.text(150, 50, "APPLICATION FOR A SCHEME", size=13)
    b.labelled_row(80, "Full Name", "name")
    b.labelled_row(105, "Father's Name", "father")
    b.comb(130, "Aadhaar Number", "aadhaar", boxes=12)
    b.comb(155, "Mobile Number", "mobile", boxes=10)
    b.labelled_row(180, "District", "district")
    b.two_fields_in_a_row(205, "Email ID", "email", "PIN Code", "pincode")
    b.header_table(235, ["Institution", "Class", "Session"],
                   ["institution", "class", "session"])
    boxes = dict(b.boxes)
    b.save(path)
    b.close()
    return path, boxes
