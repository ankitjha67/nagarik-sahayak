"""Reading the ruled grid off a scanned form, and writing inside it.

A printed government form is a table, and the border of a cell is the line a
clerk reads by. A value that crosses it lands on the next field — on the
Haryana scholarship form, the applicant's college name printed across the
Class, Session and Admission No. columns.

These forms are scans, so the borders are dark pixels rather than vector
lines and `page.get_drawings()` returns nothing at all. Everything below tests
recovering them from the image.
"""
import pytest

import form_geometry as fg
from form_geometry import Cell


def _rect(x0, y0, x1, y1):
    """A stand-in for a PyMuPDF Rect, which is all writable_gaps needs."""
    class R:
        pass
    r = R()
    r.x0, r.y0, r.x1, r.y1 = x0, y0, x1, y1
    return r


def _word(x0, y0, x1, y1, text):
    """A PyMuPDF `words` tuple: x0, y0, x1, y1, text, block, line, word_no."""
    return (x0, y0, x1, y1, text, 0, 0, 0)


class TestRunDetection:
    def test_longest_run_finds_the_line_not_the_total(self):
        """A row of printed text has plenty of ink and no long run. Scoring on
        totals made 55 rules out of a form that has about a dozen."""
        np = pytest.importorskip("numpy")

        scattered = np.array([True, False] * 30)          # 30 ink, no run
        solid = np.array([False] * 10 + [True] * 20 + [False] * 30)
        assert fg._longest_run(scattered) == 1
        assert fg._longest_run(solid) == 20

    def test_an_empty_row_has_no_run(self):
        np = pytest.importorskip("numpy")
        assert fg._longest_run(np.zeros(50, dtype=bool)) == 0

    def test_adjacent_indices_merge_into_one_rule(self):
        """A printed rule is two or three pixels thick and a scan smears it, so
        one line arrives as several adjacent rows."""
        assert fg._merge_runs([10, 11, 12, 40, 41]) == [(10, 12), (40, 41)]

    def test_distant_indices_stay_separate(self):
        assert fg._merge_runs([10, 60]) == [(10, 10), (60, 60)]


class TestCells:
    CELLS = [
        Cell(20, 100, 250, 120),
        Cell(250, 100, 400, 120),
        Cell(20, 100, 400, 120),     # a merged row spanning both
    ]

    def test_the_tightest_containing_cell_wins(self):
        """Adjacent-pair detection produces overlapping candidates where rules
        are close together; the tightest one is the real cell."""
        cell = fg.cell_containing(self.CELLS, 100, 110)
        assert cell == Cell(20, 100, 250, 120)

    def test_a_point_outside_every_cell_returns_none(self):
        assert fg.cell_containing(self.CELLS, 900, 900) is None

    def test_no_cells_is_a_legitimate_answer(self):
        """An unruled document — a typed letter — has no grid, and the caller
        falls back to bounding by the next printed word."""
        assert fg.cell_containing([], 100, 110) is None


class TestScanNoise:
    @pytest.mark.parametrize("token", ["--ll.", ".", "..", "·", "-", "'"])
    def test_specks_are_ignored(self, token):
        """An OCR layer reports scan specks as words. Bounding a value against
        "--ll." left three points of writing room beside a good IFSC label."""
        assert fg._is_scan_noise(token)

    @pytest.mark.parametrize("token", [
        "No.", "PIN", "Class", "(Enclose", "Certificate)", "Session",
    ])
    def test_real_words_are_not(self, token):
        assert not fg._is_scan_noise(token)


class TestWritableGaps:
    CELLS = [Cell(20, 100, 400, 120)]

    def test_the_cell_border_bounds_the_value(self):
        """Crossing this line is what "spilling over" means."""
        label = _rect(30, 104, 90, 116)
        gaps = fg.writable_gaps(self.CELLS, label, [], page_width=600)
        assert gaps
        assert gaps[0][1] <= 400

    def test_the_next_field_s_label_bounds_the_value(self):
        """"8. Mobile No: | Email ID:" is two fields on one row. Without this
        the mobile number was written on top of the email address."""
        label = _rect(30, 104, 90, 116)
        words = [_word(200, 104, 250, 116, "Email"),
                 _word(252, 104, 280, 116, "ID:")]
        gaps = fg.writable_gaps(self.CELLS, label, words, page_width=600)
        assert gaps[0][1] <= 200

    def test_the_gap_beside_the_label_comes_first(self):
        """Returning only the widest gap put "OBC" at the far right of the
        Category row, past "(Enclose copy of SC Certificate)", where no clerk
        would look for it."""
        label = _rect(30, 104, 90, 116)
        words = [_word(120, 104, 200, 116, "SC/Other-than-SC")]
        gaps = fg.writable_gaps(self.CELLS, label, words, page_width=600)
        assert gaps[0][0] == pytest.approx(94, abs=2)
        assert gaps[0][1] < 120

    def test_a_later_gap_is_still_offered_for_a_long_value(self):
        """"c) Date of birth:(Enclose Certificate)" leaves 28 points before the
        hint and 280 after it. Offering only the first reported the field
        unfillable."""
        label = _rect(30, 104, 90, 116)
        words = [_word(100, 104, 180, 116, "(Enclose")]
        gaps = fg.writable_gaps(self.CELLS, label, words, page_width=600)
        assert len(gaps) >= 2
        widest = max(gaps, key=lambda g: g[1] - g[0])
        assert widest[0] >= 180

    def test_a_full_row_yields_no_gap_rather_than_a_bad_one(self):
        label = _rect(30, 104, 90, 116)
        words = [_word(94, 104, 400, 116, "alreadyprinted")]
        assert fg.writable_gaps(self.CELLS, label, words, page_width=600) == []

    def test_writable_span_still_returns_one_answer(self):
        label = _rect(30, 104, 90, 116)
        start, end = fg.writable_span(self.CELLS, label, [], page_width=600)
        assert end > start


class TestAgainstARealScan:
    """The whole point, run against the actual published Haryana form.

    Skipped when the fixture is absent so the suite stays runnable offline;
    scripts/demo_fill.py writes it.
    """

    FIXTURE = "/tmp/demo_fill/original.pdf"

    @pytest.fixture
    def page(self):
        pytest.importorskip("numpy")
        pymupdf = pytest.importorskip("pymupdf")
        import os

        if not os.path.exists(self.FIXTURE):
            pytest.skip("run scripts/demo_fill.py to fetch the source form")
        return pymupdf.open(self.FIXTURE)[0]

    def test_a_scan_has_no_vector_lines_at_all(self, page):
        """The reason this module exists."""
        assert not page.get_drawings()

    def test_the_grid_is_recovered_from_the_image(self, page):
        summary = fg.describe(page)
        assert summary["gridDetected"]
        assert summary["cells"] > 10

    def test_the_college_value_stops_before_the_class_column(self, page):
        """The failure that started this: the college name ran across Class,
        Session and Admission No.

        Asserted on the writable span rather than the raw cell. The Class
        divider does not run the full height of this row, so the cell is
        row-wide and it is the printed word "Class" that bounds the value —
        which is the right answer arrived at by the second rule rather than the
        first, and the citizen cannot tell the difference.
        """
        rect = page.search_for("Name of the College/School")[0]
        start, end = fg.writable_span(fg.build_cells(page), rect,
                                      page.get_text("words"), page.rect.width)
        class_column = page.search_for("Class")[0]
        assert end <= class_column.x0 + 1

    def test_a_row_wide_field_is_not_capped_by_another_row_s_divider(self, page):
        """The Class/Session dividers exist on two rows. Treating their x as a
        page-wide boundary shrank the Address cell to 56% of its real width."""
        cells = fg.build_cells(page)
        rect = page.search_for("Address")[0]
        start, end = fg.writable_span(cells, rect, page.get_text("words"),
                                      page.rect.width)
        assert end - start > 250
