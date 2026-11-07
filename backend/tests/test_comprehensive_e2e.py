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

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001').rstrip('/')


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
        """POST /api/auth/send-otp rejects an invalid phone.

        FastAPI returns 422 for a request that fails model validation; 400 is
        the hand-rolled-check alternative. Either is a correct rejection, so the
        test accepts both rather than pinning the exact code."""
        response = requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": "123"})
        assert response.status_code in (400, 422), \
            f"Expected rejection for invalid phone, got {response.status_code}"
        print("✓ send-otp rejects invalid phone")
    
    def test_verify_otp_success(self):
        """POST /api/auth/verify-otp with otp=1234 returns user_id"""
        phone = f"99887{int(time.time()) % 100000:05d}"
        # First send OTP
        requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": phone})
        
        # Verify with 1234
        response = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": phone, "otp": "123456"})
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
        # A wrong code is an authentication failure: 401 with a reason, and the
        # remaining attempts named so the citizen knows where they stand.
        assert response.status_code == 401, f"Expected 401 for wrong OTP, got {response.status_code}"
        assert "attempt" in response.json()["detail"]
        print("✓ verify-otp rejects wrong OTP")


class TestProfilerFlow:
    """Test complete profiler agent flow: namaste → name → age → income → state → complete"""
    
    @pytest.fixture
    def user_id(self):
        """Create a fresh user for testing"""
        phone = f"98765{int(time.time()) % 100000:05d}"
        requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": phone})
        response = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": phone, "otp": "123456"})
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
        
        # The completed profiler scores the whole catalogue (the original demo
        # pinned one scheme - Vidyasiri - to the top, but that scheme has since
        # been replaced by the real government-form set). The integration
        # contract is what is asserted: every result is well-formed and at
        # least one scheme comes back eligible for this low-income profile.
        assert all(
            {"scheme", "eligible"} <= set(r) for r in results
        ), "each eligibility result must name a scheme and an eligibility"
        assert any(r.get("eligible") for r in results), \
            "a low-income applicant should qualify for at least one scheme"
        print(f"✓ Profiler returned {len(results)} eligibility results")

        return pdf_url


class TestEligibilityRules:
    """The profiler → eligibility-engine integration path.

    These once pinned the specific verdict of one income-gated scheme
    (Vidyasiri), which has since been replaced by the real government-form
    catalogue. The income thresholds themselves are now exercised directly
    against the catalogue in tests/test_catalog_levels.py and
    tests/test_gov_forms.py; what is asserted here is the integration contract -
    the chat profiler completes and hands back a scored catalogue."""

    @pytest.fixture
    def user_id(self):
        phone = f"98765{int(time.time()) % 100000:05d}"
        requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": phone})
        response = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": phone, "otp": "123456"})
        return response.json()["user_id"]

    def _run_profiler(self, user_id, income):
        for content in ("namaste", "Test User", "20", str(income)):
            requests.post(f"{BASE_URL}/api/chat",
                          json={"user_id": user_id, "content": content, "language": "hi"})
        response = requests.post(f"{BASE_URL}/api/chat",
                                 json={"user_id": user_id, "content": "Karnataka", "language": "hi"})
        return response.json()["bot_message"]

    def test_low_income_profile_scores_the_catalogue(self, user_id):
        """A completed low-income profile returns well-formed eligibility results."""
        results = self._run_profiler(user_id, 120000).get("eligibility_results", [])
        assert results, "profiler should return eligibility results"
        assert all({"scheme", "eligible"} <= set(r) for r in results)
        assert any(r.get("eligible") for r in results), \
            "a low-income applicant should qualify for at least one scheme"
        print(f"✓ Low-income profile scored {len(results)} schemes")

    def test_income_is_captured_in_the_profile(self, user_id):
        """The yearly income the citizen gives is stored on their profile.

        The chat profiler collects name/age/income/state into the basic
        profile, which is the value the eligibility engine gates on."""
        self._run_profiler(user_id, 200000)
        profile = requests.get(
            f"{BASE_URL}/api/profile/{user_id}",
            headers={"X-User-Id": user_id}).json().get("profile_data", {})
        assert profile.get("income") == 200000, \
            f"income not captured in profile: {profile}"
        print("✓ Income captured in the profile")


class TestDemoMode:
    """Test DEMO_MODE triggers: beta, 10th, scholarship"""
    
    @pytest.fixture
    def user_id(self):
        phone = f"98765{int(time.time()) % 100000:05d}"
        requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": phone})
        response = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": phone, "otp": "123456"})
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
        response = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": phone, "otp": "123456"})
        user_id = response.json()["user_id"]
        
        # Trigger DEMO mode
        response = requests.post(f"{BASE_URL}/api/chat", json={
            "user_id": user_id, "content": "beta", "language": "hi"
        })
        pdf_url = response.json()["bot_message"]["pdf_url"]

        # Download PDF as its owner (the X-User-Id header the real app sends;
        # the route enforces ownership, DPDP s8(4)).
        pdf_response = requests.get(f"{BASE_URL}{pdf_url}",
                                    headers={"X-User-Id": user_id})
        assert pdf_response.status_code == 200, f"PDF download failed: {pdf_response.status_code}"
        assert pdf_response.headers.get("content-type") == "application/pdf", f"Wrong content-type: {pdf_response.headers.get('content-type')}"

        # Check PDF magic bytes
        content = pdf_response.content
        assert content[:4] == b'%PDF', "Response is not a valid PDF file"
        print(f"✓ PDF download successful, size: {len(content)} bytes")

    def test_pdf_404_invalid_id(self):
        """GET /api/pdf/{invalid_id} returns 404 to an authenticated caller.

        An authenticated request for an id with no ownership record is answered
        404 - indistinguishable from one that never existed."""
        phone = f"99886{int(time.time()) % 100000:05d}"
        requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": phone})
        caller = requests.post(f"{BASE_URL}/api/auth/verify-otp",
                               json={"phone": phone, "otp": "123456"}).json()["user_id"]
        # Anonymous: refused outright. Signed in: not found.
        assert requests.get(f"{BASE_URL}/api/pdf/invalid-uuid-12345").status_code == 401
        response = requests.get(f"{BASE_URL}/api/pdf/invalid-uuid-12345",
                                headers={"X-User-Id": caller})
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
        
        # Check a few stable scheme names that are actually in the catalogue.
        # (The MVP's Vidyasiri and Vidya Lakshmi were replaced by the real
        # government-form set.)
        scheme_names = [s.get("name", "").lower() for s in schemes]
        assert any("awas" in n for n in scheme_names), "Missing Pradhan Mantri Awas Yojana"
        assert any("kisan" in n for n in scheme_names), "Missing PM-KISAN"
        assert any("scholarship" in n for n in scheme_names), "Missing a scholarship scheme"
        
        print(f"✓ GET /api/schemes returns {len(schemes)} schemes: {scheme_names}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
