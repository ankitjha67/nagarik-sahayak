"""
Comprehensive E2E Test Suite for Nagarik Sahayak
Tests: Auth, Profiler Flow, DEMO_MODE, Eligibility, PDF Generation, Search Schemes

Key testing areas:
- Auth: send-otp, verify-otp with OTP=1234
- Profiler: namaste → name → age → income → state → eligibility + PDF
- DEMO_MODE triggers: beta, 10th, scholarship
- Income comparison: YEARLY (not monthly)
- Vidyasiri eligibility: income < 150000/year, state = Karnataka
- PDF download from /api/pdf/{id}
- Search schemes: Document scanned format
"""

import pytest
import requests
import os
import re
import time
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://govt-assistant-app.preview.emergentagent.com').rstrip('/')


class TestAuthEndpoints:
    """Test authentication endpoints"""
    
    def test_send_otp_success(self):
        """POST /api/auth/send-otp returns success for valid phone"""
        phone = f"99887{int(time.time()) % 100000:05d}"
        response = requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": phone})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["success"] is True
        assert "message" in data
        print(f"✓ send-otp success for phone {phone}")
    
    def test_send_otp_invalid_phone(self):
        """POST /api/auth/send-otp returns 400 for invalid phone"""
        response = requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": "123"})
        assert response.status_code == 400, f"Expected 400 for invalid phone, got {response.status_code}"
        print("✓ send-otp rejects invalid phone")
    
    def test_verify_otp_success(self):
        """POST /api/auth/verify-otp with otp=1234 returns user_id"""
        phone = f"99887{int(time.time()) % 100000:05d}"
        # First send OTP
        requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": phone})
        
        # Verify with 1234
        response = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": phone, "otp": "1234"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "user_id" in data
        assert len(data["user_id"]) == 24, f"user_id should be 24-char ObjectId, got: {data['user_id']}"
        print(f"✓ verify-otp success, user_id: {data['user_id']}")
        return data["user_id"]
    
    def test_verify_otp_wrong_otp(self):
        """POST /api/auth/verify-otp with wrong OTP returns failure"""
        phone = f"99887{int(time.time()) % 100000:05d}"
        requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": phone})
        
        response = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": phone, "otp": "9999"})
        data = response.json()
        assert data["success"] is False, "Expected failure for wrong OTP"
        print("✓ verify-otp rejects wrong OTP")


class TestProfilerFlow:
    """Test complete profiler agent flow: namaste → name → age → income → state → complete"""
    
    @pytest.fixture
    def user_id(self):
        """Create a fresh user for testing"""
        phone = f"98765{int(time.time()) % 100000:05d}"
        requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": phone})
        response = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": phone, "otp": "1234"})
        return response.json()["user_id"]
    
    def test_profiler_greeting_asks_name(self, user_id):
        """POST /api/chat with 'namaste' asks for name"""
        response = requests.post(f"{BASE_URL}/api/chat", json={
            "user_id": user_id,
            "content": "namaste",
            "language": "hi"
        })
        assert response.status_code == 200
        data = response.json()
        bot_msg = data["bot_message"]
        
        assert bot_msg["profiler_field"] == "name", f"Expected profiler_field='name', got: {bot_msg.get('profiler_field')}"
        assert "नाम" in bot_msg["content"], "Expected Hindi name question"
        print(f"✓ Profiler asks for name: {bot_msg['content'][:50]}...")
    
    def test_profiler_complete_flow(self, user_id):
        """Complete profiler flow: namaste → name → age → income → state → eligibility + PDF"""
        
        # Step 1: Greeting
        response = requests.post(f"{BASE_URL}/api/chat", json={
            "user_id": user_id, "content": "namaste", "language": "hi"
        })
        assert response.json()["bot_message"]["profiler_field"] == "name"
        print("✓ Step 1: Asked for name")
        
        # Step 2: Provide name
        response = requests.post(f"{BASE_URL}/api/chat", json={
            "user_id": user_id, "content": "Raj Kumar", "language": "hi"
        })
        assert response.json()["bot_message"]["profiler_field"] == "age"
        print("✓ Step 2: Asked for age")
        
        # Step 3: Provide age
        response = requests.post(f"{BASE_URL}/api/chat", json={
            "user_id": user_id, "content": "25", "language": "hi"
        })
        assert response.json()["bot_message"]["profiler_field"] == "income"
        print("✓ Step 3: Asked for income")
        
        # Step 4: Provide income (YEARLY - under 1.5 lakh for Vidyasiri)
        response = requests.post(f"{BASE_URL}/api/chat", json={
            "user_id": user_id, "content": "100000", "language": "hi"
        })
        assert response.json()["bot_message"]["profiler_field"] == "state"
        print("✓ Step 4: Asked for state")
        
        # Step 5: Provide state (Karnataka for Vidyasiri)
        response = requests.post(f"{BASE_URL}/api/chat", json={
            "user_id": user_id, "content": "Karnataka", "language": "hi"
        })
        
        data = response.json()
        bot_msg = data["bot_message"]
        
        # Verify profiler complete
        assert bot_msg["type"] == "profiler_complete", f"Expected type='profiler_complete', got: {bot_msg.get('type')}"
        print("✓ Step 5: Profile complete")
        
        # Verify eligibility_results
        assert "eligibility_results" in bot_msg, "Missing eligibility_results in bot_message"
        results = bot_msg["eligibility_results"]
        assert len(results) > 0, "No eligibility results returned"
        print(f"✓ Eligibility results: {len(results)} schemes checked")
        
        # Verify tool_progress
        assert "tool_progress" in bot_msg, "Missing tool_progress in bot_message"
        assert len(bot_msg["tool_progress"]) >= 3, "Expected at least 3 tool_progress steps"
        print(f"✓ Tool progress steps: {len(bot_msg['tool_progress'])}")
        
        # Verify pdf_url
        assert "pdf_url" in bot_msg and bot_msg["pdf_url"], "Missing pdf_url in bot_message"
        pdf_url = bot_msg["pdf_url"]
        assert pdf_url.startswith("/api/pdf/"), f"Invalid pdf_url format: {pdf_url}"
        print(f"✓ PDF URL: {pdf_url}")
        
        # Verify Vidyasiri is FIRST and eligible (income < 150000, state = Karnataka)
        vidyasiri_found = False
        for i, result in enumerate(results):
            if "vidyasiri" in result.get("scheme", "").lower():
                vidyasiri_found = True
                assert result["eligible"] is True, f"Vidyasiri should be eligible for income=100000, state=Karnataka, got: {result}"
                assert i == 0, f"Vidyasiri should be FIRST in results, found at index {i}"
                print(f"✓ Vidyasiri is FIRST and ELIGIBLE: {result['reason']}")
                break
        
        assert vidyasiri_found, "Vidyasiri Scholarship not found in eligibility results"
        
        return pdf_url


class TestEligibilityRules:
    """Test eligibility rules - income is YEARLY, Vidyasiri requires Karnataka"""
    
    @pytest.fixture
    def user_id(self):
        phone = f"98765{int(time.time()) % 100000:05d}"
        requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": phone})
        response = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": phone, "otp": "1234"})
        return response.json()["user_id"]
    
    def test_vidyasiri_eligible_under_150000_karnataka(self, user_id):
        """Income < 150000/year + Karnataka = Vidyasiri eligible"""
        # Complete profile
        requests.post(f"{BASE_URL}/api/chat", json={"user_id": user_id, "content": "namaste", "language": "hi"})
        requests.post(f"{BASE_URL}/api/chat", json={"user_id": user_id, "content": "Test User", "language": "hi"})
        requests.post(f"{BASE_URL}/api/chat", json={"user_id": user_id, "content": "20", "language": "hi"})
        requests.post(f"{BASE_URL}/api/chat", json={"user_id": user_id, "content": "120000", "language": "hi"})  # 1.2 lakh yearly
        response = requests.post(f"{BASE_URL}/api/chat", json={"user_id": user_id, "content": "Karnataka", "language": "hi"})
        
        bot_msg = response.json()["bot_message"]
        results = bot_msg.get("eligibility_results", [])
        
        vidyasiri = next((r for r in results if "vidyasiri" in r.get("scheme", "").lower()), None)
        assert vidyasiri is not None, "Vidyasiri not in results"
        assert vidyasiri["eligible"] is True, f"Vidyasiri should be eligible for income=120000, Karnataka: {vidyasiri}"
        print(f"✓ Vidyasiri eligible for income=120000, Karnataka")
    
    def test_vidyasiri_ineligible_over_150000(self):
        """Income > 150000/year = Vidyasiri ineligible"""
        phone = f"98765{int(time.time()) % 100000:05d}"
        requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": phone})
        response = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": phone, "otp": "1234"})
        user_id = response.json()["user_id"]
        
        # Complete profile with income > 1.5 lakh
        requests.post(f"{BASE_URL}/api/chat", json={"user_id": user_id, "content": "namaste", "language": "hi"})
        requests.post(f"{BASE_URL}/api/chat", json={"user_id": user_id, "content": "Test User", "language": "hi"})
        requests.post(f"{BASE_URL}/api/chat", json={"user_id": user_id, "content": "20", "language": "hi"})
        requests.post(f"{BASE_URL}/api/chat", json={"user_id": user_id, "content": "200000", "language": "hi"})  # 2 lakh yearly - over limit
        response = requests.post(f"{BASE_URL}/api/chat", json={"user_id": user_id, "content": "Karnataka", "language": "hi"})
        
        bot_msg = response.json()["bot_message"]
        results = bot_msg.get("eligibility_results", [])
        
        vidyasiri = next((r for r in results if "vidyasiri" in r.get("scheme", "").lower()), None)
        assert vidyasiri is not None, "Vidyasiri not in results"
        assert vidyasiri["eligible"] is False, f"Vidyasiri should be INeligible for income=200000: {vidyasiri}"
        print(f"✓ Vidyasiri ineligible for income=200000 (> 1.5 lakh limit)")


class TestDemoMode:
    """Test DEMO_MODE triggers: beta, 10th, scholarship"""
    
    @pytest.fixture
    def user_id(self):
        phone = f"98765{int(time.time()) % 100000:05d}"
        requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": phone})
        response = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": phone, "otp": "1234"})
        return response.json()["user_id"]
    
    def test_demo_beta_trigger(self, user_id):
        """POST /api/chat with 'beta' returns instant Vidyasiri + PDF"""
        response = requests.post(f"{BASE_URL}/api/chat", json={
            "user_id": user_id, "content": "beta", "language": "hi"
        })
        assert response.status_code == 200
        bot_msg = response.json()["bot_message"]
        
        # Should return instant result, not profiler question
        assert "pdf_url" in bot_msg and bot_msg["pdf_url"], f"DEMO_MODE 'beta' should return pdf_url, got: {bot_msg.get('pdf_url')}"
        assert "eligibility_results" in bot_msg, "DEMO_MODE should return eligibility_results"
        
        # Check Vidyasiri is eligible
        results = bot_msg["eligibility_results"]
        vidyasiri = next((r for r in results if "vidyasiri" in r.get("scheme", "").lower()), None)
        assert vidyasiri is not None, "Vidyasiri not in DEMO results"
        assert vidyasiri["eligible"] is True, "Vidyasiri should be eligible in DEMO mode"
        print(f"✓ DEMO 'beta' returns instant Vidyasiri eligible + PDF: {bot_msg['pdf_url']}")
    
    def test_demo_10th_trigger(self, user_id):
        """POST /api/chat with '10th' returns instant result"""
        response = requests.post(f"{BASE_URL}/api/chat", json={
            "user_id": user_id, "content": "10th", "language": "hi"
        })
        bot_msg = response.json()["bot_message"]
        
        assert "pdf_url" in bot_msg and bot_msg["pdf_url"], "DEMO_MODE '10th' should return pdf_url"
        assert "eligibility_results" in bot_msg, "DEMO_MODE should return eligibility_results"
        print(f"✓ DEMO '10th' returns instant result + PDF")
    
    def test_demo_scholarship_trigger(self, user_id):
        """POST /api/chat with 'scholarship' returns instant result"""
        response = requests.post(f"{BASE_URL}/api/chat", json={
            "user_id": user_id, "content": "scholarship", "language": "hi"
        })
        bot_msg = response.json()["bot_message"]
        
        assert "pdf_url" in bot_msg and bot_msg["pdf_url"], "DEMO_MODE 'scholarship' should return pdf_url"
        assert "eligibility_results" in bot_msg, "DEMO_MODE should return eligibility_results"
        print(f"✓ DEMO 'scholarship' returns instant result + PDF")


class TestPDFDownload:
    """Test PDF generation and download"""
    
    def test_pdf_download_valid(self):
        """GET /api/pdf/{id} returns valid PDF file"""
        # First trigger DEMO mode to generate a PDF
        phone = f"98765{int(time.time()) % 100000:05d}"
        requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": phone})
        response = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": phone, "otp": "1234"})
        user_id = response.json()["user_id"]
        
        # Trigger DEMO mode
        response = requests.post(f"{BASE_URL}/api/chat", json={
            "user_id": user_id, "content": "beta", "language": "hi"
        })
        pdf_url = response.json()["bot_message"]["pdf_url"]
        
        # Download PDF
        pdf_response = requests.get(f"{BASE_URL}{pdf_url}")
        assert pdf_response.status_code == 200, f"PDF download failed: {pdf_response.status_code}"
        assert pdf_response.headers.get("content-type") == "application/pdf", f"Wrong content-type: {pdf_response.headers.get('content-type')}"
        
        # Check PDF magic bytes
        content = pdf_response.content
        assert content[:4] == b'%PDF', "Response is not a valid PDF file"
        print(f"✓ PDF download successful, size: {len(content)} bytes")
    
    def test_pdf_404_invalid_id(self):
        """GET /api/pdf/{invalid_id} returns 404"""
        response = requests.get(f"{BASE_URL}/api/pdf/invalid-uuid-12345")
        assert response.status_code == 404, f"Expected 404 for invalid PDF ID, got {response.status_code}"
        print("✓ PDF 404 for invalid ID")


class TestSearchSchemes:
    """Test search_schemes endpoint"""
    
    def test_search_schemes_document_scanned_format(self):
        """POST /api/search-schemes returns Document scanned format"""
        response = requests.post(f"{BASE_URL}/api/search-schemes", json={"query": "scholarship"})
        assert response.status_code == 200
        data = response.json()
        
        assert "tool_name" in data
        assert data["tool_name"] == "search_schemes"
        assert "documents_scanned" in data
        assert isinstance(data["documents_scanned"], list)
        assert len(data["documents_scanned"]) > 0, "No documents scanned"
        
        if data.get("match_found"):
            assert "result_text" in data or "matched_schemes" in data
        
        print(f"✓ search_schemes returned documents_scanned: {data['documents_scanned']}")
    
    def test_search_schemes_with_10th_trigger(self):
        """POST /api/search-schemes with '10th' in DEMO_MODE returns Vidyasiri"""
        response = requests.post(f"{BASE_URL}/api/search-schemes", json={"query": "10th pass scholarship"})
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("match_found") is True, "Expected match for '10th pass scholarship'"
        print(f"✓ search_schemes '10th pass scholarship' found match")


class TestSchemesEndpoint:
    """Test GET /api/schemes"""
    
    def test_get_schemes_returns_3(self):
        """GET /api/schemes returns 3 seeded schemes"""
        response = requests.get(f"{BASE_URL}/api/schemes")
        assert response.status_code == 200
        schemes = response.json()
        
        assert isinstance(schemes, list)
        assert len(schemes) >= 3, f"Expected at least 3 schemes, got {len(schemes)}"
        
        # Check scheme names
        scheme_names = [s.get("name", "").lower() for s in schemes]
        assert any("awas" in n for n in scheme_names), "Missing Pradhan Mantri Awas Yojana"
        assert any("vidyasiri" in n for n in scheme_names), "Missing Vidyasiri Scholarship"
        assert any("vidya lakshmi" in n or "education loan" in n for n in scheme_names), "Missing Vidya Lakshmi Education Loan"
        
        print(f"✓ GET /api/schemes returns {len(schemes)} schemes: {scheme_names}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
