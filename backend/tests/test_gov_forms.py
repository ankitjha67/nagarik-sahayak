"""Tests for the real government form catalog and rule-based extraction.

These cover the behaviour that makes real forms work: recovering fields from
noisy OCR text, refusing non-form documents, canonicalising field keys so
answers are reused across schemes, and keeping the bundled catalog valid.
"""
import pytest

from field_rules import (
    build_template_from_text,
    canonicalize_fields,
    classify_label,
    extract_fields_from_text,
    infer_scheme_metadata,
    looks_like_form,
)
from data.gov_forms import get_by_name, get_catalog, all_profile_keys


# Trimmed from the real OCR output of pmkisan.gov.in/Documents/Kcc.pdf —
# retains the noise (stray glyphs, broken tables) that real scans produce.
REAL_OCR_SAMPLE = """--- Page 1 (OCR) ---
ANNEXURE-II

Name of Bank...........
Bran hivecsssscscssssscssssse
To:
The Branch Manager

LOAN APPLICATION FORM FOR AGRICULTURAL CREDIT FOR PM-KISAN BENEFICIARIES

A. For office use:

B. Type of KCC/ Amount of loan required: (Please tick the appropriate box)
Amount of Loan required............

C. Particulars of the applicant(s):
Name of the Applicant.............
Account No (PM Kisan Beneficiary*)........
Aadhaar Number.............
Mobile Number...........

Village......
Area in acres.........

H. Declaration
I/ We hereby declare that all information furnished above is true.
"""

PROSE_SAMPLE = """OPERATIONAL GUIDELINES OF PM-KISAN

The scheme aims to supplement the financial needs of land holding farmers
across the country in procuring various inputs to ensure proper crop health
and appropriate yields commensurate with the anticipated farm income.

Under the scheme an amount of rupees six thousand per year is released by the
Central Government directly into the bank accounts of eligible beneficiaries
subject to certain exclusion criteria described in the following paragraphs.
"""


class TestFormDetection:
    def test_real_form_is_recognised(self):
        is_form, reason = looks_like_form(REAL_OCR_SAMPLE)
        assert is_form, reason

    def test_guidelines_prose_is_rejected(self):
        is_form, _ = looks_like_form(PROSE_SAMPLE)
        assert is_form is False

    def test_empty_text_is_rejected(self):
        assert looks_like_form("")[0] is False
        assert looks_like_form("   \n  ")[0] is False

    def test_build_template_refuses_non_form(self):
        result = build_template_from_text(PROSE_SAMPLE)
        assert result.get("_not_a_form") is True
        assert "error" in result
        assert "extractedFields" not in result

    def test_build_template_can_be_forced(self):
        result = build_template_from_text(PROSE_SAMPLE, require_form=False)
        assert "_not_a_form" not in result


class TestRuleBasedExtraction:
    def test_extracts_fields_from_real_ocr(self):
        fields = extract_fields_from_text(REAL_OCR_SAMPLE)
        keys = {f["profileKey"] for f in fields}
        # These all appear as labelled, dotted-leader fields in the sample.
        assert {"name", "aadhaar_number", "mobile_number",
                "land_holding_acres", "village"} <= keys

    def test_assigns_correct_types(self):
        by_key = {f["profileKey"]: f for f in extract_fields_from_text(REAL_OCR_SAMPLE)}
        assert by_key["aadhaar_number"]["type"] == "aadhaar"
        assert by_key["mobile_number"]["type"] == "phone"
        assert by_key["land_holding_acres"]["type"] == "number"

    def test_internal_separators_are_not_fields(self):
        keys = {f["profileKey"] for f in extract_fields_from_text(REAL_OCR_SAMPLE)}
        # "--- Page 1 (OCR) ---" and similar scaffolding must never leak through.
        assert not any("page" in k and "ocr" in k for k in keys)
        assert "additional_text_pymupdf" not in keys

    def test_no_duplicate_profile_keys(self):
        fields = extract_fields_from_text(REAL_OCR_SAMPLE)
        keys = [f["profileKey"] for f in fields]
        assert len(keys) == len(set(keys))

    def test_prose_line_does_not_become_a_field(self):
        # A long sentence merely mentioning a keyword is not a form field.
        text = ("Students of any class may apply provided the annual family "
                "income of the household does not exceed the prescribed limit.")
        assert extract_fields_from_text(text) == []

    def test_empty_input(self):
        assert extract_fields_from_text("") == []


class TestLabelClassification:
    @pytest.mark.parametrize("label,expected", [
        ("Name of the Applicant", "name"),
        ("Applicant Name", "name"),
        ("Father's Name", "father_husband_name"),
        ("Aadhaar Number", "aadhaar_number"),
        ("Mobile Number", "mobile_number"),
        ("Date of Birth", "date_of_birth"),
        ("IFSC Code", "ifsc_code"),
        ("Annual Family Income", "annual_income"),
        ("आधार संख्या", "aadhaar_number"),
    ])
    def test_maps_to_canonical_key(self, label, expected):
        spec = classify_label(label)
        assert spec is not None, f"{label!r} was not classified"
        assert spec["profileKey"] == expected

    def test_specific_beats_generic(self):
        # "Father's Name" must not collapse into the generic name field.
        assert classify_label("Father's Name")["profileKey"] == "father_husband_name"
        assert classify_label("Full Name")["profileKey"] == "name"

    def test_unknown_label_returns_none(self):
        assert classify_label("Zyxwv Qwerty Placeholder") is None


class TestCanonicalization:
    def test_differing_labels_share_one_key(self):
        """The whole point: two schemes asking the same thing reuse the answer."""
        a = canonicalize_fields([
            {"fieldName": "f1", "labelEnglish": "Name of Applicant", "type": "text"},
        ])
        b = canonicalize_fields([
            {"fieldName": "f2", "labelEnglish": "Applicant's Full Name", "type": "text"},
        ])
        assert a[0]["profileKey"] == b[0]["profileKey"] == "name"

    def test_corrects_weak_llm_types(self):
        out = canonicalize_fields([
            {"fieldName": "x", "labelEnglish": "Aadhaar Number", "type": "text"},
            {"fieldName": "y", "labelEnglish": "Mobile Number", "type": "text"},
        ])
        assert out[0]["type"] == "aadhaar"
        assert out[1]["type"] == "phone"

    def test_deduplicates_by_profile_key(self):
        out = canonicalize_fields([
            {"fieldName": "a", "labelEnglish": "Applicant Name", "type": "text"},
            {"fieldName": "b", "labelEnglish": "Name of Applicant", "type": "text"},
        ])
        assert len(out) == 1

    def test_handles_empty_and_malformed(self):
        assert canonicalize_fields([]) == []
        assert canonicalize_fields(None) == []
        assert canonicalize_fields(["not a dict", 42]) == []

    def test_fills_required_keys(self):
        out = canonicalize_fields([{"labelEnglish": "Some Custom Field"}])
        assert out[0]["profileKey"]
        assert out[0]["fieldName"]
        assert out[0]["type"] == "text"


class TestSchemeMetadata:
    def test_infers_title_and_category(self):
        meta = infer_scheme_metadata(REAL_OCR_SAMPLE)
        assert "LOAN APPLICATION FORM" in meta["schemeName"]
        assert meta["category"] == "agriculture"

    def test_categorises_by_domain(self):
        assert infer_scheme_metadata("Scholarship application for students")["category"] == "education"
        assert infer_scheme_metadata("Ayushman health hospital care")["category"] == "health"
        assert infer_scheme_metadata("Awas Yojana housing for all")["category"] == "housing"


class TestCatalogIntegrity:
    def test_catalog_is_populated(self):
        assert len(get_catalog()) >= 5

    @pytest.mark.parametrize("entry", get_catalog(), ids=lambda e: e["schemeName"])
    def test_entry_is_well_formed(self, entry):
        assert entry["schemeName"]
        assert entry["category"]
        assert entry["officialWebsite"].startswith("http")
        assert entry["extractedFields"], "every scheme needs curated fields"
        assert entry["totalFields"] == len(entry["extractedFields"])

    @pytest.mark.parametrize("entry", get_catalog(), ids=lambda e: e["schemeName"])
    def test_fields_are_well_formed(self, entry):
        valid_types = {"text", "number", "date", "select", "phone",
                       "email", "aadhaar", "textarea"}
        keys = set()
        for f in entry["extractedFields"]:
            assert f["fieldName"] and f["labelEnglish"] and f["labelHindi"], \
                f"{entry['schemeName']}: {f} missing labels"
            assert f["type"] in valid_types, f"{f['fieldName']}: bad type {f['type']}"
            if f["type"] == "select":
                assert f.get("options"), f"{f['fieldName']}: select needs options"
            assert f["profileKey"] not in keys, f"duplicate key {f['profileKey']}"
            keys.add(f["profileKey"])

    @pytest.mark.parametrize("entry", get_catalog(), ids=lambda e: e["schemeName"])
    def test_field_sections_are_declared(self, entry):
        declared = {s["name"] for s in entry.get("sections", [])}
        for f in entry["extractedFields"]:
            assert f["section"] in declared, \
                f"{entry['schemeName']}: field {f['fieldName']} in undeclared " \
                f"section {f['section']!r}"

    def test_lookup_by_exact_and_partial_name(self):
        assert get_by_name("PM-KISAN Samman Nidhi") is not None
        assert get_by_name("pm-kisan samman nidhi") is not None
        assert get_by_name("Kisan Credit Card (KCC)") is not None
        assert get_by_name("No Such Scheme Xyzzy") is None

    def test_profile_keys_are_shared_across_schemes(self):
        """Common identity fields must reuse one key so users answer once."""
        keys = all_profile_keys()
        for shared in ("name", "aadhaar_number", "mobile_number", "district", "state"):
            assert shared in keys

        schemes_with_name = [
            e["schemeName"] for e in get_catalog()
            if any(f["profileKey"] == "name" for f in e["extractedFields"])
        ]
        assert len(schemes_with_name) >= 3
