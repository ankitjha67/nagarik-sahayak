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
TEST_PHONE = f"555000{int(time.time()) % 10000:04d}"
TEST_USER_ID = None


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
        response = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": TEST_PHONE, "otp": "1234"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "user_id" in data
        TEST_USER_ID = data["user_id"]
        print(f"✓ User verified: {TEST_USER_ID}")


class TestV2Schemes:
    """V2 /api/v2/schemes endpoint tests"""
    
    def test_get_all_schemes_returns_4(self):
        """GET /api/v2/schemes returns 4 schemes"""
        response = requests.get(f"{BASE_URL}/api/v2/schemes")
        assert response.status_code == 200
        data = response.json()
        assert "schemes" in data
        assert data["count"] == 4
        print(f"✓ /api/v2/schemes returns {data['count']} schemes")
    
    def test_schemes_have_correct_categories(self):
        """Schemes have correct categories: housing, education, startup, agriculture"""
        response = requests.get(f"{BASE_URL}/api/v2/schemes")
        data = response.json()
        categories = [s["category"] for s in data["schemes"]]
        expected_categories = {"housing", "education", "startup", "agriculture"}
        assert set(categories) == expected_categories
        print(f"✓ All 4 categories present: {expected_categories}")
    
    def test_schemes_have_pmay_u(self):
        """PMAY-U scheme exists with correct data"""
        response = requests.get(f"{BASE_URL}/api/v2/schemes")
        data = response.json()
        pmay = next((s for s in data["schemes"] if "PMAY" in s["name"]), None)
        assert pmay is not None
        assert pmay["category"] == "housing"
        assert "nameHindi" in pmay
        print(f"✓ PMAY-U found: {pmay['name']}")
    
    def test_schemes_have_vidyasiri(self):
        """Vidyasiri scheme exists"""
        response = requests.get(f"{BASE_URL}/api/v2/schemes")
        data = response.json()
        vidyasiri = next((s for s in data["schemes"] if "Vidyasiri" in s["name"]), None)
        assert vidyasiri is not None
        assert vidyasiri["category"] == "education"
        print(f"✓ Vidyasiri found: {vidyasiri['name']}")
    
    def test_schemes_have_startup_india(self):
        """Startup India Seed Fund scheme exists"""
        response = requests.get(f"{BASE_URL}/api/v2/schemes")
        data = response.json()
        startup = next((s for s in data["schemes"] if "Startup" in s["name"]), None)
        assert startup is not None
        assert startup["category"] == "startup"
        print(f"✓ Startup India found: {startup['name']}")
    
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
    
    def test_get_all_templates_returns_4(self):
        """GET /api/v2/form-templates returns 4 templates"""
        response = requests.get(f"{BASE_URL}/api/v2/form-templates")
        assert response.status_code == 200
        data = response.json()
        assert "templates" in data
        assert data["count"] == 4
        print(f"✓ /api/v2/form-templates returns {data['count']} templates")
    
    def test_pmay_has_22_fields(self):
        """PMAY-U template has 22 fields"""
        response = requests.get(f"{BASE_URL}/api/v2/form-templates")
        data = response.json()
        pmay = next((t for t in data["templates"] if "PMAY" in t["schemeName"]), None)
        assert pmay is not None
        assert pmay["totalFields"] == 22
        print(f"✓ PMAY-U has {pmay['totalFields']} fields")
    
    def test_vidyasiri_has_20_fields(self):
        """Vidyasiri template has 20 fields"""
        response = requests.get(f"{BASE_URL}/api/v2/form-templates")
        data = response.json()
        vidyasiri = next((t for t in data["templates"] if "Vidyasiri" in t["schemeName"]), None)
        assert vidyasiri is not None
        assert vidyasiri["totalFields"] == 20
        print(f"✓ Vidyasiri has {vidyasiri['totalFields']} fields")
    
    def test_startup_india_has_21_fields(self):
        """Startup India Seed Fund template has 21 fields"""
        response = requests.get(f"{BASE_URL}/api/v2/form-templates")
        data = response.json()
        startup = next((t for t in data["templates"] if "Startup" in t["schemeName"]), None)
        assert startup is not None
        assert startup["totalFields"] == 21
        print(f"✓ Startup India has {startup['totalFields']} fields")
    
    def test_pmkisan_has_19_fields(self):
        """PM-KISAN template has 19 fields"""
        response = requests.get(f"{BASE_URL}/api/v2/form-templates")
        data = response.json()
        pmkisan = next((t for t in data["templates"] if "KISAN" in t["schemeName"]), None)
        assert pmkisan is not None
        assert pmkisan["totalFields"] == 19
        print(f"✓ PM-KISAN has {pmkisan['totalFields']} fields")


class TestV2SingleFormTemplate:
    """V2 /api/v2/form-template/{scheme_name} endpoint tests"""
    
    def test_pmkisan_template_has_19_fields_and_5_sections(self):
        """GET /api/v2/form-template/PM-KISAN returns 19 fields and 5 sections"""
        response = requests.get(f"{BASE_URL}/api/v2/form-template/PM-KISAN%20Samman%20Nidhi")
        assert response.status_code == 200
        data = response.json()
        assert data["schemeName"] == "PM-KISAN Samman Nidhi"
        assert len(data["extractedFields"]) == 19
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
    
    def test_pmkisan_has_farmer_details_section(self):
        """PM-KISAN has Farmer Details section"""
        response = requests.get(f"{BASE_URL}/api/v2/form-template/PM-KISAN%20Samman%20Nidhi")
        data = response.json()
        section_names = [s["name"] for s in data["sections"]]
        assert "Farmer Details" in section_names
        print(f"✓ Sections: {section_names}")
    
    def test_nonexistent_template_returns_404(self):
        """Nonexistent template returns 404"""
        response = requests.get(f"{BASE_URL}/api/v2/form-template/NonexistentScheme")
        assert response.status_code == 404
        print(f"✓ 404 for nonexistent template")


class TestV2UserProfile:
    """V2 /api/v2/user-profile/{user_id} endpoint tests"""
    
    def test_save_profile_fields(self):
        """POST /api/v2/user-profile/{user_id} saves fields"""
        global TEST_USER_ID
        if not TEST_USER_ID:
            pytest.skip("No test user_id available")
        
        response = requests.post(
            f"{BASE_URL}/api/v2/user-profile/{TEST_USER_ID}",
            json={"fields": {"name": "Test User", "aadhaar_number": "1234 5678 9012"}}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "fullProfile" in data
        assert data["fullProfile"]["name"] == "Test User"
        assert data["fullProfile"]["aadhaar_number"] == "1234 5678 9012"
        print(f"✓ Profile fields saved: {data['fieldsUpdated']}")
    
    def test_get_saved_profile(self):
        """GET /api/v2/user-profile/{user_id} returns saved profile"""
        global TEST_USER_ID
        if not TEST_USER_ID:
            pytest.skip("No test user_id available")
        
        response = requests.get(f"{BASE_URL}/api/v2/user-profile/{TEST_USER_ID}")
        assert response.status_code == 200
        data = response.json()
        assert "fullProfile" in data
        assert data["fullProfile"]["name"] == "Test User"
        assert data["fullProfile"]["aadhaar_number"] == "1234 5678 9012"
        print(f"✓ Profile retrieved: {list(data['fullProfile'].keys())}")
    
    def test_profile_merges_not_overwrites(self):
        """Profile update merges new fields, doesn't overwrite"""
        global TEST_USER_ID
        if not TEST_USER_ID:
            pytest.skip("No test user_id available")
        
        # Add more fields
        response = requests.post(
            f"{BASE_URL}/api/v2/user-profile/{TEST_USER_ID}",
            json={"fields": {"state": "Karnataka", "gender": "Male"}}
        )
        assert response.status_code == 200
        data = response.json()
        # Should have all 4 fields now
        assert data["fullProfile"]["name"] == "Test User"  # Original
        assert data["fullProfile"]["aadhaar_number"] == "1234 5678 9012"  # Original
        assert data["fullProfile"]["state"] == "Karnataka"  # New
        assert data["fullProfile"]["gender"] == "Male"  # New
        print(f"✓ Profile merged correctly: {len(data['fullProfile'])} fields")
    
    def test_invalid_user_returns_404(self):
        """Invalid user_id returns 404"""
        response = requests.get(f"{BASE_URL}/api/v2/user-profile/invalid_user_id_123")
        assert response.status_code == 404
        print(f"✓ 404 for invalid user_id")


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
            json={"user_id": TEST_USER_ID, "scheme_names": ["PM-KISAN Samman Nidhi", "Vidyasiri Scholarship"]}
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
        
        # First fill more profile fields
        requests.post(
            f"{BASE_URL}/api/v2/user-profile/{TEST_USER_ID}",
            json={"fields": {
                "father_husband_name": "Test Father",
                "date_of_birth": "1990-01-01",
                "mobile_number": "9876543210",
                "district": "Bangalore",
                "pincode": "560001"
            }}
        )
        
        response = requests.post(
            f"{BASE_URL}/api/v2/generate-filled-forms",
            json={"user_id": TEST_USER_ID, "scheme_names": ["PM-KISAN Samman Nidhi"]}
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
            json={"user_id": TEST_USER_ID, "scheme_names": ["PM-KISAN Samman Nidhi"]}
        )
        data = gen_response.json()
        pdf_url = data["pdf_urls"][0]["pdf_url"]
        
        # Download the PDF
        response = requests.get(f"{BASE_URL}{pdf_url}")
        assert response.status_code == 200
        assert response.headers.get("content-type") == "application/pdf"
        print(f"✓ PDF downloaded successfully, size: {len(response.content)} bytes")
    
    def test_invalid_pdf_returns_404(self):
        """Invalid PDF UUID returns 404"""
        response = requests.get(f"{BASE_URL}/api/pdf/nonexistent-uuid-12345")
        assert response.status_code == 404
        print(f"✓ 404 for nonexistent PDF")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
