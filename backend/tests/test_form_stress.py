"""Stress and edge-case tests for placing values on a printed form.

Every case here is drawn by tests/formfactory.py at known coordinates, so an
assertion can say not merely "a value was written" but "it was written in the
box this test drew for it". That is the only assertion worth making: the
failures that matter on a government form are all of the form *right value,
wrong box*.

The shapes covered are the ones Indian government forms actually use, and the
ones that have broken this filler at least once each:

  * comb fields — one character to a square, for Aadhaar and account numbers
  * two fields sharing one printed row
  * a column-header row over a blank data row
  * a label whose box is far from its text
  * choice cells, where "Yes/No" is printed in the answer box
  * pages with no text layer at all
  * values longer than the space, empty values, unicode, and junk
"""
import os
import tempfile

import pytest

pytest.importorskip("numpy")
pymupdf = pytest.importorskip("pymupdf")

import form_geometry as fg          # noqa: E402
import pdf_filler as pf             # noqa: E402
from formfactory import FormBuilder, aadhaar_comb_form  # noqa: E402


def field(name, label, key=None, ftype="text", required=True, options=None):
    f = {"fieldName": name, "labelEnglish": label, "labelHindi": "",
         "type": ftype, "required": required, "profileKey": key or name}
    if options:
        f["options"] = options
    return f


def fill(path, profile, fields):
    """Fill and return (report, written-by-field)."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        out = tmp.name
    try:
        report = pf.fill_pdf_form(path, out, profile, fields)
    finally:
        if os.path.exists(out):
            os.unlink(out)
    return report, {w["fieldName"]: w for w in report.get("written", [])}


def in_box(written, box, slack=3.0):
    """True when a written value starts inside the box it was meant for."""
    return (box.x0 - slack <= written["x"] <= box.x1
            and box.y0 - slack <= written["y"] <= box.y1 + slack)


@pytest.fixture(scope="module")
def comb_form(tmp_path_factory):
    """One form, built once, shared by every test that reads it and none
    that writes to it — filling always writes to a temporary copy."""
    path = str(tmp_path_factory.mktemp("comb") / "comb.pdf")
    return aadhaar_comb_form(path)


# ── Comb fields ─────────────────────────────────────────────────────────

class TestCombFields:
    """One character to a square.

    A value written across a comb as one string produces a form a clerk will
    reject: the characters do not line up with the boxes, and a data-entry
    operator keying from the squares reads nonsense.
    """

    FIELDS = [
        field("name", "Full Name"),
        field("aadhaar_number", "Aadhaar Number", ftype="aadhaar"),
        field("mobile_number", "Mobile Number", ftype="phone"),
        field("district", "District"),
    ]
    PROFILE = {"name": "Priya Sharma", "aadhaar_number": "234567890124",
               "mobile_number": "9812345678", "district": "Jhajjar"}

    def test_combs_are_detected_by_shape_not_by_label(self, comb_form):
        path, _ = comb_form
        page = pymupdf.open(path)[0]
        combs = fg.find_combs(fg.build_cells(page), pf._page_words(page))
        sizes = sorted(len(c) for c in combs)
        assert sizes == [10, 12], "twelve Aadhaar boxes and ten mobile boxes"

    def test_one_character_lands_in_each_box(self, comb_form):
        path, boxes = comb_form
        report, written = fill(path, self.PROFILE, self.FIELDS)
        assert written["aadhaar_number"]["comb_boxes"] == 12
        assert written["mobile_number"]["comb_boxes"] == 10

    def test_every_character_is_inside_its_own_square(self, comb_form):
        path, boxes = comb_form
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            out = tmp.name
        pf.fill_pdf_form(path, out, self.PROFILE, self.FIELDS)
        page = pymupdf.open(out)[0]
        os.unlink(out)

        squares = [c for c in fg.find_combs(fg.build_cells(page), [])
                   if len(c) == 10][0]
        digits = [w for w in page.get_text("words")
                  if w[4].isdigit() and len(w[4]) == 1
                  and squares[0].y0 - 2 <= (w[1] + w[3]) / 2 <= squares[0].y1 + 2]
        assert len(digits) == 10, "a digit per box, none merged or lost"
        for word in digits:
            centre = (word[0] + word[2]) / 2
            assert any(s.x0 <= centre <= s.x1 for s in squares), \
                "a digit landed between two squares"

    def test_separators_the_citizen_typed_are_dropped(self, comb_form):
        path, _ = comb_form
        profile = dict(self.PROFILE, aadhaar_number="2345 6789 0124")
        _, written = fill(path, profile, self.FIELDS)
        assert " " not in written["aadhaar_number"]["text"]

    def test_a_value_longer_than_the_comb_is_never_written_into_it(self, comb_form):
        """Truncation into a comb is the worst failure this filler can have.

        The characters line up in their squares, the form looks correct, and
        the number on it is not the citizen's. Nothing on the page shows that
        anything was dropped. So a comb too short for the value is not this
        field's box: the filler looks elsewhere and, failing that, reports the
        field for the citizen to write themselves.
        """
        path, _ = comb_form
        profile = dict(self.PROFILE, mobile_number="98123456789999")
        report, written = fill(path, profile, self.FIELDS)
        item = written.get("mobile_number")
        if item is not None:
            # Placed somewhere else on the row — but never cut short.
            assert not item.get("comb_boxes")
            assert item["text"] == "98123456789999"
        else:
            assert "mobile_number" in {u["profileKey"]
                                       for u in report["unplaced"]}

    def test_a_name_comb_keeps_the_space_between_the_names(self, comb_form):
        """A comb for a name leaves an empty box where the space goes.

        Stripping it the way an Aadhaar's separators are stripped wrote
        "SnehaFernandes" across the Daman & Diu form — one character to a
        square, perfectly aligned, and not the applicant's name.
        """
        path, _ = comb_form
        fields = [field("name", "Aadhaar Number")]   # the 12-box comb
        _, written = fill(path, {"name": "Priya Sharma"}, fields)
        assert written["name"]["comb_boxes"] == 12, "not written into the comb"
        assert written["name"]["text"] == "Priya Sharma"

    def test_a_short_value_leaves_the_rest_of_the_comb_empty(self, comb_form):
        path, _ = comb_form
        profile = dict(self.PROFILE, mobile_number="98123")
        _, written = fill(path, profile, self.FIELDS)
        assert written["mobile_number"]["text"] == "98123"
        assert written["mobile_number"]["truncated"] is False

    def test_ordinary_fields_on_the_same_form_still_work(self, comb_form):
        path, boxes = comb_form
        _, written = fill(path, self.PROFILE, self.FIELDS)
        assert in_box(written["name"], boxes["name"])
        assert in_box(written["district"], boxes["district"])

    def test_nothing_overlaps(self, comb_form):
        path, _ = comb_form
        report, _ = fill(path, self.PROFILE, self.FIELDS)
        assert report["verification"]["clean"], \
            report["verification"]["problems"]


# ── Layout shapes ───────────────────────────────────────────────────────

class TestLayoutShapes:
    def _form(self, tmp_path, build):
        b = FormBuilder()
        build(b)
        path = str(tmp_path / "form.pdf")
        b.save(path)
        boxes = dict(b.boxes)
        b.close()
        return path, boxes

    def test_two_fields_in_one_row_do_not_collide(self, tmp_path):
        """"Mobile No: | Email ID:" — the space past the second label belongs
        to the second field, and writing the first there put a phone number on
        top of an email address."""
        path, boxes = self._form(tmp_path, lambda b: b.two_fields_in_a_row(
            100, "Mobile No", "mobile", "Email ID", "email"))
        fields = [field("mobile_number", "Mobile No", ftype="phone"),
                  field("email", "Email ID", ftype="email")]
        report, written = fill(path, {"mobile_number": "9812345678",
                                      "email": "a@b.com"}, fields)
        assert in_box(written["mobile_number"], boxes["mobile"])
        assert in_box(written["email"], boxes["email"])
        assert report["verification"]["clean"]

    def test_a_column_heading_writes_into_the_row_beneath(self, tmp_path):
        path, boxes = self._form(tmp_path, lambda b: b.header_table(
            100, ["Institution", "Class", "Session"],
            ["institution", "class", "session"]))
        fields = [field("institution_name", "Institution"),
                  field("current_class", "Class"),
                  field("academic_session", "Session")]
        report, written = fill(path, {
            "institution_name": "Government College for Women",
            "current_class": "B.A. II", "academic_session": "2025-26"}, fields)
        assert in_box(written["institution_name"], boxes["institution"])
        assert in_box(written["current_class"], boxes["class"])
        assert in_box(written["academic_session"], boxes["session"])

    def test_a_narrow_column_does_not_bleed_into_its_neighbour(self, tmp_path):
        """The failure that started all of this: a college name printed across
        the Class, Session and Admission No. columns."""
        path, boxes = self._form(tmp_path, lambda b: b.header_table(
            100, ["Institution", "Class", "Session"],
            ["institution", "class", "session"]))
        fields = [field("institution_name", "Institution")]
        report, written = fill(
            path, {"institution_name": "Government College for Women, "
                                       "Bahadurgarh, Jhajjar District"}, fields)
        if "institution_name" in written:
            item = written["institution_name"]
            assert item["x"] + item["width"] <= boxes["institution"].x1 + 2
        assert report["verification"]["clean"]

    def test_a_box_far_from_its_label_is_still_found(self, tmp_path):
        """A short label in a wide cell leaves the box a long way from the
        words; measuring adjacency from the text missed it entirely."""
        path, boxes = self._form(
            tmp_path, lambda b: b.labelled_row(100, "Name", "name", split=300))
        _, written = fill(path, {"name": "Priya Sharma"}, [field("name", "Name")])
        assert in_box(written["name"], boxes["name"])

    def test_a_choice_cell_takes_the_answer_beside_its_options(self, tmp_path):
        """"Yes/No" printed in the answer box is not an occupied cell."""
        def build(b):
            b.cell(40, 100, 300, 120, label="Are you a taxpayer?")
            b.cell(300, 100, 550, 120, label="Yes / No", name="answer")
        path, boxes = self._form(tmp_path, build)
        fields = [field("is_income_tax_payer", "Are you a taxpayer?",
                        ftype="select", options=["Yes", "No"])]
        _, written = fill(path, {"is_income_tax_payer": "No"}, fields)
        assert "is_income_tax_payer" in written
        assert in_box(written["is_income_tax_payer"], boxes["answer"])

    def test_a_prose_question_outside_the_grid_is_still_answered(self, tmp_path):
        """A ruled form is not ruled all the way down.

        Item 15 of the Haryana form is running text below the last table, and
        it wraps: the line carrying the answer slot ends in "Yes/No" with the
        question mark on the *next* line. Both facts — no cell, no "?" — once
        made the filler drop a question the citizen had answered.
        """
        def build(b):
            b.cell(40, 100, 550, 130, label="Name of the Applicant",
                   name="topcell")
            b.text(40, 200, "15. Has the applicant applied for any other "
                            "sports scholarship from Yes/No")
            b.text(40, 214, "SAI or any other agency for the said "
                            "achievements?")
        path, _ = self._form(tmp_path, build)
        fields = [field("applied_other_scholarship",
                        "applied for any other sports scholarship",
                        ftype="select", required=False, options=["Yes", "No"])]
        report, written = fill(path, {"applied_other_scholarship": "No"},
                               fields)
        item = written.get("applied_other_scholarship")
        assert item, "the question was left unanswered"
        # Past the printed "Yes/No", on its own line, still on the page.
        assert item["y"] <= 205
        assert item["x"] > 300
        assert item["x"] + item["width"] <= 595
        assert report["verification"]["clean"], \
            report["verification"]["problems"]

    def test_prose_that_merely_mentions_an_option_is_left_alone(self, tmp_path):
        """The declaration says "no" in a sentence. It is not a Yes/No slot."""
        def build(b):
            b.text(40, 200, "I certify that no scholarship has been received "
                            "by me on account of the said achievement, and "
                            "that the particulars given above are true.")
        path, _ = self._form(tmp_path, build)
        fields = [field("applied_other_scholarship", "scholarship has been",
                        ftype="select", required=False, options=["Yes", "No"])]
        _, written = fill(path, {"applied_other_scholarship": "No"}, fields)
        assert "applied_other_scholarship" not in written

    def test_a_missing_border_is_bridged(self, tmp_path):
        """Scans lose rules. A line does not stop for one row and resume."""
        def build(b):
            b.rule_h(40, 550, 100)
            b.rule_h(40, 550, 130)
            b.rule_h(40, 550, 160)
            b.rule_v(40, 100, 130)      # left border stops early
            b.rule_v(40, 160, 190)
            b.rule_v(550, 100, 190)
            b.rule_h(40, 550, 190)
            b.text(45, 125, "Address")
        path, _ = self._form(tmp_path, build)
        page = pymupdf.open(path)[0]
        cells = fg.build_cells(page)
        assert any(c.y0 < 135 < c.y1 and c.width > 400 for c in cells), \
            "the row with the gap in its border formed no cell"


# ── Degradation ─────────────────────────────────────────────────────────

class TestDegradesHonestly:
    def test_a_devanagari_value_is_written_as_itself(self, tmp_path):
        """Not as a row of middle dots.

        Everything was written in the base-14 "helv", which is encoded in
        Latin-1 and has no Devanagari glyph. PyMuPDF does not refuse such a
        string — it draws a middle dot per character. So a citizen who gave
        their name in Hindi, in an app built for exactly that, got
        "······ ·····" on the official form, in the right box, at the right
        width, with nothing anywhere reporting a problem.
        """
        b = FormBuilder()
        b.labelled_row(100, "Full Name", "name")
        b.labelled_row(130, "District", "district")
        path = str(tmp_path / "hi.pdf")
        b.save(path)
        b.close()

        out = str(tmp_path / "out.pdf")
        fields = [field("name", "Full Name"), field("district", "District")]
        pf.fill_pdf_form(path, out, {"name": "प्रिया शर्मा",
                                     "district": "झज्जर"}, fields)
        text = pymupdf.open(out)[0].get_text()
        assert "प्रिया शर्मा" in text
        assert "झज्जर" in text
        assert "·····" not in text, "written as dots, not as the name"

    def test_a_script_no_bundled_font_covers_is_reported_not_dotted(self, tmp_path):
        """Gurmukhi has no face here. Saying so beats drawing dots."""
        b = FormBuilder()
        b.labelled_row(100, "Full Name", "name")
        path = str(tmp_path / "pa.pdf")
        b.save(path)
        b.close()
        report, written = fill(path, {"name": "ਪ੍ਰਿਆ ਸ਼ਰਮਾ"},
                               [field("name", "Full Name")])
        assert "name" not in written
        assert "name" in {u["profileKey"] for u in report["unplaced"]}

    def test_a_value_too_long_for_its_box_is_reported_not_cut(self, tmp_path):
        """An ellipsis is three points wide and nobody looks for it.

        "Government College for Women, B…" in a school box reads as an answer,
        and the citizen signs beneath it.
        """
        def build(b):
            b.cell(40, 100, 200, 120, label="School")
            b.cell(200, 100, 250, 120, name="tiny")
        path, _ = TestLayoutShapes()._form(tmp_path, build)
        long_name = "Government College for Women, Bahadurgarh, Jhajjar"
        report, written = fill(path, {"institution_name": long_name},
                               [field("institution_name", "School")])
        if "institution_name" in written:
            assert written["institution_name"]["text"] == long_name
        else:
            assert "institution_name" in {u["profileKey"]
                                          for u in report["unplaced"]}

    def test_a_page_with_no_text_layer_is_read_by_ocr(self, tmp_path):
        b = FormBuilder()
        b.labelled_row(100, "Full Name", "name")
        b.labelled_row(130, "District", "district")
        path = str(tmp_path / "scan.pdf")
        b.save(path, flatten=True)
        b.close()

        page = pymupdf.open(path)[0]
        assert page.get_text().strip() == "", "fixture must be a pure image"
        assert len(pf._page_text(page)) > 10, "OCR produced nothing"

    def test_a_blank_page_places_nothing_and_does_not_raise(self, tmp_path):
        b = FormBuilder()
        path = str(tmp_path / "blank.pdf")
        b.save(path)
        b.close()
        report, written = fill(path, {"name": "Priya"}, [field("name", "Name")])
        assert written == {}
        assert report.get("unplaced")

    def test_a_form_with_no_grid_still_uses_the_text(self, tmp_path):
        """A typed letter has no rules at all."""
        b = FormBuilder()
        b.text(40, 100, "Full Name:")
        b.text(40, 130, "District:")
        path = str(tmp_path / "letter.pdf")
        b.save(path)
        b.close()
        page = pymupdf.open(path)[0]
        assert fg.build_cells(page) == []
        report, written = fill(path, {"name": "Priya Sharma"},
                               [field("name", "Full Name")])
        assert "name" in written

    @pytest.mark.parametrize("value", [
        "", None, "   ", 0, False,
    ])
    def test_an_empty_value_is_never_written(self, tmp_path, value):
        b = FormBuilder()
        b.labelled_row(100, "Full Name", "name")
        path = str(tmp_path / "f.pdf")
        b.save(path)
        b.close()
        _, written = fill(path, {"name": value}, [field("name", "Full Name")])
        assert "name" not in written

    @pytest.mark.parametrize("value", [
        "प्रिया शर्मा",                       # Devanagari
        "O'Brien-D'Souza",                    # punctuation
        "A" * 300,                            # far longer than any box
        "priya\nsharma",                      # an embedded newline
        "  Priya  Sharma  ",                  # stray whitespace
    ])
    def test_awkward_values_do_not_break_the_fill(self, tmp_path, value):
        b = FormBuilder()
        b.labelled_row(100, "Full Name", "name")
        path = str(tmp_path / "f.pdf")
        b.save(path)
        b.close()
        report, _ = fill(path, {"name": value}, [field("name", "Full Name")])
        assert report.get("verification", {}).get("verified") is not False

    def test_a_field_the_form_does_not_have_is_reported(self, tmp_path):
        b = FormBuilder()
        b.labelled_row(100, "Full Name", "name")
        path = str(tmp_path / "f.pdf")
        b.save(path)
        b.close()
        report, _ = fill(path, {"name": "Priya", "pincode": "124507"},
                         [field("name", "Full Name"),
                          field("pincode", "PIN Code")])
        unplaced = {u["profileKey"] for u in report["unplaced"]}
        assert "pincode" in unplaced

    def test_a_corrupt_file_degrades_instead_of_raising(self, tmp_path):
        path = tmp_path / "broken.pdf"
        path.write_bytes(b"%PDF-1.4\nnot really a pdf")
        report = pf.fill_pdf_form(str(path), str(tmp_path / "out.pdf"),
                                  {"name": "Priya"}, [field("name", "Name")])
        assert report["success"] is False and report.get("error")


# ── Invariants that must hold on every form ─────────────────────────────

class TestInvariants:
    """Properties that must never be violated, whatever the form looks like."""

    FIELDS = [
        field("name", "Full Name"),
        field("father_husband_name", "Father's Name"),
        field("aadhaar_number", "Aadhaar Number", ftype="aadhaar"),
        field("mobile_number", "Mobile Number", ftype="phone"),
        field("district", "District"),
        field("email", "Email ID", ftype="email"),
        field("pincode", "PIN Code"),
        field("institution_name", "Institution"),
        field("current_class", "Class"),
        field("academic_session", "Session"),
    ]
    PROFILE = {
        "name": "Priya Sharma", "father_husband_name": "Rajesh Sharma",
        "aadhaar_number": "234567890124", "mobile_number": "9812345678",
        "district": "Jhajjar", "email": "priya@example.com",
        "pincode": "124507", "institution_name": "Govt College",
        "current_class": "B.A. II", "academic_session": "2025-26",
    }

    def test_every_value_lands_in_the_box_drawn_for_it(self, comb_form):
        path, boxes = comb_form
        _, written = fill(path, self.PROFILE, self.FIELDS)
        expected = {
            "name": "name", "father_husband_name": "father",
            "aadhaar_number": "aadhaar", "mobile_number": "mobile",
            "district": "district", "email": "email", "pincode": "pincode",
            "institution_name": "institution", "current_class": "class",
            "academic_session": "session",
        }
        misplaced = [
            name for name, box in expected.items()
            if name in written and not in_box(written[name], boxes[box])
        ]
        assert not misplaced, f"written outside their own box: {misplaced}"

    def test_no_field_is_written_twice(self, comb_form):
        path, _ = comb_form
        report, _ = fill(path, self.PROFILE, self.FIELDS)
        names = [w["fieldName"] for w in report["written"]]
        assert len(names) == len(set(names))

    def test_no_value_crosses_a_printed_border(self, comb_form):
        path, _ = comb_form
        report, _ = fill(path, self.PROFILE, self.FIELDS)
        assert not [p for p in report["verification"]["problems"]
                    if p["kind"] == "crossed_cell_border"]

    def test_no_two_values_overlap(self, comb_form):
        path, _ = comb_form
        report, _ = fill(path, self.PROFILE, self.FIELDS)
        assert not [p for p in report["verification"]["problems"]
                    if p["kind"] == "values_overlap"]

    def test_no_aadhaar_reaches_the_page_in_full(self, comb_form):
        """s29(4) makes publishing an Aadhaar number an offence, and a comb
        writes the digits one at a time — which must not become a loophole."""
        from dpdp.aadhaar_policy import contains_full_aadhaar

        path, _ = comb_form
        report, written = fill(path, self.PROFILE, self.FIELDS)
        assert not contains_full_aadhaar({"written": str(report["written"])})
        assert "23456789" not in written["aadhaar_number"]["text"]

    def test_filling_is_deterministic(self, comb_form):
        """The same form and the same profile must produce the same page."""
        path, _ = comb_form
        first, _ = fill(path, self.PROFILE, self.FIELDS)
        second, _ = fill(path, self.PROFILE, self.FIELDS)
        as_key = lambda r: sorted(  # noqa: E731
            (w["fieldName"], round(w["x"], 1), round(w["y"], 1), w["text"])
            for w in r["written"])
        assert as_key(first) == as_key(second)
