"""
Test Download All PDFs endpoints - 405 Method Not Allowed Fix
Tests that /api/download-all and /api/download-all-zip accept GET requests
Previously they were POST-only which caused 405 errors when frontend called with GET
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session

@pytest.fixture
def authenticated_user(api_client):
    """Create a test user and return user_id"""
    # Send OTP
    resp = api_client.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": "9876543210"})
    assert resp.status_code == 200
    
    # Verify OTP
    resp = api_client.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": "9876543210", "otp": "1234"})
    assert resp.status_code == 200
    return resp.json()["user_id"]

@pytest.fixture
def demo_pdf_urls(api_client, authenticated_user):
    """Get PDF URLs from demo response by sending 'scholarship' trigger"""
    resp = api_client.post(f"{BASE_URL}/api/chat", json={
        "user_id": authenticated_user,
        "content": "scholarship",
        "language": "hi"
    })
    assert resp.status_code == 200
    data = resp.json()
    bot_msg = data.get("bot_message", {})
    pdf_urls = bot_msg.get("pdf_urls", [])
    assert len(pdf_urls) >= 2, "Demo should return at least 2 PDF URLs"
    return pdf_urls


class TestDownloadAllGet:
    """Test GET /api/download-all endpoint (was POST-only, now GET)"""
    
    def test_download_all_get_returns_200(self, api_client):
        """GET /api/download-all?user_id=test&count=2 should return 200"""
        resp = api_client.get(f"{BASE_URL}/api/download-all", params={"user_id": "test", "count": 2})
        assert resp.status_code == 200
        
    def test_download_all_get_returns_tracked_true(self, api_client):
        """GET /api/download-all should return {tracked: true}"""
        resp = api_client.get(f"{BASE_URL}/api/download-all", params={"user_id": "test", "count": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("tracked") == True
        
    def test_download_all_get_includes_count(self, api_client):
        """GET /api/download-all should return the count passed"""
        resp = api_client.get(f"{BASE_URL}/api/download-all", params={"user_id": "test", "count": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("count") == 5


class TestDownloadAllZipGet:
    """Test GET /api/download-all-zip endpoint (was POST-only, now GET)"""
    
    def test_download_all_zip_without_pdf_ids_returns_400(self, api_client):
        """GET /api/download-all-zip without pdf_ids should return 400"""
        resp = api_client.get(f"{BASE_URL}/api/download-all-zip", params={"user_id": "test"})
        assert resp.status_code == 400
        data = resp.json()
        assert "No pdf_ids provided" in data.get("detail", "")
        
    def test_download_all_zip_with_nonexistent_ids_returns_404(self, api_client):
        """GET /api/download-all-zip with nonexistent IDs should return 404"""
        resp = api_client.get(f"{BASE_URL}/api/download-all-zip", params={
            "pdf_ids": "nonexistent-uuid",
            "user_id": "test"
        })
        assert resp.status_code == 404
        data = resp.json()
        assert "No PDFs found" in data.get("detail", "")
        
    def test_download_all_zip_with_valid_ids_returns_zip(self, api_client, demo_pdf_urls):
        """GET /api/download-all-zip with valid IDs should return a zip file"""
        # Extract PDF IDs from URLs
        pdf_ids = []
        for p in demo_pdf_urls:
            parts = (p.get("pdf_url") or "").split("/")
            if parts:
                pdf_ids.append(parts[-1])
        
        pdf_ids_str = ",".join(pdf_ids)
        resp = api_client.get(f"{BASE_URL}/api/download-all-zip", params={
            "pdf_ids": pdf_ids_str,
            "user_id": "test"
        })
        assert resp.status_code == 200
        assert "application/zip" in resp.headers.get("Content-Type", "")


class TestIndividualPdfDownload:
    """Test individual PDF download via GET /api/pdf/{uuid}"""
    
    def test_pdf_download_returns_200(self, api_client, demo_pdf_urls):
        """GET /api/pdf/{uuid} should return 200 for valid PDF"""
        pdf_url = demo_pdf_urls[0].get("pdf_url", "")
        assert pdf_url, "PDF URL should not be empty"
        
        resp = api_client.get(f"{BASE_URL}{pdf_url}")
        assert resp.status_code == 200
        assert "application/pdf" in resp.headers.get("Content-Type", "")
        
    def test_pdf_download_nonexistent_returns_404(self, api_client):
        """GET /api/pdf/{uuid} should return 404 for nonexistent PDF"""
        resp = api_client.get(f"{BASE_URL}/api/pdf/nonexistent-uuid")
        assert resp.status_code == 404


class TestDemoResponseContainsPdfUrls:
    """Test that demo response contains pdf_urls array with 2 items"""
    
    def test_scholarship_trigger_returns_pdf_urls(self, api_client, authenticated_user):
        """Sending 'scholarship' should return pdf_urls array with 2 items"""
        resp = api_client.post(f"{BASE_URL}/api/chat", json={
            "user_id": authenticated_user,
            "content": "scholarship",
            "language": "hi"
        })
        assert resp.status_code == 200
        data = resp.json()
        
        bot_msg = data.get("bot_message", {})
        pdf_urls = bot_msg.get("pdf_urls", [])
        
        # Verify 2 PDFs
        assert len(pdf_urls) == 2, f"Expected 2 PDFs, got {len(pdf_urls)}"
        
        # Verify structure
        for pdf in pdf_urls:
            assert "pdf_url" in pdf
            assert "scheme_name" in pdf
            assert pdf["pdf_url"].startswith("/api/pdf/")
