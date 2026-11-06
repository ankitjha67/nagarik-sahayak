"""
Test V2 API endpoints for Nagarik Sahayak v2.0

Tests:
- GET /api/v2/schemes - List all 4 schemes
- GET /api/v2/form-templates - List form templates with totalFields
- GET /api/v2/form-template/{scheme} - Get full template with sections/fields
- POST /api/v2/user-profile/{user_id} - Save profile fields
- GET /api/v2/user-profile/{user_id} - Get saved profile
- POST /api/v2/smart-profiler - Get filled/missing counts
- POST /api/v2/generate-filled-forms - Generate PDFs
- GET /api/pdf/{uuid} - Download generated PDF
"""
import pytest
import requests
import os
import time
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://govt-assistant-app.preview.emergentagent.com').rstrip('/')

# Test user data
TEST_PHONE = f"900000{int(time.time()) % 10000:04d}"
TEST_USER_ID = None


def auth_headers():
    """The header the real app's API client always sends. The profile and PDF
    routes read X-User-Id to enforce ownership (DPDP s8(4)); a request without
    it is correctly refused, so every test that reaches those routes must send
    it, exactly as the frontend does."""
    return {"X-User-Id": TEST_USER_ID or ""}


# These scheme names are stable fixtures in the catalog, chosen one per category
# that is actually present. The original MVP schemes the tests were written
# against (Vidyasiri, PMAY-U, Startup India Seed Fund) have since been replaced
# by the real government-form catalogue, so the tests now assert against schemes
# that exist rather than those four.
STABLE_SCHEME = "PM-KISAN Samman Nidhi"           # agriculture
HOUSING_SCHEME = "Pradhan Mantri Awas Yojana - Gramin"
EDUCATION_SCHEME = "National Scholarship - Post Matric"

# A few profile keys need a value in a specific format to pass validation
# (a six-digit PIN, a digits-only account number, a real IFSC). Everything
# else can be a plausible sample. Kept here so a complete, *valid* profile can
# be built from any scheme's own template, which is what the engine requires
# before it will fill and release a form.
_VALID_SAMPLES = {
    "pincode": "560001", "ifsc_code": "SBIN0001234",
    "bank_account_number": "123456789012", "mobile_number": "9876543210",
    "aadhaar_number": "234567890124", "email": "test@example.com",
    "name": "Ramesh Kumar", "father_husband_name": "Suresh Kumar",
    "survey_khasra_number": "123/4", "land_holding_acres": 2,
}


def complete_valid_profile(scheme_name):
    """Build a profile that satisfies a scheme's form, from the form itself.

    The eligibility/validity engine refuses to fill a form from an incomplete
    or malformed profile — correctly, since a wrong value on a signed
    government form is a false declaration — so a generation test must supply a
    whole valid profile. Reading the required fields from the live template
    keeps the test honest as the form evolves."""
    tpl = requests.get(
        f"{BASE_URL}/api/v2/form-template/{requests.utils.quote(scheme_name)}").json()
    profile = {}
    for f in tpl.get("extractedFields", []):
        key, ftype, options = f["profileKey"], f.get("type", "text"), f.get("options")
        if key in _VALID_SAMPLES:
            profile[key] = _VALID_SAMPLES[key]
        elif options:
            profile[key] = options[0]
        elif ftype == "date":
            profile[key] = "1985-06-15"
        elif ftype == "number":
            profile[key] = 2
        else:
            profile[key] = "Sample " + key.replace("_", " ").title()
    return profile


class TestAuth:
    """Authentication to get a test user_id"""
    
    def test_send_otp(self):
        """Send OTP to test phone"""
        response = requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": TEST_PHONE})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        print(f"✓ OTP sent to {TEST_PHONE}")
    
    def test_verify_otp(self):
        """Verify OTP and get user_id"""
        global TEST_USER_ID
        response = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": TEST_PHONE, "otp": "123456"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "user_id" in data
        TEST_USER_ID = data["user_id"]
        print(f"✓ User verified: {TEST_USER_ID}")


class TestV2Schemes:
    """V2 /api/v2/schemes endpoint tests"""

    def test_get_all_schemes_is_populated_and_consistent(self):
        """GET /api/v2/schemes returns the catalogue, with count matching the list.

        The catalogue grew from the original four MVP schemes to the full real
        government-form set, so this asserts the invariant — a populated list
        whose reported count matches it — rather than a frozen number."""
        response = requests.get(f"{BASE_URL}/api/v2/schemes")
        assert response.status_code == 200
        data = response.json()
        assert "schemes" in data
        assert data["count"] == len(data["schemes"])
        assert data["count"] >= 4, "catalogue should never be emptier than the MVP"
        print(f"✓ /api/v2/schemes returns {data['count']} schemes")

    def test_schemes_have_known_categories(self):
        """Every scheme carries one of the catalogue's declared categories."""
        response = requests.get(f"{BASE_URL}/api/v2/schemes")
        data = response.json()
        categories = {s["category"] for s in data["schemes"]}
        known = {"housing", "education", "startup", "agriculture",
                 "health", "finance", "general"}
        assert categories, "schemes must declare categories"
        assert categories <= known, f"unexpected categories: {categories - known}"
        print(f"✓ Categories present: {sorted(categories)}")

    def test_schemes_have_a_housing_scheme(self):
        """A housing scheme exists with the expected shape."""
        response = requests.get(f"{BASE_URL}/api/v2/schemes")
        data = response.json()
        housing = next((s for s in data["schemes"] if s["category"] == "housing"), None)
        assert housing is not None
        assert "nameHindi" in housing
        print(f"✓ Housing scheme found: {housing['name']}")

    def test_schemes_have_an_education_scheme(self):
        """An education scheme exists (the original Vidyasiri was replaced)."""
        response = requests.get(f"{BASE_URL}/api/v2/schemes")
        data = response.json()
        edu = next((s for s in data["schemes"] if s["category"] == "education"), None)
        assert edu is not None
        assert "nameHindi" in edu
        print(f"✓ Education scheme found: {edu['name']}")

    def test_schemes_have_pmkisan(self):
        """PM-KISAN scheme exists"""
        response = requests.get(f"{BASE_URL}/api/v2/schemes")
        data = response.json()
        pmkisan = next((s for s in data["schemes"] if "KISAN" in s["name"]), None)
        assert pmkisan is not None
        assert pmkisan["category"] == "agriculture"
        print(f"✓ PM-KISAN found: {pmkisan['name']}")


class TestV2FormTemplates:
    """V2 /api/v2/form-templates endpoint tests"""
    
    def test_templates_match_scheme_count(self):
        """Every scheme has a form template: the two lists are the same size."""
        templates = requests.get(f"{BASE_URL}/api/v2/form-templates").json()
        schemes = requests.get(f"{BASE_URL}/api/v2/schemes").json()
        assert templates["count"] == len(templates["templates"])
        assert templates["count"] == schemes["count"]
        print(f"✓ /api/v2/form-templates returns {templates['count']} templates")

    def test_every_template_reports_its_field_count(self):
        """Each template in the list declares a field count and its identity.

        The list view is a summary — scheme name, category, counts — and does
        not carry the per-section breakdown, which the detail endpoint provides
        (see TestV2SingleFormTemplate)."""
        data = requests.get(f"{BASE_URL}/api/v2/form-templates").json()
        for t in data["templates"]:
            assert t["totalFields"] >= 1, f"{t['schemeName']} has no fields"
            assert t.get("schemeName")
        print(f"✓ All {data['count']} templates report field counts")

    def test_pmkisan_template_has_fields(self):
        """PM-KISAN's template is present and populated.

        The exact count moved (19 → 21) as the real form was modelled more
        fully, so this asserts the template exists with fields rather than a
        frozen number; the precise PM-KISAN shape is pinned in
        TestV2SingleFormTemplate."""
        data = requests.get(f"{BASE_URL}/api/v2/form-templates").json()
        pmkisan = next((t for t in data["templates"] if "KISAN" in t["schemeName"]), None)
        assert pmkisan is not None
        assert pmkisan["totalFields"] >= 15
        print(f"✓ PM-KISAN has {pmkisan['totalFields']} fields")


class TestV2SingleFormTemplate:
    """V2 /api/v2/form-template/{scheme_name} endpoint tests"""
    
    def test_pmkisan_template_has_21_fields_and_5_sections(self):
        """GET /api/v2/form-template/PM-KISAN returns its current 21 fields / 5 sections."""
        response = requests.get(f"{BASE_URL}/api/v2/form-template/PM-KISAN%20Samman%20Nidhi")
        assert response.status_code == 200
        data = response.json()
        assert data["schemeName"] == "PM-KISAN Samman Nidhi"
        assert len(data["extractedFields"]) == 21
        assert len(data["sections"]) == 5
        print(f"✓ PM-KISAN template: {len(data['extractedFields'])} fields, {len(data['sections'])} sections")
    
    def test_pmkisan_fields_have_required_properties(self):
        """PM-KISAN fields have labelHindi, labelEnglish, profileKey"""
        response = requests.get(f"{BASE_URL}/api/v2/form-template/PM-KISAN%20Samman%20Nidhi")
        data = response.json()
        for field in data["extractedFields"]:
            assert "labelHindi" in field, f"Field missing labelHindi: {field}"
            assert "labelEnglish" in field, f"Field missing labelEnglish: {field}"
            assert "profileKey" in field, f"Field missing profileKey: {field}"
            assert "required" in field, f"Field missing required: {field}"
        print(f"✓ All {len(data['extractedFields'])} fields have required properties")
    
    def test_pmkisan_has_land_details_section(self):
        """PM-KISAN's form covers the applicant's landholding.

        The section was renamed "Land Details" (from the MVP's "Farmer
        Details") when the real PM-KISAN form was modelled — it is the land a
        farmer owns that the scheme turns on."""
        response = requests.get(f"{BASE_URL}/api/v2/form-template/PM-KISAN%20Samman%20Nidhi")
        data = response.json()
        section_names = [s["name"] for s in data["sections"]]
        assert "Land Details" in section_names
        print(f"✓ Sections: {section_names}")
    
    def test_nonexistent_template_returns_404(self):
        """Nonexistent template returns 404"""
        response = requests.get(f"{BASE_URL}/api/v2/form-template/NonexistentScheme")
        assert response.status_code == 404
        print(f"✓ 404 for nonexistent template")


class TestV2UserProfile:
    """V2 /api/v2/user-profile/{user_id} endpoint tests"""
    
    def test_save_profile_fields(self):
        """POST /api/v2/user-profile/{user_id} saves fields — and never the Aadhaar.

        The full Aadhaar is stripped before storage (Aadhaar Act s29; see
        dpdp/aadhaar_policy): only its last four digits are kept. So the test
        sends one and asserts the ordinary fields round-trip while the number
        itself does not reach the stored profile."""
        global TEST_USER_ID
        if not TEST_USER_ID:
            pytest.skip("No test user_id available")

        response = requests.post(
            f"{BASE_URL}/api/v2/user-profile/{TEST_USER_ID}",
            json={"fields": {"name": "Test User", "aadhaar_number": "1234 5678 9012"}},
            headers=auth_headers(),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "fullProfile" in data
        assert data["fullProfile"]["name"] == "Test User"
        # The number is stripped; its last four may be retained.
        assert data["fullProfile"].get("aadhaar_number") != "1234 5678 9012"
        assert "9012" not in str(data["fullProfile"].get("aadhaar_number", "")) or \
            data["fullProfile"].get("aadhaar_number_last4") == "9012"
        print(f"✓ Profile fields saved (Aadhaar stripped): {data['fieldsUpdated']}")

    def test_get_saved_profile(self):
        """GET /api/v2/user-profile/{user_id} returns the saved, non-Aadhaar fields."""
        global TEST_USER_ID
        if not TEST_USER_ID:
            pytest.skip("No test user_id available")

        response = requests.get(
            f"{BASE_URL}/api/v2/user-profile/{TEST_USER_ID}", headers=auth_headers())
        assert response.status_code == 200
        data = response.json()
        assert "fullProfile" in data
        assert data["fullProfile"]["name"] == "Test User"
        assert data["fullProfile"].get("aadhaar_number") != "1234 5678 9012"
        print(f"✓ Profile retrieved: {list(data['fullProfile'].keys())}")

    def test_profile_merges_not_overwrites(self):
        """Profile update merges new fields rather than replacing the record."""
        global TEST_USER_ID
        if not TEST_USER_ID:
            pytest.skip("No test user_id available")

        response = requests.post(
            f"{BASE_URL}/api/v2/user-profile/{TEST_USER_ID}",
            json={"fields": {"state": "Karnataka", "gender": "Male"}},
            headers=auth_headers(),
        )
        assert response.status_code == 200
        data = response.json()
        # The earlier name survives, and the new fields are added.
        assert data["fullProfile"]["name"] == "Test User"   # original, preserved
        assert data["fullProfile"]["state"] == "Karnataka"   # new
        assert data["fullProfile"]["gender"] == "Male"       # new
        print(f"✓ Profile merged correctly: {len(data['fullProfile'])} fields")
    
    def test_invalid_user_is_refused(self):
        """An unknown or malformed user id never leaks anything: anonymous
        callers get 401, a signed-in citizen asking about any id but their
        own gets 403. Only an admin would ever see the 404."""
        response = requests.get(f"{BASE_URL}/api/v2/user-profile/invalid_user_id_123")
        assert response.status_code == 401
        if TEST_USER_ID:
            response = requests.get(f"{BASE_URL}/api/v2/user-profile/invalid_user_id_123",
                                    headers=auth_headers())
            assert response.status_code == 403
        print("✓ invalid user_id is refused, not resolved")


class TestV2SmartProfiler:
    """V2 /api/v2/smart-profiler endpoint tests"""
    
    def test_smart_profiler_returns_counts(self):
        """POST /api/v2/smart-profiler returns filled/missing counts"""
        global TEST_USER_ID
        if not TEST_USER_ID:
            pytest.skip("No test user_id available")
        
        response = requests.post(
            f"{BASE_URL}/api/v2/smart-profiler",
            json={"user_id": TEST_USER_ID, "scheme_names": ["PM-KISAN Samman Nidhi"]}
        )
        assert response.status_code == 200
        data = response.json()
        assert "filledCount" in data
        assert "missingCount" in data
        assert "totalFields" in data
        assert "progress" in data
        print(f"✓ Smart profiler: {data['filledCount']} filled, {data['missingCount']} missing, {data['progress']}% progress")
    
    def test_smart_profiler_returns_next_question(self):
        """Smart profiler returns nextQuestion if profile incomplete"""
        global TEST_USER_ID
        if not TEST_USER_ID:
            pytest.skip("No test user_id available")
        
        response = requests.post(
            f"{BASE_URL}/api/v2/smart-profiler",
            json={"user_id": TEST_USER_ID, "scheme_names": ["PM-KISAN Samman Nidhi"]}
        )
        data = response.json()
        if data["missingCount"] > 0:
            assert "nextQuestion" in data
            assert data["nextQuestion"] is not None
            assert "questionHindi" in data["nextQuestion"]
            assert "profileKey" in data["nextQuestion"]
            print(f"✓ Next question: {data['nextQuestion']['questionHindi'][:50]}...")
        else:
            assert data["allComplete"] == True
            print(f"✓ Profile complete, no next question")
    
    def test_smart_profiler_multiple_schemes(self):
        """Smart profiler works with multiple schemes"""
        global TEST_USER_ID
        if not TEST_USER_ID:
            pytest.skip("No test user_id available")
        
        response = requests.post(
            f"{BASE_URL}/api/v2/smart-profiler",
            json={"user_id": TEST_USER_ID, "scheme_names": [STABLE_SCHEME, EDUCATION_SCHEME]}
        )
        assert response.status_code == 200
        data = response.json()
        # Multiple schemes should have more fields
        assert data["totalFields"] > 19  # PM-KISAN alone has 19
        print(f"✓ Multi-scheme: {data['totalFields']} total fields from 2 schemes")


class TestV2GenerateFilledForms:
    """V2 /api/v2/generate-filled-forms endpoint tests"""
    
    def test_generate_forms_returns_pdf_urls(self):
        """POST /api/v2/generate-filled-forms returns pdf_urls"""
        global TEST_USER_ID
        if not TEST_USER_ID:
            pytest.skip("No test user_id available")
        
        # Supply a whole valid profile for the scheme — the engine refuses to
        # fill a form from incomplete or malformed data.
        requests.post(
            f"{BASE_URL}/api/v2/user-profile/{TEST_USER_ID}",
            json={"fields": complete_valid_profile(STABLE_SCHEME)},
            headers=auth_headers(),
        )

        response = requests.post(
            f"{BASE_URL}/api/v2/generate-filled-forms",
            json={"user_id": TEST_USER_ID, "scheme_names": [STABLE_SCHEME]},
            headers=auth_headers(),
        )
        assert response.status_code == 200
        data = response.json()
        assert "pdf_urls" in data
        assert len(data["pdf_urls"]) > 0
        assert "count" in data
        print(f"✓ Generated {data['count']} PDF(s)")
    
    def test_pdf_url_format(self):
        """PDF URL format is correct"""
        global TEST_USER_ID
        if not TEST_USER_ID:
            pytest.skip("No test user_id available")
        
        response = requests.post(
            f"{BASE_URL}/api/v2/generate-filled-forms",
            json={"user_id": TEST_USER_ID, "scheme_names": ["PM-KISAN Samman Nidhi"]}
        )
        data = response.json()
        for pdf_info in data["pdf_urls"]:
            assert "pdf_url" in pdf_info
            assert pdf_info["pdf_url"].startswith("/api/pdf/")
            assert "scheme_name" in pdf_info
            print(f"✓ PDF URL: {pdf_info['pdf_url']} for {pdf_info['scheme_name']}")


class TestPDFDownload:
    """PDF download endpoint tests"""
    
    def test_download_generated_pdf(self):
        """GET /api/pdf/{uuid} downloads PDF"""
        global TEST_USER_ID
        if not TEST_USER_ID:
            pytest.skip("No test user_id available")
        
        # Generate a PDF first
        gen_response = requests.post(
            f"{BASE_URL}/api/v2/generate-filled-forms",
            json={"user_id": TEST_USER_ID, "scheme_names": [STABLE_SCHEME]},
            headers=auth_headers(),
        )
        data = gen_response.json()
        pdf_url = data["pdf_urls"][0]["pdf_url"]

        # Download the PDF as its owner — the ownership header is what the real
        # app's client always sends; without it the route returns 401.
        response = requests.get(f"{BASE_URL}{pdf_url}", headers=auth_headers())
        assert response.status_code == 200
        assert response.headers.get("content-type") == "application/pdf"
        print(f"✓ PDF downloaded successfully, size: {len(response.content)} bytes")

    def test_invalid_pdf_returns_404(self):
        """A PDF id with no ownership record returns 404 to an authenticated caller.

        The route answers 404 (not 403) for an unowned artefact so that it is
        indistinguishable from one that never existed — no existence oracle."""
        response = requests.get(
            f"{BASE_URL}/api/pdf/nonexistent-uuid-12345", headers=auth_headers())
        assert response.status_code == 404
        print(f"✓ 404 for nonexistent PDF")

    def test_pdf_without_auth_is_refused(self):
        """A download with no X-User-Id is refused outright (ownership gate)."""
        response = requests.get(f"{BASE_URL}/api/pdf/nonexistent-uuid-12345")
        assert response.status_code == 401
        print(f"✓ 401 for unauthenticated PDF request")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
