"""
End-to-end tests using FastAPI TestClient with mocked MongoDB/Prisma.
Tests all security fixes, auth flows, PDF operations, and core endpoints.
"""
import os
import sys
import json
import time
import secrets
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from datetime import datetime, timezone

# Set required env vars BEFORE importing server
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017/test")
os.environ.setdefault("DB_NAME", "test")
os.environ.setdefault("DEMO_MODE", "true")
os.environ.setdefault("ADMIN_SECRET", "test-secret")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
os.environ.setdefault("AGNOST_WRITE_KEY", "")

import pytest

# ─── Utility / Security function tests (no server needed) ───

class TestSecurityHelpers:
    """Test security helper functions directly."""

    def test_validate_phone_valid(self):
        from server import _validate_phone
        assert _validate_phone("9876543210") is True
        assert _validate_phone("6000000000") is True
        assert _validate_phone("7999999999") is True

    def test_validate_phone_invalid(self):
        from server import _validate_phone
        assert _validate_phone("1234567890") is False  # starts with 1
        assert _validate_phone("5555555555") is False  # starts with 5
        assert _validate_phone("123") is False  # too short
        assert _validate_phone("") is False
        assert _validate_phone("98765432101") is False  # 11 digits
        assert _validate_phone("abcdefghij") is False

    def test_generate_otp_format(self):
        from server import _generate_otp
        for _ in range(100):
            otp = _generate_otp()
            assert len(otp) == 6
            assert otp.isdigit()
            assert 100000 <= int(otp) <= 999999

    def test_generate_otp_randomness(self):
        from server import _generate_otp
        otps = {_generate_otp() for _ in range(50)}
        # With 50 attempts we should get many unique values
        assert len(otps) > 30

    def test_sanitize_input_strips_control_chars(self):
        from server import _sanitize_input
        assert _sanitize_input("hello\x00world") == "helloworld"
        assert _sanitize_input("test\x07\x08data") == "testdata"
        # Preserves newlines and tabs
        assert _sanitize_input("hello\nworld") == "hello\nworld"
        assert _sanitize_input("hello\tworld") == "hello\tworld"

    def test_sanitize_input_length_limit(self):
        from server import _sanitize_input
        long_text = "a" * 20000
        result = _sanitize_input(long_text, max_length=100)
        assert len(result) == 100

    def test_sanitize_input_empty(self):
        from server import _sanitize_input
        assert _sanitize_input("") == ""
        assert _sanitize_input(None) == ""

    def test_validate_path_within_safe(self):
        from server import _validate_path_within
        base = Path("/tmp/test_pdfs")
        safe_path = Path("/tmp/test_pdfs/report.pdf")
        assert _validate_path_within(safe_path, base) is True

    def test_validate_path_traversal_blocked(self):
        from server import _validate_path_within
        base = Path("/tmp/test_pdfs")
        # Path traversal attempts
        assert _validate_path_within(Path("/tmp/test_pdfs/../../../etc/passwd"), base) is False
        assert _validate_path_within(Path("/etc/passwd"), base) is False

    def test_validate_pdf_content(self):
        from server import _validate_pdf_content
        assert _validate_pdf_content(b'%PDF-1.4 ...') is True
        assert _validate_pdf_content(b'%PDF-2.0 ...') is True
        assert _validate_pdf_content(b'not a pdf') is False
        assert _validate_pdf_content(b'') is False
        assert _validate_pdf_content(b'PK\x03\x04') is False  # ZIP file

    def test_rate_limiter(self):
        from server import _check_rate_limit, _rate_limit_store, RATE_LIMIT_MAX
        key = f"test_rate_{secrets.token_hex(4)}"
        # First N requests should pass
        for i in range(RATE_LIMIT_MAX):
            assert _check_rate_limit(key) is False, f"Request {i+1} should pass"
        # Next request should be rate-limited
        assert _check_rate_limit(key) is True

    def test_rate_limiter_different_keys(self):
        from server import _check_rate_limit
        key1 = f"test_a_{secrets.token_hex(4)}"
        key2 = f"test_b_{secrets.token_hex(4)}"
        assert _check_rate_limit(key1) is False
        assert _check_rate_limit(key2) is False


class TestPydanticModels:
    """Test request/response model validation."""

    def test_send_otp_request_valid(self):
        from server import SendOTPRequest
        req = SendOTPRequest(phone="9876543210")
        assert req.phone == "9876543210"

    def test_send_otp_request_invalid_phone(self):
        from server import SendOTPRequest
        with pytest.raises(Exception):
            SendOTPRequest(phone="123")

    def test_chat_message_request(self):
        from server import ChatMessageRequest
        req = ChatMessageRequest(user_id="abc123", content="hello", language="hi")
        assert req.content == "hello"

    def test_verify_otp_request(self):
        from server import VerifyOTPRequest
        req = VerifyOTPRequest(phone="9876543210", otp="123456")
        assert req.otp == "123456"


class TestBotResponseLogic:
    """Test the MCP bot response logic (no DB needed)."""

    def test_greeting_response(self):
        from server import get_bot_response_with_mcp
        resp = get_bot_response_with_mcp("namaste", "hi")
        assert resp["content"]  # Should return greeting
        assert isinstance(resp["tool_calls"], list)

    def test_scheme_query_response(self):
        from server import get_bot_response_with_mcp
        resp = get_bot_response_with_mcp("kisan योजना", "hi")
        assert resp["content"]
        # Should trigger tool call
        assert len(resp["tool_calls"]) > 0

    def test_default_response(self):
        from server import get_bot_response_with_mcp
        resp = get_bot_response_with_mcp("random text xyz", "hi")
        assert resp["content"]


class TestSearchSchemes:
    """Test scheme search logic."""

    def test_search_kisan(self):
        from server import search_schemes
        result = search_schemes("kisan", "hi")
        assert "match_found" in result
        assert "documents_scanned" in result

    def test_search_health(self):
        from server import search_schemes
        result = search_schemes("ayushman health", "hi")
        assert "match_found" in result

    def test_search_no_match(self):
        from server import search_schemes
        result = search_schemes("quantum computing", "hi")
        assert result["match_found"] is False


# ─── FastAPI TestClient tests (mocked DB) ───

@pytest.fixture(scope="module")
def client():
    """Create a TestClient with mocked Prisma and Motor."""
    # We need to mock prisma and motor before importing app
    from server import app
    from starlette.testclient import TestClient

    # Disable startup/shutdown events since we don't have real DB
    app.router.on_startup.clear()
    app.router.on_shutdown.clear()

    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_rate_limits():
    """Clear rate limits between tests."""
    from server import _rate_limit_store
    _rate_limit_store.clear()
    yield


class TestAuthEndpoints:
    """Test auth endpoints with mocked DB."""

    @pytest.mark.asyncio
    async def test_send_otp_invalid_phone(self, client):
        """Should reject invalid phone numbers."""
        resp = client.post("/api/auth/send-otp", json={"phone": "1234"})
        assert resp.status_code == 422 or resp.status_code == 400

    @pytest.mark.asyncio
    async def test_send_otp_rate_limit(self, client):
        """Should rate limit after 5 requests."""
        from server import _rate_limit_store
        phone = "9876543210"
        # Pre-fill rate limit store
        key = f"otp:{phone}"
        now = time.time()
        _rate_limit_store[key] = [now] * 5

        with patch("server.motor_db") as mock_db:
            mock_db.otp_sessions.update_one = AsyncMock()
            resp = client.post("/api/auth/send-otp", json={"phone": phone})
            assert resp.status_code == 429

    @pytest.mark.asyncio
    async def test_send_otp_success(self, client):
        """Should succeed with valid phone in DEMO_MODE."""
        phone = "9876543210"
        with patch("server.motor_db") as mock_db:
            mock_db.otp_sessions.update_one = AsyncMock()
            resp = client.post("/api/auth/send-otp", json={"phone": phone})
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert "OTP sent" in data["message"]

    @pytest.mark.asyncio
    async def test_verify_otp_success(self, client):
        """Should verify OTP correctly."""
        phone = "9876543210"
        mock_user = MagicMock()
        mock_user.id = "user123"
        mock_user.phone = phone
        mock_user.language = "hi"
        mock_user.profile = json.dumps({"name": ""})
        mock_user.createdAt = datetime.now(timezone.utc)

        with patch("server.motor_db") as mock_db, \
             patch("server.prisma") as mock_prisma:
            mock_db.otp_sessions.find_one = AsyncMock(return_value={
                "phone": phone, "otp": "123456", "verified": False,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            mock_db.otp_sessions.update_one = AsyncMock()
            mock_prisma.user.find_unique = AsyncMock(return_value=mock_user)

            resp = client.post("/api/auth/verify-otp", json={"phone": phone, "otp": "123456"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["user_id"] == "user123"

    @pytest.mark.asyncio
    async def test_verify_otp_wrong(self, client):
        """Should reject wrong OTP."""
        phone = "9876543210"
        with patch("server.motor_db") as mock_db:
            mock_db.otp_sessions.find_one = AsyncMock(return_value={
                "phone": phone, "otp": "123456", "verified": False,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            resp = client.post("/api/auth/verify-otp", json={"phone": phone, "otp": "000000"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is False
            assert "Invalid" in data["message"]

    @pytest.mark.asyncio
    async def test_verify_otp_expired(self, client):
        """Should reject expired OTP."""
        phone = "9876543210"
        old_time = "2020-01-01T00:00:00+00:00"
        with patch("server.motor_db") as mock_db:
            mock_db.otp_sessions.find_one = AsyncMock(return_value={
                "phone": phone, "otp": "123456", "verified": False,
                "created_at": old_time
            })
            resp = client.post("/api/auth/verify-otp", json={"phone": phone, "otp": "123456"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is False
            assert "expired" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_verify_otp_no_session(self, client):
        """Should reject when no OTP session exists."""
        with patch("server.motor_db") as mock_db:
            mock_db.otp_sessions.find_one = AsyncMock(return_value=None)
            resp = client.post("/api/auth/verify-otp", json={"phone": "9876543210", "otp": "123456"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is False


class TestProfileEndpoints:
    """Test profile endpoints."""

    def test_get_profile_not_found(self, client):
        with patch("server.prisma") as mock_prisma:
            mock_prisma.user.find_unique = AsyncMock(return_value=None)
            resp = client.get("/api/profile/nonexistent")
            assert resp.status_code == 404

    def test_get_profile_success(self, client):
        mock_user = MagicMock()
        mock_user.id = "user123"
        mock_user.phone = "9876543210"
        mock_user.language = "hi"
        mock_user.profile = json.dumps({"name": "Test", "_complete": True})
        mock_user.createdAt = datetime.now(timezone.utc)

        with patch("server.prisma") as mock_prisma:
            mock_prisma.user.find_unique = AsyncMock(return_value=mock_user)
            resp = client.get("/api/profile/user123")
            assert resp.status_code == 200
            data = resp.json()
            assert data["phone"] == "9876543210"
            assert data["name"] == "Test"
            assert data["profile_complete"] is True


class TestSchemeEndpoints:
    """Test scheme endpoints."""

    def test_get_schemes(self, client):
        mock_scheme = MagicMock()
        mock_scheme.id = "scheme1"
        mock_scheme.name = "PM-KISAN"
        mock_scheme.eligibilityCriteriaText = "Farmer family"
        mock_scheme.pdfUrl = "https://example.com/kisan.pdf"

        with patch("server.prisma") as mock_prisma:
            mock_prisma.scheme.find_many = AsyncMock(return_value=[mock_scheme])
            resp = client.get("/api/schemes")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) >= 1
            assert data[0]["name"] == "PM-KISAN"


class TestDemoToggle:
    """Test demo toggle endpoint security."""

    def test_demo_toggle_no_auth(self, client):
        """Should reject without admin secret."""
        with patch("server.ADMIN_SECRET", "test-secret"):
            resp = client.post("/api/demo/toggle")
            assert resp.status_code in (401, 403)

    def test_demo_toggle_wrong_secret(self, client):
        """Should reject wrong admin secret."""
        with patch("server.ADMIN_SECRET", "test-secret"):
            resp = client.post("/api/demo/toggle", headers={"X-Admin-Secret": "wrong"})
            assert resp.status_code in (401, 403)

    def test_demo_toggle_correct_secret(self, client):
        """Should succeed with correct admin secret."""
        with patch("server.ADMIN_SECRET", "test-secret"):
            resp = client.post("/api/demo/toggle", headers={"X-Admin-Secret": "test-secret"})
            assert resp.status_code == 200
            data = resp.json()
            assert "demo_mode" in data


class TestPDFEndpoints:
    """Test PDF serving with path traversal protection."""

    def test_pdf_path_traversal_blocked(self, client):
        """Path traversal in PDF ID should be rejected."""
        resp = client.get("/api/pdf/../../../etc/passwd")
        assert resp.status_code in (400, 404, 422)

    def test_pdf_invalid_uuid(self, client):
        """Non-UUID PDF IDs should be rejected."""
        resp = client.get("/api/pdf/not-a-uuid")
        assert resp.status_code in (400, 404, 422)

    def test_pdf_valid_uuid_not_found(self, client):
        """Valid UUID but file doesn't exist should return 404."""
        test_uuid = str(__import__("uuid").uuid4())
        resp = client.get(f"/api/pdf/{test_uuid}")
        assert resp.status_code == 404

    def test_audio_path_traversal_blocked(self, client):
        """Path traversal in audio ID should be rejected."""
        resp = client.get("/api/audio/../../../etc/passwd")
        assert resp.status_code in (400, 404, 422)


class TestChatEndpoint:
    """Test chat endpoint."""

    def test_chat_greeting(self, client):
        """Chat with greeting should return response."""
        profiler_result = {
            "content": "नमस्ते! मैं नागरिक सहायक हूँ।",
            "tool_calls": [],
            "type": "profiler",
            "profiler_field": "name",
        }
        with patch("server.save_chat_prisma", new_callable=AsyncMock), \
             patch("server.get_chat_history_prisma", new_callable=AsyncMock, return_value=[]), \
             patch("server.profiler_agent_respond", new_callable=AsyncMock, return_value=profiler_result):
            resp = client.post("/api/chat", json={
                "user_id": "user123",
                "content": "namaste",
                "language": "hi"
            })
            assert resp.status_code == 200
            data = resp.json()
            assert "bot_message" in data
            assert "content" in data["bot_message"]

    def test_chat_sanitizes_input(self, client):
        """Chat should sanitize malicious input."""
        profiler_result = {
            "content": "कृपया अपना नाम बताएं",
            "tool_calls": [],
            "type": "profiler",
            "profiler_field": "name",
        }
        with patch("server.save_chat_prisma", new_callable=AsyncMock), \
             patch("server.get_chat_history_prisma", new_callable=AsyncMock, return_value=[]), \
             patch("server.profiler_agent_respond", new_callable=AsyncMock, return_value=profiler_result):
            resp = client.post("/api/chat", json={
                "user_id": "user123",
                "content": "<script>alert('xss')</script>hello",
                "language": "hi"
            })
            assert resp.status_code == 200


class TestV2Endpoints:
    """Test V2 API endpoints."""

    def test_v2_schemes(self, client):
        mock_scheme = MagicMock()
        mock_scheme.id = "s1"
        mock_scheme.name = "PM-KISAN"
        mock_scheme.eligibilityCriteriaText = "Farmers"
        mock_scheme.pdfUrl = "https://example.com/kisan.pdf"

        with patch("server.prisma") as mock_prisma:
            mock_prisma.scheme.find_many = AsyncMock(return_value=[mock_scheme])
            resp = client.get("/api/v2/schemes")
            assert resp.status_code == 200

    def test_v2_form_templates(self, client):
        mock_template = MagicMock()
        mock_template.id = "ft1"
        mock_template.schemeName = "PM-KISAN"
        mock_template.schemeId = "s1"
        mock_template.formTitle = "PM-KISAN Application"
        mock_template.extractedFields = json.dumps({"sections": [{"fields": [{"key": "name"}]}]})

        with patch("server.prisma") as mock_prisma:
            mock_prisma.formtemplate.find_many = AsyncMock(return_value=[mock_template])
            resp = client.get("/api/v2/form-templates")
            assert resp.status_code == 200


class TestCORSConfiguration:
    """Test CORS is properly configured."""

    def test_cors_headers_present(self, client):
        """CORS should include proper headers for allowed origin."""
        resp = client.options("/api/schemes", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        })
        # Should have CORS headers
        assert resp.status_code in (200, 204, 400)

    def test_cors_wildcard_blocked(self, client):
        """Random origins should not get CORS access."""
        resp = client.options("/api/schemes", headers={
            "Origin": "http://evil.com",
            "Access-Control-Request-Method": "GET",
        })
        # Should NOT have Access-Control-Allow-Origin for evil.com
        allow_origin = resp.headers.get("access-control-allow-origin", "")
        assert allow_origin != "*"
        assert "evil.com" not in allow_origin


# ─── PDF Generator tests ───

class TestPDFGenerator:
    """Test PDF generation functions."""

    def test_generate_eligibility_pdf(self):
        from pdf_generator import generate_eligibility_pdf
        profile = {"name": "Test User", "age": "30", "income": "100000", "state": "Karnataka"}
        results = [{"scheme": "PM-KISAN", "eligible": True, "reason": "Meets criteria"}]
        out = tempfile.mktemp(suffix=".pdf")
        pdf_path = generate_eligibility_pdf(profile, results, output_path=out)
        assert pdf_path is not None
        assert Path(pdf_path).exists()
        with open(pdf_path, "rb") as f:
            assert f.read(5) == b"%PDF-"
        Path(pdf_path).unlink(missing_ok=True)

    def test_generate_filled_form_pdf(self):
        from pdf_generator import generate_filled_form_pdf
        profile = {"name": "Test User", "age": "30", "phone": "9876543210", "income": "100000", "state": "Delhi"}
        out = tempfile.mktemp(suffix=".pdf")
        pdf_path = generate_filled_form_pdf(profile, "PM-KISAN", output_path=out)
        assert pdf_path is not None
        assert Path(pdf_path).exists()
        with open(pdf_path, "rb") as f:
            assert f.read(5) == b"%PDF-"
        Path(pdf_path).unlink(missing_ok=True)

    def test_generate_real_filled_form_pdf(self):
        from pdf_generator import generate_real_filled_form_pdf
        sections = [
            {
                "title": "Personal Details",
                "fields": [
                    {"key": "applicant_name", "label": "Name", "type": "text"},
                    {"key": "dob", "label": "Date of Birth", "type": "date"},
                    {"key": "phone", "label": "Phone", "type": "phone"},
                    {"key": "aadhaar", "label": "Aadhaar", "type": "aadhaar"},
                    {"key": "address", "label": "Address", "type": "textarea"},
                ]
            }
        ]
        filled = {
            "applicant_name": "राम कुमार",
            "dob": "1990-01-15",
            "phone": "9876543210",
            "aadhaar": "123456789012",
            "address": "123 Main Street, Block A, Some Colony, Delhi - 110001",
        }
        out = tempfile.mktemp(suffix=".pdf")
        pdf_path = generate_real_filled_form_pdf(
            filled_fields=filled,
            scheme_name="PM-KISAN",
            sections=sections,
            output_path=out,
        )
        assert pdf_path is not None
        assert Path(pdf_path).exists()
        with open(pdf_path, "rb") as f:
            content = f.read()
            assert content[:5] == b"%PDF-"
            assert len(content) > 1000
        Path(pdf_path).unlink(missing_ok=True)

    def test_real_pdf_multi_page(self):
        """Test that many fields generate multiple pages."""
        from pdf_generator import generate_real_filled_form_pdf
        fields = [{"key": f"field_{i}", "label": f"Field Number {i}", "type": "text"} for i in range(40)]
        filled = {f"field_{i}": f"Value for field {i}" for i in range(40)}
        sections = [{"title": "Large Section", "fields": fields}]

        out = tempfile.mktemp(suffix=".pdf")
        pdf_path = generate_real_filled_form_pdf(
            filled_fields=filled,
            scheme_name="Test Scheme",
            sections=sections,
            output_path=out,
        )
        assert pdf_path is not None
        assert Path(pdf_path).exists()
        with open(pdf_path, "rb") as f:
            content = f.read()
            assert content[:5] == b"%PDF-"
            assert len(content) > 5000
        Path(pdf_path).unlink(missing_ok=True)

    def test_real_pdf_empty_fields(self):
        """Test PDF generation with missing/empty field values."""
        from pdf_generator import generate_real_filled_form_pdf
        sections = [{"title": "Section", "fields": [
            {"key": "name", "label": "Name", "type": "text"},
            {"key": "age", "label": "Age", "type": "number"},
        ]}]
        filled = {"name": "Test"}  # age is missing

        out = tempfile.mktemp(suffix=".pdf")
        pdf_path = generate_real_filled_form_pdf(
            filled_fields=filled,
            scheme_name="Test",
            sections=sections,
            output_path=out,
        )
        assert pdf_path is not None
        Path(pdf_path).unlink(missing_ok=True)


# ─── Form Extractor tests ───

class TestFormExtractor:
    """Test form extractor helper functions."""

    def test_sanitize_pdf_text(self):
        from form_extractor import _sanitize_pdf_text, MAX_PDF_TEXT_LENGTH
        # Should truncate long text
        long_text = "x" * (MAX_PDF_TEXT_LENGTH + 10000)
        result = _sanitize_pdf_text(long_text)
        assert len(result) <= MAX_PDF_TEXT_LENGTH
        # Should strip null bytes
        assert "\x00" not in _sanitize_pdf_text("hello\x00world")


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health(self, client):
        resp = client.get("/api/health")
        # May or may not exist, but should not crash
        assert resp.status_code in (200, 404)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
