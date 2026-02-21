"""
Test suite for Agnost SDK integration in Nagarik Sahayak API
Tests: analytics/status, search-schemes, eligibility-check, generate-pdf with agnost tracking
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://govt-assistant.preview.emergentagent.com')


class TestAnalyticsStatus:
    """Test GET /api/analytics/status endpoint"""
    
    def test_analytics_status_returns_enabled_true(self):
        """Verify analytics/status returns enabled: true and dashboard_url"""
        response = requests.get(f"{BASE_URL}/api/analytics/status")
        assert response.status_code == 200
        
        data = response.json()
        assert "enabled" in data, "Response must contain 'enabled' field"
        assert data["enabled"] is True, "Analytics should be enabled"
        assert "dashboard_url" in data, "Response must contain 'dashboard_url' field"
        assert data["dashboard_url"] == "https://app.agnost.ai", "Dashboard URL should be Agnost"


class TestSearchSchemes:
    """Test POST /api/search-schemes endpoint with agnost tracking"""
    
    def test_search_schemes_farmer_returns_results(self):
        """Verify search-schemes with query 'farmer' returns PM-KISAN scheme"""
        response = requests.post(
            f"{BASE_URL}/api/search-schemes",
            json={"query": "farmer"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("match_found") is True, "Search should find matching schemes"
        assert "matched_schemes" in data, "Response should contain matched_schemes"
        assert len(data["matched_schemes"]) > 0, "Should have at least one matched scheme"
        
        # Verify PM-KISAN is in results
        scheme_titles = [s.get("scheme_title_en", "") for s in data["matched_schemes"]]
        assert any("KISAN" in title for title in scheme_titles), "PM-KISAN should be in results for 'farmer' query"
    
    def test_search_schemes_returns_tool_metadata(self):
        """Verify search-schemes returns MCP tool metadata"""
        response = requests.post(
            f"{BASE_URL}/api/search-schemes",
            json={"query": "health insurance"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("tool_name") == "search_schemes", "Tool name should be search_schemes"
        assert "tool_input" in data, "Should contain tool_input"
        assert "documents_scanned" in data, "Should contain documents_scanned list"
    
    def test_search_schemes_no_match(self):
        """Verify search-schemes handles no-match gracefully"""
        response = requests.post(
            f"{BASE_URL}/api/search-schemes",
            json={"query": "xyz123nonexistent"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("match_found") is False, "Should return match_found: false for invalid query"


class TestEligibilityCheck:
    """Test POST /api/eligibility-check endpoint with agnost tracking"""
    
    def test_eligibility_check_with_profile(self):
        """Verify eligibility-check returns eligibility results for valid profile"""
        profile = {
            "name": "Test User",
            "age": 30,
            "income": 20000,
            "state": "Maharashtra"
        }
        response = requests.post(
            f"{BASE_URL}/api/eligibility-check",
            json={"profile": profile},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("match_found") is True, "Should find eligibility results"
        assert "results" in data, "Should contain results array"
        assert len(data["results"]) > 0, "Should have at least one scheme result"
        
        # Verify result structure
        result = data["results"][0]
        assert "scheme" in result, "Result should have scheme name"
        assert "eligible" in result, "Result should have eligible boolean"
        assert "reasons" in result, "Result should have reasons list"
    
    def test_eligibility_check_tool_metadata(self):
        """Verify eligibility-check returns MCP tool metadata"""
        response = requests.post(
            f"{BASE_URL}/api/eligibility-check",
            json={"profile": {"name": "Test", "age": 25, "income": 15000, "state": "Delhi"}},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("tool_name") == "eligibility_matcher", "Tool name should be eligibility_matcher"
        assert "documents_scanned" in data, "Should contain documents_scanned"
    
    def test_eligibility_check_without_profile_returns_400(self):
        """Verify eligibility-check returns 400 without profile"""
        response = requests.post(
            f"{BASE_URL}/api/eligibility-check",
            json={},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400


class TestGeneratePDF:
    """Test POST /api/generate-pdf endpoint with agnost tracking"""
    
    def test_generate_pdf_with_profile(self):
        """Verify generate-pdf creates PDF and returns download URL"""
        profile = {
            "name": "Test User",
            "age": 35,
            "income": 25000,
            "state": "Karnataka"
        }
        response = requests.post(
            f"{BASE_URL}/api/generate-pdf",
            json={"profile": profile},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") is True, "PDF generation should succeed"
        assert "pdf_url" in data, "Should return pdf_url"
        assert "pdf_id" in data, "Should return pdf_id"
        assert data["pdf_url"].startswith("/api/pdf/"), "PDF URL should be /api/pdf/{id}"
        assert "eligible_count" in data, "Should return eligible_count"
        assert "total_schemes" in data, "Should return total_schemes"
    
    def test_generate_pdf_download(self):
        """Verify generated PDF can be downloaded"""
        # First generate a PDF
        profile = {"name": "Download Test", "age": 40, "income": 30000, "state": "Tamil Nadu"}
        gen_response = requests.post(
            f"{BASE_URL}/api/generate-pdf",
            json={"profile": profile},
            headers={"Content-Type": "application/json"}
        )
        assert gen_response.status_code == 200
        
        pdf_url = gen_response.json().get("pdf_url")
        
        # Download the PDF
        download_response = requests.get(f"{BASE_URL}{pdf_url}")
        assert download_response.status_code == 200
        assert download_response.headers.get("content-type") == "application/pdf"
    
    def test_generate_pdf_incomplete_profile_returns_400(self):
        """Verify generate-pdf returns 400 for incomplete profile"""
        response = requests.post(
            f"{BASE_URL}/api/generate-pdf",
            json={"profile": {"age": 30}},  # Missing name
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400


class TestAuthFlow:
    """Test authentication endpoints"""
    
    def test_send_otp(self):
        """Verify send-otp works"""
        response = requests.post(
            f"{BASE_URL}/api/auth/send-otp",
            json={"phone": "9876543210"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
    
    def test_verify_otp_valid(self):
        """Verify OTP verification with mock OTP 1234"""
        # First send OTP
        requests.post(
            f"{BASE_URL}/api/auth/send-otp",
            json={"phone": "9876543210"},
            headers={"Content-Type": "application/json"}
        )
        
        # Then verify
        response = requests.post(
            f"{BASE_URL}/api/auth/verify-otp",
            json={"phone": "9876543210", "otp": "1234"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert "user_id" in data


class TestSchemesEndpoints:
    """Test schemes CRUD endpoints"""
    
    def test_get_all_schemes(self):
        """Verify GET /api/schemes returns seeded schemes"""
        response = requests.get(f"{BASE_URL}/api/schemes")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 3, "Should have at least 3 seeded schemes"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
