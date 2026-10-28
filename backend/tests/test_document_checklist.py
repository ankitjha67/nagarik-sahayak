"""Tests for the 'what to carry to the counter' checklist.

The checklist is derived purely from catalog data, so these run without a
server, a database, or any native dependency.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.gov_forms import GOV_FORM_CATALOG, get_by_name  # noqa: E402
from services.document_checklist import (  # noqa: E402
    required_documents, checklist_for, _DOCS,
)


def _keys(name):
    return {d.key for d in required_documents(get_by_name(name))}


class TestEveryFillableSchemeGetsAChecklist:
    def test_no_fillable_scheme_comes_back_empty(self):
        for s in GOV_FORM_CATALOG:
            if not s.get("official_pdf_url"):
                continue
            docs = required_documents(s)
            assert docs, f"{s['schemeName']} produced no checklist"
            # The form itself and a photo are on essentially every application.
            keys = {d.key for d in docs}
            assert "application_form" in keys
            assert "photo" in keys

    def test_the_form_and_identity_lead_the_list(self):
        docs = required_documents(get_by_name("Sports Achievement Scholarship (Haryana)"))
        assert docs[0].key == "application_form"
        assert "identity" in {d.key for d in docs[:4]}


class TestDocumentsAreImpliedByFields:
    def test_bank_fields_ask_for_a_passbook(self):
        assert "bank" in _keys("Sports Achievement Scholarship (Haryana)")

    def test_a_scholarship_asks_for_study_proof_and_marksheet(self):
        keys = _keys("Saraswati Vidya Yojana Scholarship")
        assert "study" in keys
        assert "marksheet" in keys

    def test_an_agriculture_scheme_asks_for_land_records(self):
        assert "land" in _keys("Kisan Credit Card (KCC)")

    def test_a_date_of_birth_field_asks_for_age_proof(self):
        assert "age" in _keys("Sports Achievement Scholarship (Haryana)")

    def test_a_domicile_field_asks_for_a_domicile_certificate(self):
        # The Haryana sports form has an explicit domicile certificate field.
        assert "domicile" in _keys("Sports Achievement Scholarship (Haryana)")


class TestConditionalDocuments:
    def test_caste_certificate_only_when_a_reserved_category_is_offered(self):
        # Saraswati's form has no caste category field at all (girl-student
        # scheme gated on domicile and income), so no caste certificate.
        assert "caste" not in _keys("Saraswati Vidya Yojana Scholarship")
        # KCC and the Haryana form do carry a category field.
        assert "caste" in _keys("Kisan Credit Card (KCC)")

    def test_income_certificate_appears_for_an_income_gated_scheme(self):
        # A rule on annual_income is the clear signal.
        by_rule = {"schemeName": "X", "level": "Central",
                   "extractedFields": [{"profileKey": "name", "type": "text"}],
                   "eligibilityCriteria":
                       {"rules": [{"field": "annual_income", "op": "<", "value": 250000}]}}
        assert "income" in {d.key for d in required_documents(by_rule)}
        # So is a summary that names an income threshold in words.
        by_text = {"schemeName": "Y", "level": "Central",
                   "extractedFields": [{"profileKey": "name", "type": "text"}],
                   "eligibilityCriteria":
                       {"summary": "For families with annual income below 1.5 lakh."}}
        assert "income" in {d.key for d in required_documents(by_text)}

    def test_income_certificate_is_absent_when_nothing_signals_income(self):
        plain = {"schemeName": "Z", "level": "Central",
                 "extractedFields": [{"profileKey": "name", "type": "text"}],
                 "eligibilityCriteria": {"summary": "Open to all residents."}}
        assert "income" not in {d.key for d in required_documents(plain)}

    def test_a_state_scheme_asks_for_domicile_even_without_the_field(self):
        # Force a minimal State scheme with no domicile field.
        scheme = {"schemeName": "X", "level": "State",
                  "extractedFields": [{"profileKey": "name", "type": "text"}]}
        assert "domicile" in {d.key for d in required_documents(scheme)}

    def test_a_central_scheme_without_a_domicile_field_does_not_demand_one(self):
        scheme = {"schemeName": "X", "level": "Central",
                  "extractedFields": [{"profileKey": "name", "type": "text"}]}
        assert "domicile" not in {d.key for d in required_documents(scheme)}


class TestIdentityIsNeverForcedToAadhaar:
    def test_identity_names_non_aadhaar_alternatives(self):
        doc = _DOCS["identity"]
        joined = " ".join(doc.alternatives).lower()
        assert "voter" in joined and "ration" in joined, \
            "a citizen without Aadhaar must see accepted alternatives"


class TestChecklistShape:
    def test_checklist_is_serialisable_and_bilingual(self):
        c = checklist_for(get_by_name("Kisan Credit Card (KCC)"))
        assert c["total"] == len(c["documents"])
        assert c["noticeHindi"] and c["noticeEnglish"]
        for d in c["documents"]:
            assert d["nameEnglish"] and d["nameHindi"]
            assert d["reasonEnglish"] and d["reasonHindi"]
            assert isinstance(d["alternatives"], list)

    def test_no_document_is_listed_twice(self):
        for s in GOV_FORM_CATALOG:
            keys = [d.key for d in required_documents(s)]
            assert len(keys) == len(set(keys)), f"{s['schemeName']} has a duplicate"
